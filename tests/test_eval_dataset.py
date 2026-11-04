"""Consistency checks on the labelled ticket set against the taxonomy, the KB and the policy."""

from __future__ import annotations

from collections import Counter

import pytest

from triagedesk.chunking import load_articles
from triagedesk.config import PROJECT_ROOT
from triagedesk.eval import DEFAULT_TICKETS, dataset_stats, load_tickets
from triagedesk.policy import AutomationPolicy
from triagedesk.taxonomy import Intent

KB_DIR = PROJECT_ROOT / "kb" / "articles"
POLICY = PROJECT_ROOT / "config" / "automation_policy.yaml"


@pytest.fixture(scope="module")
def tickets():
    return load_tickets(DEFAULT_TICKETS)


@pytest.fixture(scope="module")
def articles():
    return {a.id: a for a in load_articles(KB_DIR)}


def test_size_ids_and_coverage(tickets):
    assert 160 <= len(tickets) <= 200
    assert len({t.id for t in tickets}) == len(tickets)
    assert {t.gold_intent for t in tickets} == {i.value for i in Intent}
    assert all(t.body.strip() for t in tickets)


def test_gold_articles_exist(tickets, articles):
    missing = {(t.id, a) for t in tickets for a in t.gold_articles if a not in articles}
    assert not missing


def test_other_has_no_articles_and_everything_else_does(tickets):
    for t in tickets:
        assert bool(t.gold_articles) == (t.gold_intent != Intent.OTHER.value), t.id


def test_secondary_intents_match_multi_intent_tag(tickets):
    for t in tickets:
        assert t.gold_intent not in t.gold_secondary, t.id
        assert bool(t.gold_secondary) == (t.difficulty == "multi_intent"), t.id


def test_should_automate_consistent_with_policy(tickets):
    policy = AutomationPolicy.load(POLICY)
    for t in tickets:
        if not t.should_automate:
            continue
        p = policy.for_intent(t.gold_intent)
        # Money movement and regulated intents are never automated; neither are multi-intent,
        # angry, critical or action-request tickets.
        assert p.risk_class == "informational" and p.auto_send, t.id
        assert t.difficulty != "multi_intent", t.id
        assert not {"angry", "critical", "action_request"} & set(t.tags), t.id


def test_mix_of_difficulties(tickets):
    stats = dataset_stats(tickets)
    assert stats["by_difficulty"]["ambiguous"] > 0 and stats["by_difficulty"]["multi_intent"] > 0
    assert stats["hinglish"] > 0
    assert sum(stats["by_intent"].values()) == len(tickets)
    assert max(Counter(t.gold_intent for t in tickets).values()) <= 0.15 * len(tickets)
