import pytest

from triagedesk.retrieval import rrf_fuse


def test_rrf_scores_and_order():
    fused = rrf_fuse([[1, 2, 3], [3, 1, 4]], k=60)
    scores = dict(fused)
    assert scores[1] == pytest.approx(1 / 61 + 1 / 62)
    assert scores[3] == pytest.approx(1 / 63 + 1 / 61)
    assert scores[4] == pytest.approx(1 / 63)
    assert [d for d, _ in fused][:2] == [1, 3]  # appears high in both lists


def test_rrf_single_list_preserves_order_and_ties_break_by_id():
    assert [d for d, _ in rrf_fuse([[5, 2, 9]])] == [5, 2, 9]
    assert [d for d, _ in rrf_fuse([[7], [3]])] == [3, 7]
    assert rrf_fuse([]) == []


@pytest.mark.parametrize(
    "query,category,expected",
    [
        ("webhook signature does not match X-Northwind-Signature HMAC", "webhooks", "WHK-02"),
        ("how long do refunds take to reach a UPI customer", "refunds", "REF-02"),
        ("payout reversed, beneficiary bank returned money", "payouts", "PYO-02"),
        ("settlement amount lower than expected MDR GST deducted", None, "SET-06"),
    ],
)
def test_hybrid_finds_gold_article(retriever, query, category, expected):
    hits = retriever.search(query, category=category, top_k=5)
    assert expected in [h.article_id for h in hits]


def test_category_filter_restricts_results(retriever):
    hits = retriever.search("refund failed", category="payouts", top_k=5)
    assert hits and all(h.category == "payouts" for h in hits)


def test_dedupes_chunks_per_article(retriever):
    hits = retriever.search("webhook retries signature events setup", top_k=5)
    ids = [h.article_id for h in hits]
    assert all(ids.count(a) <= 2 for a in ids)


def test_modes(retriever):
    v = retriever.search("chargeback evidence deadline", mode="vector", top_k=3)
    f = retriever.search("chargeback evidence deadline", mode="fts", top_k=3)
    assert all(h.fts_rank is None or h.vector_rank for h in v)
    assert v and f
