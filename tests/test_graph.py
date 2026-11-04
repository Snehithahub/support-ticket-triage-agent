import json

import pytest

from tests.conftest import ScriptedLLM
from triagedesk.fake_llm import FakeLLM
from triagedesk.graph import TriageDeps, build_graph, run_triage
from triagedesk.llm import LLMError

CLS = json.dumps({"intent": "webhooks", "urgency": "normal", "sentiment": "neutral", "confidence": 0.95})


@pytest.fixture
def make_graph(settings, retriever, policy):
    def _make(llm):
        return build_graph(TriageDeps(llm, retriever, policy, settings))

    return _make


def test_fake_llm_end_to_end_informational(make_graph):
    g = make_graph(FakeLLM())
    st = run_triage(
        g,
        "Webhook signature mismatch",
        "Our endpoint rejects every event: the X-Northwind-Signature HMAC never matches. "
        "We compute it on the parsed JSON body. Contact me at dev@shop.in",
    )
    assert st["classification"]["intent"] == "webhooks"
    assert "[EMAIL_1]" in st["masked_text"] and st["pii_types"] == ["EMAIL"]
    assert st["retrieved"] and all(c["category"] == "webhooks" for c in st["retrieved"])
    assert st["verification"]["passed"]
    assert st["routing"]["decision"] == "auto_send"
    assert "](http" in st["draft"]["reply_rendered"]
    assert set(st["timings_ms"]) == {"normalize", "classify", "retrieve", "draft", "verify", "route"}


def test_fake_llm_money_movement_goes_to_human(make_graph):
    st = run_triage(make_graph(FakeLLM()), "Refund", "Refund for pay_N3x9QbV2kL7mTz not received, share ARN")
    assert st["classification"]["intent"] == "refunds"
    assert st["routing"]["decision"] == "human_review"


def test_redraft_after_fabricated_citation(make_graph):
    bad = json.dumps({"reply": "Retries last 24 hours. [WHK-99]", "needs_escalation": False})
    good = json.dumps(
        {
            "reply": "Failed deliveries are retried with exponential backoff for up to 24 hours. [WHK-03]",
            "needs_escalation": False,
        }
    )
    llm = ScriptedLLM([CLS, bad, good])
    st = run_triage(make_graph(llm), "", "webhook retries: how long do you retry failed deliveries?")
    assert st["draft_meta"]["attempts"] == 2
    assert "failed verification" in llm.calls[2][-1]["content"]
    assert "WHK-99" in llm.calls[2][-1]["content"]
    assert st["verification"]["passed"], st["verification"]
    assert st["routing"]["decision"] == "auto_send"


def test_persistent_fabrication_routes_to_human(make_graph):
    bad = json.dumps({"reply": "Retries last 24 hours. [WHK-99]", "needs_escalation": False})
    st = run_triage(make_graph(ScriptedLLM([CLS, bad, bad])), "", "webhook retry question")
    assert not st["verification"]["passed"]
    assert st["routing"]["decision"] == "human_review"
    assert any("verification failed" in r for r in st["routing"]["reasons"])


def test_llm_outage_degrades_to_human_review(make_graph):
    st = run_triage(make_graph(ScriptedLLM([LLMError("down"), LLMError("down")])), "", "help with refund")
    assert st["classify_meta"]["fallback"]
    assert st["draft"] is None
    assert st["routing"]["decision"] == "human_review"
    assert any(e.startswith("draft:") for e in st["errors"])


def test_draft_escalation_flag_escalates(make_graph):
    esc = json.dumps(
        {
            "reply": "We are escalating this to the team.",
            "needs_escalation": True,
            "escalation_reason": "needs account lookup",
        }
    )
    st = run_triage(make_graph(ScriptedLLM([CLS, esc])), "", "webhook for my account broken")
    assert st["routing"]["decision"] == "escalate"
