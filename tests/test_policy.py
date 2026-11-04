import pytest

from triagedesk.policy import route
from triagedesk.schemas import Classification, DraftOutput, Verification

DRAFT = DraftOutput(reply="r")
OK = Verification(passed=True, grounding_score=1.0)


def cls(intent="api_keys", conf=0.95, urgency="normal", sentiment="neutral", secondary=()):
    return Classification(
        intent=intent, confidence=conf, urgency=urgency, sentiment=sentiment, secondary_intents=list(secondary)
    )


def r(policy, c, **kw):
    args = dict(classifier_fallback=False, draft=DRAFT, verification=OK, language="en")
    args.update(kw)
    return route(policy, c, **args)


def test_informational_high_confidence_auto_sends(policy):
    d = r(policy, cls())
    assert d.decision == "auto_send" and d.team == "developer-support"


@pytest.mark.parametrize("intent", ["refunds", "settlements", "payouts", "disputes", "kyc", "account_access"])
def test_money_movement_and_regulated_never_auto_send(policy, intent):
    d = r(policy, cls(intent=intent, conf=0.99))
    assert d.decision == "human_review"
    assert "never auto-sends" in d.reasons[0]


def test_low_confidence_goes_to_review(policy):
    d = r(policy, cls(conf=0.6))
    assert d.decision == "human_review" and "confidence 0.60 < 0.85" in d.reasons[0]


def test_threshold_override_for_what_if(policy):
    assert r(policy, cls(conf=0.6), min_confidence_override=0.5).decision == "auto_send"
    assert r(policy, cls("refunds", 0.99), ignore_risk_class=True).decision == "auto_send"


def test_critical_urgency_escalates_any_intent(policy):
    d = r(policy, cls(urgency="critical"))
    assert d.decision == "escalate"


def test_high_urgency_escalates_money_movement_only(policy):
    assert r(policy, cls("disputes", urgency="high")).decision == "escalate"
    assert r(policy, cls("api_keys", urgency="high")).decision == "auto_send"


@pytest.mark.parametrize(
    "kw,expected_reason",
    [
        ({"verification": Verification(passed=False, issues=["citations not in retrieved set: X"])}, "verification"),
        ({"draft": None, "verification": None}, "no draft"),
        ({"language": "ta"}, "language"),
        ({"classifier_fallback": True}, "classifier output invalid"),
    ],
)
def test_gates_block_auto_send(policy, kw, expected_reason):
    d = r(policy, cls(), **kw)
    assert d.decision == "human_review"
    assert any(expected_reason in x for x in d.reasons)


def test_negative_sentiment_and_multi_intent_block(policy):
    assert r(policy, cls(sentiment="negative")).decision == "human_review"
    assert r(policy, cls(secondary=["webhooks"])).decision == "human_review"


def test_draft_requested_escalation(policy):
    d = r(policy, cls(), draft=DraftOutput(reply="r", needs_escalation=True, escalation_reason="needs staff"))
    assert d.decision == "escalate" and "needs staff" in d.reasons[0]


def test_unknown_intent_uses_default(policy):
    d = r(policy, cls(intent="other", conf=0.99))
    assert d.decision == "human_review" and d.team == "general-support"
