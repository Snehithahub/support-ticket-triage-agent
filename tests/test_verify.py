from triagedesk.schemas import RetrievedChunk
from triagedesk.verify import render_citations, verify_draft


def chunk(aid: str, content: str, cid: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        article_id=aid,
        title=aid,
        url=f"http://kb/{aid}",
        heading=aid,
        category="refunds",
        content=content,
        score=0.1,
    )


CHUNKS = [
    chunk("REF-02", "Refunds to cards take 5-7 business days. UPI refunds take 2-3 business days.", 1),
    chunk("REF-04", "Instant refunds are credited within 30 minutes for a fee of 0.5% plus GST.", 2),
]


def test_valid_grounded_draft_passes():
    reply = (
        "Hi,\n\nRefunds to cards take 5-7 business days. [REF-02] Instant refunds are credited within "
        "30 minutes [REF-04].\n\nNorthwind Pay Support"
    )
    v = verify_draft(reply, CHUNKS)
    assert v.passed, v.issues
    assert v.grounding_score == 1.0
    assert {c.article_id for c in v.citations} == {"REF-02", "REF-04"}


def test_fabricated_citation_rejected():
    reply = "Refunds to cards take 5-7 business days. [REF-99]"
    v = verify_draft(reply, CHUNKS)
    assert not v.passed
    assert v.fabricated == ["REF-99"]
    assert any("not in retrieved set" in i for i in v.issues)
    assert not next(c for c in v.citations if c.article_id == "REF-99").in_retrieved


def test_real_article_not_in_retrieved_set_is_also_rejected():
    v = verify_draft("Disputes need evidence within 7 days. [DSP-02]", CHUNKS)
    assert not v.passed and v.fabricated == ["DSP-02"]


def test_wrong_number_with_valid_citation_is_unsupported():
    v = verify_draft("Refunds to cards take 10 business days. [REF-02]", CHUNKS)
    assert not v.passed
    assert v.unsupported_sentences


def test_citing_the_wrong_article_is_unsupported():
    v = verify_draft("Instant refunds are credited within 30 minutes for a fee. [REF-02]", CHUNKS)
    assert not v.passed


def test_uncited_factual_claim_flagged_but_ids_ignored():
    v = verify_draft("Your refund rfnd_ABC123 will arrive in 3 days.", CHUNKS)
    assert not v.passed and v.uncited_claims
    ok = verify_draft("We checked rfnd_ABC123. Refunds to cards take 5-7 business days. [REF-02]", CHUNKS)
    assert ok.passed, ok.issues


def test_escalation_reply_without_citations_passes():
    v = verify_draft("We are escalating your ticket to the right team.", CHUNKS, needs_escalation=True)
    assert v.passed
    v2 = verify_draft("We are escalating your ticket to the right team.", CHUNKS)
    assert not v2.passed and "no citations" in v2.issues[0]


def test_markdown_link_citations_and_rendering():
    rendered = render_citations("Cards take 5-7 business days. [REF-02]", lambda a: f"http://kb/{a}")
    assert rendered.endswith("[REF-02](http://kb/REF-02)")
    assert render_citations(rendered, lambda a: "x") == rendered  # idempotent
    assert verify_draft(rendered, CHUNKS).passed
