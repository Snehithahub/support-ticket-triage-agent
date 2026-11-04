import pytest

from tests.conftest import ScriptedLLM
from triagedesk.graph import classify_with_repair
from triagedesk.json_repair import JsonRepairError, extract_json
from triagedesk.llm import LLMError
from triagedesk.schemas import Classification
from triagedesk.taxonomy import Intent

GOOD = '{"intent": "refunds", "urgency": "high", "sentiment": "negative", "confidence": 0.9, "rationale": "r"}'


@pytest.mark.parametrize(
    "raw",
    [
        GOOD,
        f"```json\n{GOOD}\n```",
        f"Sure! Here is the classification:\n{GOOD}\nLet me know.",
        GOOD.replace("}", ",}"),
        "{'intent': 'refunds', 'urgency': 'high', 'sentiment': 'negative', 'confidence': 0.9}",
        '{intent: "refunds", urgency: "high", sentiment: "negative", confidence: 0.9}',
        "{“intent”: “refunds”, “confidence”: 0.9}",
    ],
)
def test_extract_json_repairs(raw):
    assert extract_json(raw)["intent"] == "refunds"


def test_extract_json_handles_braces_inside_strings():
    assert extract_json('noise {"rationale": "uses {braces}", "intent": "kyc"} tail')["intent"] == "kyc"


@pytest.mark.parametrize("raw", ["", "no json here", "[1, 2, 3]", "{broken"])
def test_extract_json_failure(raw):
    with pytest.raises(JsonRepairError):
        extract_json(raw)


def test_classification_normalises_values():
    c = Classification.model_validate(
        {
            "intent": "Chargeback",
            "secondary_intents": "refund, nonsense, chargeback",
            "urgency": "URGENT",
            "sentiment": "Angry",
            "confidence": "85%",
        }
    )
    assert c.intent is Intent.DISPUTES
    assert c.secondary_intents == [Intent.REFUNDS]
    assert (c.urgency, c.sentiment, c.confidence) == ("high", "negative", 0.85)


def test_classification_rejects_bad_values():
    with pytest.raises(ValueError):
        Classification.model_validate({"intent": "pizza", "confidence": 0.5})
    with pytest.raises(ValueError):
        Classification.model_validate({"intent": "kyc", "confidence": 3.0e3})


def test_classifier_retries_with_error_feedback():
    llm = ScriptedLLM(['{"intent": "pizza", "confidence": 0.9}', "not json at all", GOOD])
    result, meta = classify_with_repair(llm, "", "refund please", max_attempts=3)
    assert result.intent is Intent.REFUNDS
    assert meta["attempts"] == 3 and meta["repaired"] and not meta["fallback"]
    # the retry prompt carries the previous bad output and the validation error
    assert "invalid" in llm.calls[1][-1]["content"]
    assert llm.calls[1][-2]["role"] == "assistant"


def test_classifier_falls_back_after_max_attempts():
    llm = ScriptedLLM(["garbage"] * 3)
    result, meta = classify_with_repair(llm, "", "text", max_attempts=3)
    assert meta["fallback"] and result.intent is Intent.OTHER and result.confidence == 0.0


def test_classifier_provider_error_falls_back_without_retry_storm():
    llm = ScriptedLLM([LLMError("down")])
    _, meta = classify_with_repair(llm, "", "text", max_attempts=3)
    assert meta["fallback"] and meta["attempts"] == 1
