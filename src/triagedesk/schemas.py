"""Pydantic models shared by the graph, the API and the store."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from triagedesk.taxonomy import Intent, parse_intent

Urgency = Literal["low", "normal", "high", "critical"]
Sentiment = Literal["negative", "neutral", "positive"]
Decision = Literal["auto_send", "human_review", "escalate"]
ReviewAction = Literal["approve", "edit", "reject"]

_URGENCY_SYNONYMS = {"medium": "normal", "urgent": "high", "p0": "critical", "p1": "high", "blocker": "critical"}
_SENTIMENT_SYNONYMS = {"angry": "negative", "frustrated": "negative", "mixed": "neutral", "happy": "positive"}


class Classification(BaseModel):
    """Structured output of the classify node. Validators normalise sloppy LLM values."""

    model_config = ConfigDict(extra="ignore")

    intent: Intent
    secondary_intents: list[Intent] = Field(default_factory=list)
    urgency: Urgency = "normal"
    sentiment: Sentiment = "neutral"
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""

    @field_validator("intent", mode="before")
    @classmethod
    def _intent(cls, v: object) -> Intent:
        return parse_intent(v)

    @field_validator("secondary_intents", mode="before")
    @classmethod
    def _secondary(cls, v: object) -> list[Intent]:
        if v in (None, "", "none"):
            return []
        items = v if isinstance(v, list) else re.split(r"[,;]", str(v))
        out: list[Intent] = []
        for item in items:
            try:
                intent = parse_intent(item)
            except ValueError:
                continue
            if intent not in out and intent is not Intent.OTHER:
                out.append(intent)
        return out

    @field_validator("urgency", "sentiment", mode="before")
    @classmethod
    def _lower(cls, v: object) -> str:
        s = str(v).strip().lower()
        return _URGENCY_SYNONYMS.get(s, _SENTIMENT_SYNONYMS.get(s, s))

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, v: object) -> float:
        if isinstance(v, str):
            s = v.strip().rstrip("%")
            v = float(s) / 100 if v.strip().endswith("%") else float(s)
        f = float(v)  # type: ignore[arg-type]
        if 1.0 < f <= 100.0:
            f /= 100.0
        return f

    @field_validator("rationale", mode="before")
    @classmethod
    def _rationale(cls, v: object) -> str:
        return "" if v is None else str(v)[:500]

    def model_post_init(self, _ctx: object) -> None:
        if self.intent in self.secondary_intents:
            self.secondary_intents.remove(self.intent)


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    reply: str = Field(min_length=1)
    needs_escalation: bool = False
    escalation_reason: str = ""


class RetrievedChunk(BaseModel):
    chunk_id: int
    article_id: str
    title: str
    url: str
    heading: str
    category: str
    content: str
    score: float
    vector_rank: int | None = None
    fts_rank: int | None = None


class CitationCheck(BaseModel):
    article_id: str
    url: str | None = None
    in_retrieved: bool
    supported: bool
    support_score: float


class Verification(BaseModel):
    passed: bool
    citations: list[CitationCheck] = Field(default_factory=list)
    fabricated: list[str] = Field(default_factory=list)
    unsupported_sentences: list[str] = Field(default_factory=list)
    uncited_claims: list[str] = Field(default_factory=list)
    grounding_score: float = 0.0
    issues: list[str] = Field(default_factory=list)


class RoutingDecision(BaseModel):
    decision: Decision
    team: str
    reasons: list[str]
    policy_version: str


# ---- API boundary models ----


class TicketIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(default="", max_length=500)
    body: str = Field(min_length=1, max_length=20_000)
    customer_email: str | None = Field(default=None, max_length=320)
    channel: Literal["email", "web", "chat", "api", "n8n"] = "api"
    external_id: str | None = Field(default=None, max_length=200, description="Idempotency key")


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ReviewAction
    reviewer: str = Field(min_length=1, max_length=120)
    final_body: str | None = Field(default=None, max_length=20_000)
    reason: str | None = Field(default=None, max_length=1000)
    started_at: datetime | None = Field(default=None, description="When the reviewer opened the ticket")
    handling_seconds: float | None = Field(default=None, ge=0, le=86_400)


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(default="n8n", max_length=50)
    event: str = Field(min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)
