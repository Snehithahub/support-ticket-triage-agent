"""End-to-end eval plumbing, offline: in-memory retrieval with the hashing embedder and the fake LLM."""

from __future__ import annotations

import json

import pytest

from triagedesk.chunking import chunk_article, load_articles
from triagedesk.config import PROJECT_ROOT, Settings
from triagedesk.embeddings import HashEmbedder
from triagedesk.eval import (
    DEFAULT_TICKETS,
    FAKE_LLM_LABEL,
    THRESHOLDS,
    dataset_stats,
    evaluate_pipeline,
    evaluate_retrieval,
    load_tickets,
    print_report,
    write_report,
)
from triagedesk.fake_llm import FakeLLM
from triagedesk.graph import TriageDeps, build_graph
from triagedesk.policy import AutomationPolicy
from triagedesk.retrieval import InMemoryHybridRetriever


@pytest.fixture(scope="module")
def settings():
    return Settings(llm_provider="fake", embeddings_provider="hash", _env_file=None)


@pytest.fixture(scope="module")
def retriever(settings):
    articles = load_articles(PROJECT_ROOT / "kb" / "articles")
    chunks = [c for a in articles for c in chunk_article(a)]
    return InMemoryHybridRetriever(articles, chunks, HashEmbedder(384), settings.article_url)


@pytest.fixture(scope="module")
def sample():
    tickets = load_tickets(DEFAULT_TICKETS)
    # A few of each difficulty plus an 'other' ticket (no gold articles).
    picked = [t for t in tickets if t.difficulty == "easy"][:6]
    picked += [t for t in tickets if t.difficulty == "ambiguous"][:2]
    picked += [t for t in tickets if t.difficulty == "multi_intent"][:2]
    picked += [t for t in tickets if t.gold_intent == "other"][:1]
    return picked


def test_evaluate_retrieval_structure(retriever, sample):
    res = evaluate_retrieval(retriever, sample)
    assert res["skipped_no_gold"] == 1
    assert res["scored_tickets"] == len(sample) - 1
    assert set(res["modes"]) == {"hybrid", "vector", "fts", "hybrid+gold_intent_filter"}
    for mode in res["modes"].values():
        assert 0.0 <= mode["hit@1"] <= mode["hit@3"] <= mode["hit@5"] <= 1.0
        assert 0.0 <= mode["mrr@10"] <= 1.0
        assert mode["by_difficulty"]["easy"]["n"] == 6


def test_evaluate_pipeline_with_fake_llm(settings, retriever, sample, tmp_path, capsys):
    policy = AutomationPolicy.load(settings.policy_path)
    graph = build_graph(TriageDeps(FakeLLM(), retriever, policy, settings))
    pipe = evaluate_pipeline(graph, policy, sample, demo=True)

    assert pipe["label"] == FAKE_LLM_LABEL
    assert pipe["tickets"] == len(sample) and pipe["errors"] == 0
    assert 0.0 <= pipe["macro_f1"] <= 1.0
    assert sum(sum(row.values()) for row in pipe["confusion_matrix"].values()) == len(sample)
    assert [row["threshold"] for row in pipe["policy_thresholds"]] == list(THRESHOLDS)
    assert 0.0 <= pipe["citations"]["validity_rate"] <= 1.0
    by_intent = {x["intent"]: x for x in pipe["per_intent_automation"]}
    for intent in ("refunds", "settlements", "payouts", "disputes"):
        assert by_intent[intent]["risk_class"] == "money_movement"
        assert by_intent[intent]["recommendation"] == "never (money_movement)"
    # The configured policy must never auto-send a money-movement ticket.
    money = {"refunds", "settlements", "payouts", "disputes", "kyc", "account_access"}
    assert not [r for r in pipe["records"] if r["decision"] == "auto_send" and r["pred_intent"] in money]

    report = {
        "meta": {
            "retrieval_only": False,
            "llm_provider": "fake",
            "llm_model": "fake",
            "pipeline_retriever": "in-memory",
        },
        "dataset": dataset_stats(sample),
        "pipeline": pipe,
        "handling_time": {"status": "no review data"},
    }
    print_report(report)
    out = capsys.readouterr().out
    assert FAKE_LLM_LABEL.upper() in out and "no review data" in out
    path = write_report(report, tmp_path)
    assert json.loads(path.read_text())["pipeline"]["label"] == FAKE_LLM_LABEL
    assert (tmp_path / "latest_full.json").exists()
