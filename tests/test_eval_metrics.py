"""Unit tests for the evaluation metric functions (tiny hand-computed fixtures, offline)."""

from __future__ import annotations

import pytest

from triagedesk.eval import (
    RoutedRow,
    confusion_matrix,
    difficulty_of,
    format_table,
    hit_at_k,
    macro_f1,
    per_class_prf,
    recall_at_k,
    reciprocal_rank,
    recommend,
    threshold_table,
    unique_in_order,
)

RANKED = ["REF-02", "REF-03", "PAY-01", "SET-01", "REF-05"]


@pytest.mark.parametrize(
    ("gold", "k", "expected"),
    [
        (["REF-02"], 1, 1.0),
        (["REF-03"], 1, 0.0),
        (["REF-03"], 3, 1.0),
        (["REF-05"], 3, 0.0),
        (["REF-05"], 5, 1.0),
        (["XXX-01", "PAY-01"], 3, 1.0),  # any gold article counts
        (["XXX-01"], 5, 0.0),
        ([], 5, 0.0),
    ],
)
def test_hit_at_k(gold, k, expected):
    assert hit_at_k(RANKED, gold, k) == expected


def test_hit_at_k_shorter_ranking_than_k():
    assert hit_at_k(["A"], ["A"], 5) == 1.0
    assert hit_at_k([], ["A"], 5) == 0.0


@pytest.mark.parametrize(
    ("gold", "expected"),
    [
        (["REF-02"], 1.0),
        (["REF-03"], 0.5),
        (["PAY-01", "REF-05"], 1 / 3),  # first gold hit wins
        (["SET-01"], 0.25),
        (["NOPE-1"], 0.0),
    ],
)
def test_reciprocal_rank(gold, expected):
    assert reciprocal_rank(RANKED, gold) == pytest.approx(expected)


def test_reciprocal_rank_respects_cutoff():
    assert reciprocal_rank(RANKED, ["REF-05"], k=4) == 0.0
    assert reciprocal_rank(RANKED, ["REF-05"], k=5) == pytest.approx(0.2)


def test_mean_reciprocal_rank_over_queries():
    queries = [(["a", "b"], ["a"]), (["a", "b"], ["b"]), (["a", "b"], ["c"])]
    mrr = sum(reciprocal_rank(r, g) for r, g in queries) / len(queries)
    assert mrr == pytest.approx((1 + 0.5 + 0) / 3)


def test_recall_at_k():
    assert recall_at_k(RANKED, ["REF-02", "SET-01"], 3) == 0.5
    assert recall_at_k(RANKED, ["REF-02", "SET-01"], 4) == 1.0
    assert recall_at_k(RANKED, [], 3) == 0.0


def test_unique_in_order_collapses_chunks_to_articles():
    assert unique_in_order(["A", "A", "B", "A", "C", "B"]) == ["A", "B", "C"]


def test_per_class_prf_hand_computed():
    gold = ["a", "a", "a", "b", "b", "c"]
    pred = ["a", "a", "b", "b", "c", "c"]
    prf = per_class_prf(gold, pred, ["a", "b", "c"])
    # a: tp=2 fp=0 fn=1 ; b: tp=1 fp=1 fn=1 ; c: tp=1 fp=1 fn=0
    assert prf["a"]["precision"] == 1.0 and prf["a"]["recall"] == pytest.approx(2 / 3)
    assert prf["a"]["f1"] == pytest.approx(0.8)
    assert prf["b"]["precision"] == 0.5 and prf["b"]["recall"] == 0.5 and prf["b"]["f1"] == 0.5
    assert prf["c"]["precision"] == 0.5 and prf["c"]["recall"] == 1.0
    assert prf["c"]["f1"] == pytest.approx(2 / 3)
    assert prf["a"]["support"] == 3 and prf["c"]["predicted"] == 2


def test_macro_f1_is_unweighted_mean():
    gold = ["a", "a", "a", "b", "b", "c"]
    pred = ["a", "a", "b", "b", "c", "c"]
    assert macro_f1(gold, pred) == pytest.approx((0.8 + 0.5 + 2 / 3) / 3)


def test_macro_f1_perfect_and_label_never_predicted():
    assert macro_f1(["x", "y"], ["x", "y"]) == 1.0
    # 'b' is never predicted: its F1 is 0 and it still counts in the mean.
    assert macro_f1(["a", "b"], ["a", "a"]) == pytest.approx((2 / 3 + 0.0) / 2)
    assert macro_f1([], []) == 0.0


def test_per_class_prf_length_mismatch():
    with pytest.raises(ValueError):
        per_class_prf(["a"], ["a", "b"], ["a", "b"])


def test_confusion_matrix_rows_are_gold():
    m = confusion_matrix(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert m == {"a": {"a": 1, "b": 1}, "b": {"a": 0, "b": 1}}
    assert sum(sum(r.values()) for r in m.values()) == 3


def _rows() -> list[RoutedRow]:
    # Ticket i is auto-sent at every threshold <= its confidence.
    def r(intent: str, conf: float, correct: bool) -> RoutedRow:
        return RoutedRow(intent, correct, {t: conf >= t for t in (0.6, 0.7, 0.8, 0.9)})

    return [
        r("billing", 0.95, True),
        r("billing", 0.85, True),
        r("billing", 0.75, False),
        r("billing", 0.65, False),
        r("checkout", 0.95, True),
        r("checkout", 0.5, True),
    ]


def test_threshold_table_overall():
    table = threshold_table(_rows())
    by_t = {row["threshold"]: row for row in table}
    assert by_t[0.6]["auto_sent"] == 5 and by_t[0.6]["correct"] == 3
    assert by_t[0.6]["precision"] == pytest.approx(0.6)
    assert by_t[0.7]["auto_sent"] == 4 and by_t[0.7]["precision"] == pytest.approx(0.75)
    assert by_t[0.8]["precision"] == 1.0 and by_t[0.9]["auto_sent"] == 2
    assert by_t[0.6]["auto_rate"] == pytest.approx(5 / 6, abs=1e-4)


def test_threshold_table_per_intent_and_empty():
    table = threshold_table(_rows(), intent="billing")
    assert [row["auto_sent"] for row in table] == [4, 3, 2, 1]
    assert [row["precision"] for row in table] == [0.5, pytest.approx(2 / 3, abs=1e-4), 1.0, 1.0]
    empty = threshold_table(_rows(), intent="kyc")
    assert all(row["auto_sent"] == 0 and row["precision"] is None for row in empty)


def test_recommend():
    table = threshold_table(_rows(), intent="billing")
    assert recommend(table, "informational", target=0.95, min_support=2) == "auto-send at >= 0.8"
    assert recommend(table, "informational", target=0.95, min_support=3).startswith("human review")
    assert recommend(table, "informational", min_support=10).startswith("insufficient data")
    assert recommend(table, "money_movement") == "never (money_movement)"
    assert recommend(table, "regulated") == "never (regulated)"


def test_difficulty_of():
    assert difficulty_of([]) == "easy"
    assert difficulty_of(["hinglish", "ambiguous"]) == "ambiguous"
    assert difficulty_of(["ambiguous", "multi_intent"]) == "multi_intent"


def test_format_table_aligns_and_renders_none():
    out = format_table(["mode", "hit@1"], [["hybrid", 0.5], ["fts", None]]).splitlines()
    assert out[0].startswith("mode") and "0.500" in out[2] and out[3].rstrip().endswith("-")
    col = out[0].index("hit@1")
    assert out[2][col:].startswith("0.500") and out[3][col:].startswith("-")
