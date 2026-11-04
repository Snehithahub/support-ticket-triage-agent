"""Routing policy: auto_send vs human_review vs escalate, driven by a per-intent YAML policy."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from triagedesk.schemas import Classification, DraftOutput, RoutingDecision, Verification
from triagedesk.taxonomy import Intent

RiskClass = Literal["money_movement", "regulated", "informational"]


class IntentPolicy(BaseModel):
    risk_class: RiskClass = "informational"
    auto_send: bool = False
    min_confidence: float = Field(default=0.9, ge=0, le=1)
    team: str = "general-support"
    escalate_urgencies: list[str] = Field(default_factory=list)


class AutomationPolicy(BaseModel):
    version: str
    supported_languages: list[str] = Field(default_factory=lambda: ["en"])
    escalate_urgencies: list[str] = Field(default_factory=lambda: ["critical"])
    review_negative_sentiment: bool = True
    default: IntentPolicy = Field(default_factory=IntentPolicy)
    intents: dict[str, IntentPolicy] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> AutomationPolicy:
        raw = yaml.safe_load(path.read_text())
        default = raw.get("default", {})
        raw["intents"] = {Intent(k).value: {**default, **(v or {})} for k, v in (raw.get("intents") or {}).items()}
        return cls.model_validate(raw)

    def for_intent(self, intent: str) -> IntentPolicy:
        return self.intents.get(intent, self.default)


def route(
    policy: AutomationPolicy,
    classification: Classification,
    *,
    classifier_fallback: bool,
    draft: DraftOutput | None,
    verification: Verification | None,
    language: str,
    min_confidence_override: float | None = None,
    ignore_risk_class: bool = False,
) -> RoutingDecision:
    """Apply the policy. The two keyword-only overrides exist for the eval's what-if sweeps."""
    p = policy.for_intent(classification.intent.value)
    escalate: list[str] = []
    blockers: list[str] = []

    if classifier_fallback:
        blockers.append("classifier output invalid after retries")
    urgency = classification.urgency
    if urgency in policy.escalate_urgencies or urgency in p.escalate_urgencies:
        escalate.append(f"urgency={urgency} escalates for {classification.intent.value}")
    if draft is not None and draft.needs_escalation:
        escalate.append(f"draft asked to escalate: {draft.escalation_reason or 'no grounded answer'}")

    if not p.auto_send and not ignore_risk_class:
        blockers.append(f"{classification.intent.value} is {p.risk_class}; policy never auto-sends it")
    threshold = p.min_confidence if min_confidence_override is None else min_confidence_override
    if classification.confidence < threshold:
        blockers.append(f"confidence {classification.confidence:.2f} < {threshold:.2f}")
    if classification.secondary_intents:
        blockers.append("multi-intent: " + ", ".join(i.value for i in classification.secondary_intents))
    if draft is None:
        blockers.append("no draft produced")
    if verification is not None and not verification.passed:
        blockers.append("verification failed: " + "; ".join(verification.issues))
    if policy.review_negative_sentiment and classification.sentiment == "negative":
        blockers.append("negative sentiment")
    if language not in policy.supported_languages:
        blockers.append(f"language {language!r} not supported for auto-send")

    if escalate:
        decision, reasons = "escalate", escalate + blockers
    elif blockers:
        decision, reasons = "human_review", blockers
    else:
        decision, reasons = "auto_send", [f"all gates passed (confidence >= {threshold:.2f})"]
    return RoutingDecision(decision=decision, team=p.team, reasons=reasons, policy_version=policy.version)
