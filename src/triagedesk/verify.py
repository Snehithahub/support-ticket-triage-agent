"""Draft verification: citations must come from the retrieved set and cited sentences must be
supported by the cited excerpts (lexical overlap plus exact match of every number)."""

from __future__ import annotations

import re
from collections.abc import Callable

from triagedesk.schemas import CitationCheck, RetrievedChunk, Verification
from triagedesk.text import content_tokens, numbers, split_sentences

CITE_RE = re.compile(r"\[([A-Z]{3}-\d{2})\](?:\((https?://[^)\s]+)\))?")
_CITE_GROUP = r"((?:\s*\[[A-Z]{3}-\d{2}\](?:\([^)\s]*\))?)+)"
_MOVE_CITES_RE = re.compile(r"([.!?])" + _CITE_GROUP)
_FACTUAL_RE = re.compile(r"\d|%|\brs\.?\b|\binr\b|business days?|\bfee\b|\bgst\b", re.IGNORECASE)
_IDS_RE = re.compile(r"\b[a-z]+_[A-Za-z0-9_]+\b|\[[A-Z_]+_\d+\]")
_GENERIC = frozenset(
    """northwind pay support reach out writing reply ticket email look into help resolve let know sure
    happy hope sorry hear understand regarding question query concern escalating escalated relevant ids
    details share please team""".split()
)


def _sentences(reply: str) -> list[str]:
    # Move citations that follow a full stop to before it: "days. [REF-02]" -> "days [REF-02]."
    moved = _MOVE_CITES_RE.sub(lambda m: f"{m.group(2)}{m.group(1)}", reply)
    return split_sentences(moved)


def _claim_tokens(sentence: str) -> set[str]:
    s = CITE_RE.sub(" ", _IDS_RE.sub(" ", sentence))
    return {t for t in content_tokens(s) if t not in _GENERIC}


def verify_draft(
    reply: str,
    retrieved: list[RetrievedChunk],
    *,
    needs_escalation: bool = False,
    min_support: float = 0.5,
) -> Verification:
    by_article: dict[str, list[RetrievedChunk]] = {}
    for c in retrieved:
        by_article.setdefault(c.article_id, []).append(c)

    checks: dict[str, CitationCheck] = {}
    fabricated: list[str] = []
    unsupported: list[str] = []
    uncited: list[str] = []
    cited_sentences = 0
    supported_sentences = 0

    for sent in _sentences(reply):
        cites = CITE_RE.findall(sent)
        if not cites:
            body = _IDS_RE.sub(" ", sent)
            if _FACTUAL_RE.search(body):
                uncited.append(sent)
            continue
        cited_sentences += 1
        claim = _claim_tokens(sent)
        claim_nums = numbers(_IDS_RE.sub(" ", CITE_RE.sub(" ", sent)))
        best = 0.0
        nums_ok = not claim_nums
        for aid, url in cites:
            chunks = by_article.get(aid)
            if not chunks:
                if aid not in fabricated:
                    fabricated.append(aid)
                checks[aid] = CitationCheck(
                    article_id=aid, url=url or None, in_retrieved=False, supported=False, support_score=0.0
                )
                continue
            evidence = " ".join(c.heading + " " + c.content for c in chunks)
            ev_tokens = set(content_tokens(evidence))
            score = len(claim & ev_tokens) / len(claim) if claim else 1.0
            nums_here = claim_nums <= numbers(evidence)
            ok = score >= min_support and nums_here
            prev = checks.get(aid)
            checks[aid] = CitationCheck(
                article_id=aid,
                url=url or chunks[0].url,
                in_retrieved=True,
                supported=ok or bool(prev and prev.supported),
                support_score=round(max(score, prev.support_score if prev else 0.0), 3),
            )
            best = max(best, score)
            nums_ok = nums_ok or nums_here
        if best >= min_support and nums_ok:
            supported_sentences += 1
        else:
            unsupported.append(sent)

    issues: list[str] = []
    if fabricated:
        issues.append(f"citations not in retrieved set: {', '.join(fabricated)}")
    if unsupported:
        issues.append(f"{len(unsupported)} cited sentence(s) not supported by the cited article")
    if uncited:
        issues.append(f"{len(uncited)} factual sentence(s) without a citation")
    if cited_sentences == 0 and not needs_escalation:
        issues.append("no citations in a non-escalation reply")

    claims = cited_sentences + len(uncited)
    grounding = supported_sentences / claims if claims else (1.0 if needs_escalation else 0.0)
    return Verification(
        passed=not issues,
        citations=list(checks.values()),
        fabricated=fabricated,
        unsupported_sentences=unsupported,
        uncited_claims=uncited,
        grounding_score=round(grounding, 3),
        issues=issues,
    )


def render_citations(reply: str, url_for: Callable[[str], str]) -> str:
    """Turn bare [ID] citations into markdown links [ID](url) for the customer-facing text."""
    return CITE_RE.sub(lambda m: m.group(0) if m.group(2) else f"[{m.group(1)}]({url_for(m.group(1))})", reply)
