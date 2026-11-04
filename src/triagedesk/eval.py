"""Offline evaluation of TriageDesk against the labelled ticket set (data/eval/tickets.jsonl).

Usage:
    python -m triagedesk.eval --retrieval-only          # no LLM: hit@k / MRR, hybrid vs ablations
    python -m triagedesk.eval [--provider groq] [--limit 40] [--delay 2]

Sections:
  1. Retrieval (no LLM). The ticket text is normalised exactly as the graph does it and sent to
     the real PgHybridRetriever (pgvector + Postgres FTS fused with RRF). Chunks are collapsed to
     a ranked list of unique articles and scored against gold_articles. Ablations: dense-only and
     FTS-only, plus hybrid filtered to the gold intent's category (what the graph sees when the
     classifier is right).
  2. Routing/classification (needs the configured LLM): macro-F1, per-intent precision/recall,
     confusion matrix, citation validity, auto-send precision at confidence thresholds and a
     per-intent "safe to automate" recommendation, plus the auto-resolution rate.
  3. Handling time from recorded human review actions in the database, if there are any.

Results are printed as tables and written to data/eval/results/eval_<timestamp>.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import statistics
import sys
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from triagedesk.config import PROJECT_ROOT, Settings, get_settings
from triagedesk.taxonomy import Intent

log = logging.getLogger(__name__)

DEFAULT_TICKETS = PROJECT_ROOT / "data" / "eval" / "tickets.jsonl"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "eval" / "results"
THRESHOLDS: tuple[float, ...] = (0.6, 0.7, 0.8, 0.9)
HIT_KS: tuple[int, ...] = (1, 3, 5)
MRR_K = 10
FETCH_CHUNKS = 20  # chunks requested per query; at most 2 per article, so >= 10 unique articles
TARGET_PRECISION = 0.95
MIN_SUPPORT = 5
FAKE_LLM_LABEL = "fake LLM, pipeline check only, not a quality measure"
DIFFICULTIES = ("easy", "ambiguous", "multi_intent")


# ---------------------------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalTicket:
    id: str
    subject: str
    body: str
    gold_intent: str
    gold_secondary: tuple[str, ...]
    gold_articles: tuple[str, ...]
    should_automate: bool
    tags: tuple[str, ...] = ()
    merchant_type: str = ""

    @property
    def difficulty(self) -> str:
        return difficulty_of(self.tags)


def difficulty_of(tags: Iterable[str]) -> str:
    """The dataset tags tickets; difficulty is derived: multi_intent > ambiguous > easy."""
    tags = set(tags)
    if "multi_intent" in tags:
        return "multi_intent"
    if "ambiguous" in tags:
        return "ambiguous"
    return "easy"


def load_tickets(path: Path) -> list[EvalTicket]:
    out: list[EvalTicket] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        r = json.loads(line)
        try:
            out.append(
                EvalTicket(
                    id=str(r["id"]),
                    subject=r.get("subject") or "",
                    body=r["body"],
                    gold_intent=Intent(r["gold_intent"]).value,
                    gold_secondary=tuple(Intent(i).value for i in r.get("gold_secondary") or []),
                    gold_articles=tuple(r.get("gold_articles") or []),
                    should_automate=bool(r["should_automate"]),
                    tags=tuple(r.get("tags") or []),
                    merchant_type=r.get("merchant_type") or "",
                )
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{path}:{n}: invalid ticket record: {exc}") from exc
    return out


def dataset_stats(tickets: Sequence[EvalTicket]) -> dict[str, Any]:
    return {
        "tickets": len(tickets),
        "by_intent": dict(sorted(Counter(t.gold_intent for t in tickets).items())),
        "by_difficulty": {d: sum(t.difficulty == d for t in tickets) for d in DIFFICULTIES},
        "hinglish": sum("hinglish" in t.tags for t in tickets),
        "should_automate": sum(t.should_automate for t in tickets),
        "with_gold_articles": sum(bool(t.gold_articles) for t in tickets),
    }


# ---------------------------------------------------------------------------------------------
# Metric functions (pure, unit-tested)
# ---------------------------------------------------------------------------------------------


def unique_in_order(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def hit_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    """1.0 if any gold item is in the top k of the ranking, else 0.0."""
    gold = set(gold)
    return 1.0 if any(r in gold for r in ranked[:k]) else 0.0


def reciprocal_rank(ranked: Sequence[str], gold: Iterable[str], k: int = MRR_K) -> float:
    """1 / rank of the first gold item within the top k (ranks start at 1); 0.0 if absent."""
    gold = set(gold)
    for rank, r in enumerate(ranked[:k], start=1):
        if r in gold:
            return 1.0 / rank
    return 0.0


def recall_at_k(ranked: Sequence[str], gold: Iterable[str], k: int) -> float:
    gold = set(gold)
    return len(gold & set(ranked[:k])) / len(gold) if gold else 0.0


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def per_class_prf(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> dict[str, dict[str, float]]:
    if len(gold) != len(pred):
        raise ValueError("gold and pred must have the same length")
    out: dict[str, dict[str, float]] = {}
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, pred, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, pred, strict=True))
        precision, recall = _safe_div(tp, tp + fp), _safe_div(tp, tp + fn)
        out[label] = {
            "precision": precision,
            "recall": recall,
            "f1": _safe_div(2 * precision * recall, precision + recall),
            "support": tp + fn,
            "predicted": tp + fp,
        }
    return out


def macro_f1(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str] | None = None) -> float:
    """Unweighted mean F1 over labels (default: every label seen in gold or pred)."""
    labels = list(labels) if labels is not None else sorted(set(gold) | set(pred))
    if not labels:
        return 0.0
    prf = per_class_prf(gold, pred, labels)
    return sum(v["f1"] for v in prf.values()) / len(labels)


def confusion_matrix(gold: Sequence[str], pred: Sequence[str], labels: Sequence[str]) -> dict[str, dict[str, int]]:
    """matrix[gold][pred] = count. Labels outside `labels` are counted under their own key."""
    m: dict[str, dict[str, int]] = {g: dict.fromkeys(labels, 0) for g in labels}
    for g, p in zip(gold, pred, strict=True):
        m.setdefault(g, dict.fromkeys(labels, 0))
        m[g][p] = m[g].get(p, 0) + 1
    return m


@dataclass
class RoutedRow:
    """One triaged ticket, reduced to what the auto-send analysis needs.

    auto_by_threshold maps a confidence threshold to whether the ticket would be auto-sent at it.
    correct means "auto-sending this ticket would have been right": the predicted intent equals
    the gold intent and the gold label says the ticket is safe to automate.
    """

    pred_intent: str
    correct: bool
    auto_by_threshold: dict[float, bool] = field(default_factory=dict)


def threshold_table(
    rows: Sequence[RoutedRow], thresholds: Sequence[float] = THRESHOLDS, intent: str | None = None
) -> list[dict[str, Any]]:
    """Auto-send volume and precision at each threshold, optionally for one predicted intent."""
    scoped = [r for r in rows if intent is None or r.pred_intent == intent]
    out = []
    for t in thresholds:
        sent = [r for r in scoped if r.auto_by_threshold.get(t)]
        good = sum(r.correct for r in sent)
        out.append(
            {
                "threshold": t,
                "auto_sent": len(sent),
                "correct": good,
                "precision": round(good / len(sent), 4) if sent else None,
                "auto_rate": round(len(sent) / len(scoped), 4) if scoped else None,
            }
        )
    return out


def recommend(
    table: Sequence[dict[str, Any]],
    risk_class: str,
    *,
    target: float = TARGET_PRECISION,
    min_support: int = MIN_SUPPORT,
) -> str:
    """Per-intent verdict from a threshold table (rows sorted by ascending threshold)."""
    if risk_class != "informational":
        return f"never ({risk_class})"
    for row in table:
        if row["auto_sent"] >= min_support and row["precision"] is not None and row["precision"] >= target:
            return f"auto-send at >= {row['threshold']:.1f}"
    if all(row["auto_sent"] < min_support for row in table):
        return f"insufficient data (< {min_support} auto-sends)"
    return f"human review (precision < {target:.2f})"


# ---------------------------------------------------------------------------------------------
# Retrieval evaluation (no LLM)
# ---------------------------------------------------------------------------------------------


def ticket_query(t: EvalTicket) -> str:
    """The exact text the graph's retrieve node searches with."""
    from triagedesk.normalize import normalize_ticket

    return normalize_ticket(t.subject, t.body).masked_text


def _score_rankings(rankings: dict[str, list[str]], tickets: Sequence[EvalTicket]) -> dict[str, Any]:
    by_id = {t.id: t for t in tickets}

    def agg(ids: list[str]) -> dict[str, Any]:
        n = len(ids)
        res: dict[str, Any] = {"n": n}
        for k in HIT_KS:
            res[f"hit@{k}"] = round(_safe_div(sum(hit_at_k(rankings[i], by_id[i].gold_articles, k) for i in ids), n), 4)
        res[f"mrr@{MRR_K}"] = round(
            _safe_div(sum(reciprocal_rank(rankings[i], by_id[i].gold_articles) for i in ids), n), 4
        )
        res["recall@5"] = round(_safe_div(sum(recall_at_k(rankings[i], by_id[i].gold_articles, 5) for i in ids), n), 4)
        return res

    ids = list(rankings)
    out = agg(ids)
    out["by_difficulty"] = {d: agg([i for i in ids if by_id[i].difficulty == d]) for d in DIFFICULTIES}
    out["by_intent"] = {
        intent: agg([i for i in ids if by_id[i].gold_intent == intent])
        for intent in sorted({by_id[i].gold_intent for i in ids})
    }
    return out


def evaluate_retrieval(
    retriever,
    tickets: Sequence[EvalTicket],
    *,
    modes: Sequence[str] = ("hybrid", "vector", "fts"),
    gold_category_filter: bool = True,
) -> dict[str, Any]:
    """Score each retrieval mode. Tickets without gold articles (intent 'other') are skipped."""
    scored = [t for t in tickets if t.gold_articles]
    variants: list[tuple[str, str, bool]] = [(m, m, False) for m in modes]
    if gold_category_filter:
        variants.append(("hybrid+gold_intent_filter", "hybrid", True))
    queries = {t.id: ticket_query(t) for t in scored}
    results: dict[str, Any] = {}
    misses: list[dict[str, Any]] = []
    for name, mode, filtered in variants:
        rankings: dict[str, list[str]] = {}
        latencies: list[float] = []
        for t in scored:
            t0 = time.perf_counter()
            chunks = retriever.search(
                queries[t.id], category=t.gold_intent if filtered else None, top_k=FETCH_CHUNKS, mode=mode
            )
            latencies.append((time.perf_counter() - t0) * 1000)
            rankings[t.id] = unique_in_order(c.article_id for c in chunks)
        res = _score_rankings(rankings, scored)
        res["latency_ms_p50"] = round(statistics.median(latencies), 1) if latencies else None
        results[name] = res
        if name == "hybrid":
            misses = [
                {"id": t.id, "gold": list(t.gold_articles), "top3": rankings[t.id][:3]}
                for t in scored
                if not hit_at_k(rankings[t.id], t.gold_articles, 3)
            ]
    return {
        "scored_tickets": len(scored),
        "skipped_no_gold": len(tickets) - len(scored),
        "fetch_chunks": FETCH_CHUNKS,
        "modes": results,
        "hybrid_misses_at_3": misses,
    }


# ---------------------------------------------------------------------------------------------
# Pipeline (classification + routing) evaluation
# ---------------------------------------------------------------------------------------------


def _reroute(policy, state: dict[str, Any], threshold: float | None, ignore_risk_class: bool) -> str:
    from triagedesk.policy import route
    from triagedesk.schemas import Classification, DraftOutput, Verification

    d, v = state.get("draft"), state.get("verification")
    return route(
        policy,
        Classification.model_validate(state["classification"]),
        classifier_fallback=state["classify_meta"]["fallback"],
        draft=DraftOutput.model_validate(d) if d else None,
        verification=Verification.model_validate(v) if v else None,
        language=state.get("language", "en"),
        min_confidence_override=threshold,
        ignore_risk_class=ignore_risk_class,
    ).decision


def triage_record(
    t: EvalTicket, state: dict[str, Any], policy, thresholds: Sequence[float] = THRESHOLDS
) -> dict[str, Any]:
    cls = state["classification"]
    draft, ver = state.get("draft"), state.get("verification")
    return {
        "id": t.id,
        "difficulty": t.difficulty,
        "gold_intent": t.gold_intent,
        "gold_secondary": list(t.gold_secondary),
        "gold_articles": list(t.gold_articles),
        "should_automate": t.should_automate,
        "pred_intent": cls["intent"],
        "pred_secondary": cls["secondary_intents"],
        "confidence": cls["confidence"],
        "urgency": cls["urgency"],
        "sentiment": cls["sentiment"],
        "classifier_fallback": state["classify_meta"]["fallback"],
        "retrieved_articles": unique_in_order(c["article_id"] for c in state.get("retrieved", [])),
        "has_draft": draft is not None,
        "needs_escalation": bool(draft and draft["needs_escalation"]),
        "verified": bool(ver and ver["passed"]),
        "citations": [
            {k: c[k] for k in ("article_id", "in_retrieved", "supported")} for c in (ver or {}).get("citations", [])
        ],
        "decision": state["routing"]["decision"],
        "auto_policy": {str(th): _reroute(policy, state, th, False) == "auto_send" for th in thresholds},
        "auto_whatif": {str(th): _reroute(policy, state, th, True) == "auto_send" for th in thresholds},
        "errors": state.get("errors", []),
    }


def summarize_pipeline(
    records: Sequence[dict[str, Any]], policy, *, demo: bool, thresholds: Sequence[float] = THRESHOLDS
) -> dict[str, Any]:
    ok = [r for r in records if "pred_intent" in r]
    labels = [i.value for i in Intent]
    gold = [r["gold_intent"] for r in ok]
    pred = [r["pred_intent"] for r in ok]
    prf = per_class_prf(gold, pred, labels)
    seen = sorted(set(gold) | set(pred))

    cites = [c for r in ok for c in r["citations"]]
    answerable = [r for r in ok if r["gold_articles"] and r["has_draft"] and not r["needs_escalation"]]
    multi = [r for r in ok if r["difficulty"] == "multi_intent"]

    def rows(key: str) -> list[RoutedRow]:
        return [
            RoutedRow(
                r["pred_intent"],
                r["pred_intent"] == r["gold_intent"] and r["should_automate"],
                {th: r[key][str(th)] for th in thresholds},
            )
            for r in ok
        ]

    policy_rows, whatif_rows = rows("auto_policy"), rows("auto_whatif")
    per_intent = []
    for intent in labels:
        p = policy.for_intent(intent)
        table = threshold_table(whatif_rows, thresholds, intent=intent)
        per_intent.append(
            {
                "intent": intent,
                "risk_class": p.risk_class,
                "policy_auto_send": p.auto_send,
                "policy_min_confidence": p.min_confidence,
                "predicted": sum(x == intent for x in pred),
                "whatif_thresholds": table,
                "recommendation": recommend(table, p.risk_class),
            }
        )

    auto = [r for r in ok if r["decision"] == "auto_send"]
    should = [r for r in ok if r["should_automate"]]
    auto_correct = [r for r in auto if r["should_automate"] and r["pred_intent"] == r["gold_intent"]]
    return {
        "label": FAKE_LLM_LABEL if demo else "live LLM",
        "tickets": len(records),
        "errors": len(records) - len(ok),
        "classifier_fallbacks": sum(r["classifier_fallback"] for r in ok),
        "accuracy": round(_safe_div(sum(g == p for g, p in zip(gold, pred, strict=True)), len(ok)), 4),
        "macro_f1": round(macro_f1(gold, pred, seen), 4),
        "accuracy_by_difficulty": {
            d: round(
                _safe_div(
                    sum(r["gold_intent"] == r["pred_intent"] for r in ok if r["difficulty"] == d),
                    sum(r["difficulty"] == d for r in ok),
                ),
                4,
            )
            for d in DIFFICULTIES
        },
        "per_intent": {
            k: {m: round(v, 4) if isinstance(v, float) else v for m, v in d.items()} for k, d in prf.items()
        },
        "confusion_matrix": confusion_matrix(gold, pred, labels),
        "multi_intent": {
            "tickets": len(multi),
            "secondary_flagged": sum(bool(r["pred_secondary"]) for r in multi),
            "all_gold_intents_covered": sum(
                {r["gold_intent"], *r["gold_secondary"]} <= {r["pred_intent"], *r["pred_secondary"]} for r in multi
            ),
        },
        "citations": {
            "total": len(cites),
            "validity_rate": round(_safe_div(sum(c["in_retrieved"] for c in cites), len(cites)), 4),
            "supported_rate": round(_safe_div(sum(c["supported"] for c in cites), len(cites)), 4),
            "drafts": sum(r["has_draft"] for r in ok),
            "drafts_verified": sum(r["verified"] for r in ok),
            "gold_article_cited_rate": round(
                _safe_div(
                    sum(bool({c["article_id"] for c in r["citations"]} & set(r["gold_articles"])) for r in answerable),
                    len(answerable),
                ),
                4,
            ),
        },
        "routing": {
            "decisions": dict(Counter(r["decision"] for r in ok)),
            "auto_resolution_rate": round(_safe_div(len(auto), len(ok)), 4),
            "auto_send_precision": round(len(auto_correct) / len(auto), 4) if auto else None,
            "auto_send_recall": round(_safe_div(len(auto_correct), len(should)), 4),
            "unsafe_auto_sends": [r["id"] for r in auto if r not in auto_correct],
        },
        "policy_thresholds": threshold_table(policy_rows, thresholds),
        "whatif_thresholds_ignore_risk_class": threshold_table(whatif_rows, thresholds),
        "per_intent_automation": per_intent,
    }


def evaluate_pipeline(
    graph, policy, tickets: Sequence[EvalTicket], *, demo: bool, delay_s: float = 0.0, progress: bool = False
) -> dict[str, Any]:
    from triagedesk.graph import run_triage

    records: list[dict[str, Any]] = []
    latencies: list[float] = []
    for n, t in enumerate(tickets, start=1):
        t0 = time.perf_counter()
        try:
            state = run_triage(graph, t.subject, t.body)
            records.append(triage_record(t, state, policy))
        except Exception as exc:  # one bad ticket must not abort the run
            log.exception("triage failed", extra={"ticket": t.id})
            records.append({"id": t.id, "error": str(exc)[:300]})
        latencies.append((time.perf_counter() - t0) * 1000)
        if progress:
            print(f"\r  triaged {n}/{len(tickets)}", end="", file=sys.stderr, flush=True)
        if delay_s and n < len(tickets):
            time.sleep(delay_s)
    if progress:
        print(file=sys.stderr)
    summary = summarize_pipeline(records, policy, demo=demo)
    summary["latency_ms_p50"] = round(statistics.median(latencies), 1) if latencies else None
    summary["records"] = records
    return summary


# ---------------------------------------------------------------------------------------------
# Handling time (recorded reviews)
# ---------------------------------------------------------------------------------------------


def handling_time(database_url: str) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    try:
        with psycopg.connect(database_url, connect_timeout=5, row_factory=dict_row) as conn:
            rows = conn.execute(
                """SELECT action, count(*) AS n,
                          count(handling_seconds) AS timed,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY handling_seconds) AS median_s,
                          percentile_cont(0.9) WITHIN GROUP (ORDER BY handling_seconds) AS p90_s,
                          avg(edit_ratio) AS mean_edit_ratio
                   FROM review_actions GROUP BY action ORDER BY action"""
            ).fetchall()
    except Exception as exc:  # noqa: BLE001 - report "no review data" on any DB failure
        return {"status": "no review data", "detail": f"database unavailable: {str(exc)[:200]}"}
    if not rows or sum(r["timed"] for r in rows) == 0:
        return {"status": "no review data", "reviews": sum(r["n"] for r in rows)}
    return {
        "status": "ok",
        "source": "review_actions (real reviews recorded through the API)",
        "by_action": [
            {k: (round(float(v), 3) if isinstance(v, float) or hasattr(v, "is_finite") else v) for k, v in r.items()}
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------------------------


def format_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    def cell(v: Any) -> str:
        if v is None:
            return "-"
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v)

    data = [[cell(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in data)) if data else len(h) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(w) for h, w in zip(headers, widths, strict=True))
    sep = "  ".join("-" * w for w in widths)
    body = ["  ".join(c.ljust(w) for c, w in zip(r, widths, strict=True)) for r in data]
    return "\n".join([line, sep, *body])


def print_report(report: dict[str, Any]) -> None:
    ds = report["dataset"]
    print(f"\nDataset: {ds['tickets']} tickets  difficulty={ds['by_difficulty']}  hinglish={ds['hinglish']}")
    ret = report.get("retrieval")
    if ret:
        if "error" in ret:
            print(f"\nRetrieval: {ret['error']}")
        else:
            print(
                f"\nRetrieval (no LLM; {ret['scored_tickets']} tickets with gold articles, "
                f"{ret['skipped_no_gold']} 'other' tickets skipped; ranking = unique articles)"
            )
            keys = [f"hit@{k}" for k in HIT_KS] + [f"mrr@{MRR_K}", "recall@5", "latency_ms_p50"]
            print(format_table(["mode", *keys], [[m, *(r[k] for k in keys)] for m, r in ret["modes"].items()]))
            h = ret["modes"]["hybrid"]["by_difficulty"]
            print("\nHybrid by difficulty")
            print(
                format_table(
                    ["difficulty", "n", "hit@1", "hit@3", "hit@5", f"mrr@{MRR_K}"],
                    [[d, v["n"], v["hit@1"], v["hit@3"], v["hit@5"], v[f"mrr@{MRR_K}"]] for d, v in h.items()],
                )
            )
            hi = ret["modes"]["hybrid"]["by_intent"]
            print("\nHybrid by gold intent")
            print(
                format_table(
                    ["intent", "n", "hit@1", "hit@3", "hit@5", f"mrr@{MRR_K}"],
                    [[i, v["n"], v["hit@1"], v["hit@3"], v["hit@5"], v[f"mrr@{MRR_K}"]] for i, v in hi.items()],
                )
            )
    pipe = report.get("pipeline")
    if pipe:
        if "error" in pipe:
            print(f"\nRouting/classification: {pipe['error']}")
        else:
            label = pipe["label"].upper() if pipe["label"] == FAKE_LLM_LABEL else pipe["label"]
            print(
                f"\nRouting/classification [{label}] provider={report['meta']['llm_provider']} "
                f"model={report['meta']['llm_model']} retriever={report['meta'].get('pipeline_retriever')}"
            )
            print(
                f"tickets={pipe['tickets']} errors={pipe['errors']} fallbacks={pipe['classifier_fallbacks']} "
                f"accuracy={pipe['accuracy']:.3f} macro_f1={pipe['macro_f1']:.3f} "
                f"by_difficulty={pipe['accuracy_by_difficulty']}"
            )
            print(
                format_table(
                    ["intent", "precision", "recall", "f1", "support", "predicted"],
                    [
                        [k, v["precision"], v["recall"], v["f1"], v["support"], v["predicted"]]
                        for k, v in pipe["per_intent"].items()
                    ],
                )
            )
            labels = list(pipe["confusion_matrix"])
            short = [lbl[:6] for lbl in labels]
            print("\nConfusion matrix (rows = gold, columns = predicted)")
            print(
                format_table(
                    ["gold \\ pred", *short],
                    [[g, *(pipe["confusion_matrix"][g].get(p, 0) for p in labels)] for g in labels],
                )
            )
            c, r = pipe["citations"], pipe["routing"]
            print(
                f"\nCitations: total={c['total']} validity={c['validity_rate']:.3f} "
                f"supported={c['supported_rate']:.3f} drafts_verified={c['drafts_verified']}/{c['drafts']} "
                f"gold_article_cited={c['gold_article_cited_rate']:.3f}"
            )
            print(
                f"Routing: {r['decisions']} auto_resolution_rate={r['auto_resolution_rate']:.3f} "
                f"auto_send_precision={r['auto_send_precision']} auto_send_recall={r['auto_send_recall']:.3f}"
            )
            print(f"Multi-intent: {pipe['multi_intent']}")
            print("\nAuto-send at confidence thresholds (configured policy, risk classes respected)")
            print(
                format_table(
                    ["threshold", "auto_sent", "correct", "precision", "auto_rate"],
                    [
                        [x["threshold"], x["auto_sent"], x["correct"], x["precision"], x["auto_rate"]]
                        for x in pipe["policy_thresholds"]
                    ],
                )
            )
            print("\nPer-intent safe-to-automate (what-if: risk class ignored, precision of auto-sends)")
            rows = []
            for x in pipe["per_intent_automation"]:
                prec = [
                    f"{'-' if t['precision'] is None else format(t['precision'], '.2f')}/{t['auto_sent']}"
                    for t in x["whatif_thresholds"]
                ]
                rows.append(
                    [
                        x["intent"],
                        x["risk_class"],
                        "yes" if x["policy_auto_send"] else "no",
                        x["policy_min_confidence"],
                        *prec,
                        x["recommendation"],
                    ]
                )
            print(
                format_table(
                    [
                        "intent",
                        "risk_class",
                        "policy_auto",
                        "policy_min",
                        *(f"p/n@{t}" for t in THRESHOLDS),
                        "recommendation",
                    ],
                    rows,
                )
            )
    ht = report.get("handling_time")
    if ht:
        if ht["status"] != "ok":
            print(f"\nHandling time: no review data{(' (' + ht['detail'] + ')') if 'detail' in ht else ''}")
        else:
            print("\nHandling time (" + ht["source"] + ")")
            print(
                format_table(
                    ["action", "n", "timed", "median_s", "p90_s", "mean_edit_ratio"],
                    [
                        [x["action"], x["n"], x["timed"], x["median_s"], x["p90_s"], x["mean_edit_ratio"]]
                        for x in ht["by_action"]
                    ],
                )
            )


def write_report(report: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    kind = "retrieval" if report["meta"]["retrieval_only"] else "full"
    path = out_dir / f"eval_{kind}_{stamp}.json"
    text = json.dumps(report, indent=2, default=str)
    path.write_text(text, encoding="utf-8")
    (out_dir / f"latest_{kind}.json").write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def _in_memory_retriever(settings: Settings, embedder):
    from triagedesk.chunking import chunk_article, load_articles
    from triagedesk.retrieval import InMemoryHybridRetriever

    articles = load_articles(settings.kb_dir)
    chunks = [c for a in articles for c in chunk_article(a)]
    return InMemoryHybridRetriever(
        articles, chunks, embedder, settings.article_url, candidates=settings.retrieval_candidates, rrf_k=settings.rrf_k
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m triagedesk.eval", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--retrieval-only", action="store_true", help="skip the LLM sections")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N tickets")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["fake", "gemini", "groq", "openai", "azure", "custom"],
        help="override LLM_PROVIDER for this run",
    )
    parser.add_argument("--tickets", type=Path, default=DEFAULT_TICKETS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to sleep between tickets (rate limits)")
    args = parser.parse_args(argv)

    from triagedesk.logging_setup import configure_logging

    settings = Settings(llm_provider=args.provider) if args.provider else get_settings()
    configure_logging("WARNING", json_logs=False)

    tickets = load_tickets(args.tickets)
    if args.limit:
        tickets = tickets[: args.limit]
    report: dict[str, Any] = {
        "meta": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "tickets_file": str(args.tickets),
            "tickets_sha256": hashlib.sha256(args.tickets.read_bytes()).hexdigest()[:16],
            "limit": args.limit,
            "retrieval_only": args.retrieval_only,
            "embedder": f"{settings.embeddings_provider}:{settings.embeddings_model}",
            "retrieval_candidates": settings.retrieval_candidates,
            "rrf_k": settings.rrf_k,
        },
        "dataset": dataset_stats(tickets),
    }

    from triagedesk.embeddings import build_embedder

    embedder = build_embedder(settings)
    pool = None
    try:
        from triagedesk.db import make_pool

        pool = make_pool(settings.database_url, max_size=2, open_timeout=10)
        with pool.connection() as conn:
            n_chunks = conn.execute("SELECT count(*) AS n FROM kb_chunks").fetchone()["n"]
        if n_chunks == 0:
            raise RuntimeError("kb_chunks is empty; run `python -m triagedesk.ingest` first")
        report["meta"]["kb_chunks"] = n_chunks
    except Exception as exc:  # noqa: BLE001 - recorded in the report
        if pool is not None:
            pool.close()
        pool = None
        report["retrieval"] = {"error": f"Postgres retrieval unavailable: {str(exc)[:300]}"}

    try:
        if pool is not None:
            from triagedesk.retrieval import PgHybridRetriever

            retriever = PgHybridRetriever(
                pool, embedder, candidates=settings.retrieval_candidates, rrf_k=settings.rrf_k
            )
            report["retrieval"] = evaluate_retrieval(retriever, tickets)
        if not args.retrieval_only:
            from triagedesk.graph import TriageDeps, build_graph
            from triagedesk.llm import build_llm
            from triagedesk.policy import AutomationPolicy

            llm = build_llm(settings)
            policy = AutomationPolicy.load(settings.policy_path)
            if pool is not None:
                pipe_retriever, kind = retriever, "postgres-hybrid"
            else:
                pipe_retriever, kind = _in_memory_retriever(settings, embedder), "in-memory-hybrid (no database)"
            report["meta"].update(
                llm_provider=settings.llm_provider,
                llm_model=llm.model,
                pipeline_retriever=kind,
                policy_version=policy.version,
            )
            graph = build_graph(TriageDeps(llm, pipe_retriever, policy, settings))
            report["pipeline"] = evaluate_pipeline(
                graph, policy, tickets, demo=llm.demo, delay_s=args.delay, progress=True
            )
        report["handling_time"] = handling_time(settings.database_url)
    finally:
        if pool is not None:
            pool.close()

    print_report(report)
    path = write_report(report, args.out_dir)
    print(f"\nWrote {path}")
    ret = report.get("retrieval", {})
    return 1 if "error" in ret and args.retrieval_only else 0


if __name__ == "__main__":
    sys.exit(main())
