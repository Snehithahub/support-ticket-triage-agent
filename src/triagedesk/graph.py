"""LangGraph workflow: normalize -> classify -> retrieve -> draft -> verify -> route.

verify loops back to draft once (configurable) with the verifier's issues as feedback.
Nodes never raise on provider failures: they record the error and the router sends the
ticket to a human.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from triagedesk.config import Settings
from triagedesk.json_repair import JsonRepairError, extract_json, was_repaired
from triagedesk.llm import LLMClient, LLMError
from triagedesk.normalize import normalize_ticket
from triagedesk.policy import AutomationPolicy, route
from triagedesk.prompts import classify_messages, draft_messages
from triagedesk.retrieval import Retriever
from triagedesk.schemas import Classification, DraftOutput, RetrievedChunk, Verification
from triagedesk.taxonomy import Intent
from triagedesk.verify import render_citations, verify_draft

log = logging.getLogger(__name__)


class TriageState(TypedDict, total=False):
    subject: str
    body: str
    clean_text: str
    masked_text: str
    language: str
    pii_types: list[str]
    classification: dict[str, Any]
    classify_meta: dict[str, Any]
    retrieved: list[dict[str, Any]]
    draft: dict[str, Any] | None
    draft_meta: dict[str, Any]
    verification: dict[str, Any] | None
    routing: dict[str, Any]
    errors: list[str]
    timings_ms: dict[str, float]


@dataclass
class TriageDeps:
    llm: LLMClient
    retriever: Retriever
    policy: AutomationPolicy
    settings: Settings


def _timed(name: str, fn):
    def wrapper(state: TriageState) -> dict:
        t0 = time.perf_counter()
        update = fn(state)
        timings = dict(state.get("timings_ms", {}))
        timings[name] = round(timings.get(name, 0.0) + (time.perf_counter() - t0) * 1000, 1)
        update["timings_ms"] = timings
        return update

    return wrapper


def classify_with_repair(llm: LLMClient, subject: str, text: str, max_attempts: int) -> tuple[Classification, dict]:
    """Call the LLM, repair/validate its JSON, and re-ask with the error on failure."""
    messages = classify_messages(subject, text)
    meta: dict[str, Any] = {"attempts": 0, "repaired": False, "fallback": False, "errors": []}
    for _ in range(max_attempts):
        meta["attempts"] += 1
        try:
            raw = llm.chat(messages, json_mode=True)
        except LLMError as exc:
            meta["errors"].append(f"llm: {exc}")
            break
        try:
            data = extract_json(raw)
            result = Classification.model_validate(data)
            meta["repaired"] = meta["repaired"] or was_repaired(raw)
            return result, meta
        except (JsonRepairError, ValidationError, ValueError) as exc:
            err = str(exc).splitlines()[0][:300]
            meta["errors"].append(err)
            meta["repaired"] = True
            messages = [
                *messages,
                {"role": "assistant", "content": raw[:2000]},
                {
                    "role": "user",
                    "content": f"That output was invalid ({err}). Reply with ONLY the JSON "
                    "object, using the allowed values.",
                },
            ]
    meta["fallback"] = True
    return Classification(
        intent=Intent.OTHER,
        urgency="normal",
        sentiment="neutral",
        confidence=0.0,
        rationale="classifier failed; routed to a human",
    ), meta


def build_graph(deps: TriageDeps):
    s = deps.settings

    def normalize(state: TriageState) -> dict:
        n = normalize_ticket(state.get("subject", ""), state["body"][: s.max_ticket_chars])
        return {
            "clean_text": n.clean_text,
            "masked_text": n.masked_text,
            "language": n.language,
            "pii_types": n.pii_types,
            "errors": list(state.get("errors", [])),
        }

    def classify(state: TriageState) -> dict:
        result, meta = classify_with_repair(deps.llm, "", state["masked_text"], s.classify_max_attempts)
        errors = list(state.get("errors", [])) + [f"classify: {e}" for e in meta["errors"] if meta["fallback"]]
        return {"classification": result.model_dump(mode="json"), "classify_meta": meta, "errors": errors}

    def retrieve(state: TriageState) -> dict:
        cls = Classification.model_validate(state["classification"])
        use_filter = cls.intent is not Intent.OTHER and cls.confidence >= s.retrieval_filter_min_confidence
        category = cls.intent.value if use_filter else None
        query = state["masked_text"]
        try:
            chunks = deps.retriever.search(query, category=category, top_k=s.retrieval_top_k)
            if use_filter:
                for extra in cls.secondary_intents:
                    chunks += deps.retriever.search(query, category=extra.value, top_k=2)
                # Some answers live in another category; always mix in the best unfiltered hits.
                chunks += deps.retriever.search(query, category=None, top_k=s.retrieval_unfiltered_mix)
            seen: set[int] = set()
            chunks = [c for c in chunks if not (c.chunk_id in seen or seen.add(c.chunk_id))]
        except Exception as exc:  # a retrieval outage must not drop the ticket
            log.exception("retrieval failed")
            return {"retrieved": [], "errors": [*state.get("errors", []), f"retrieve: {exc}"]}
        return {"retrieved": [c.model_dump() for c in chunks]}

    def draft(state: TriageState) -> dict:
        chunks = [RetrievedChunk.model_validate(c) for c in state.get("retrieved", [])]
        prev = state.get("verification")
        feedback = "; ".join(prev["issues"]) if prev and not prev["passed"] else None
        attempts = state.get("draft_meta", {}).get("attempts", 0) + 1
        cls = state["classification"]
        msgs = draft_messages("", state["masked_text"], cls["intent"], chunks, feedback)
        try:
            raw = deps.llm.chat(msgs, json_mode=True)
            out = DraftOutput.model_validate(extract_json(raw))
        except (LLMError, JsonRepairError, ValidationError) as exc:
            err = str(exc).splitlines()[0][:300]
            return {
                "draft": None,
                "draft_meta": {"attempts": attempts, "error": err},
                "errors": [*state.get("errors", []), f"draft: {err}"],
            }
        return {"draft": out.model_dump(), "draft_meta": {"attempts": attempts}}

    def verify(state: TriageState) -> dict:
        d = state.get("draft")
        if d is None:
            return {"verification": None}
        chunks = [RetrievedChunk.model_validate(c) for c in state.get("retrieved", [])]
        v = verify_draft(
            d["reply"], chunks, needs_escalation=d["needs_escalation"], min_support=s.grounding_min_support
        )
        return {"verification": v.model_dump()}

    def after_verify(state: TriageState) -> str:
        v = state.get("verification")
        d = state.get("draft")
        attempts = state.get("draft_meta", {}).get("attempts", 0)
        if v and not v["passed"] and d and not d["needs_escalation"] and attempts < s.draft_max_attempts:
            return "draft"
        return "route"

    def route_node(state: TriageState) -> dict:
        d = state.get("draft")
        v = state.get("verification")
        decision = route(
            deps.policy,
            Classification.model_validate(state["classification"]),
            classifier_fallback=state["classify_meta"]["fallback"],
            draft=DraftOutput.model_validate(d) if d else None,
            verification=Verification.model_validate(v) if v else None,
            language=state.get("language", "en"),
        )
        update: dict[str, Any] = {"routing": decision.model_dump()}
        if d:
            update["draft"] = {**d, "reply_rendered": render_citations(d["reply"], s.article_url)}
        return update

    g = StateGraph(TriageState)
    g.add_node("normalize", _timed("normalize", normalize))
    g.add_node("classify", _timed("classify", classify))
    g.add_node("retrieve", _timed("retrieve", retrieve))
    g.add_node("draft", _timed("draft", draft))
    g.add_node("verify", _timed("verify", verify))
    g.add_node("route", _timed("route", route_node))
    g.add_edge(START, "normalize")
    g.add_edge("normalize", "classify")
    g.add_edge("classify", "retrieve")
    g.add_edge("retrieve", "draft")
    g.add_edge("draft", "verify")
    g.add_conditional_edges("verify", after_verify, {"draft": "draft", "route": "route"})
    g.add_edge("route", END)
    return g.compile()


def run_triage(graph, subject: str, body: str) -> TriageState:
    return graph.invoke({"subject": subject, "body": body, "errors": [], "timings_ms": {}})
