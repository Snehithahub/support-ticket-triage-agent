"""Prompt templates. The TASK markers also let the fake LLM recognise which node is calling."""

from __future__ import annotations

from triagedesk.schemas import RetrievedChunk
from triagedesk.taxonomy import INTENT_DESCRIPTIONS

CLASSIFY_MARKER = "TASK: CLASSIFY_TICKET"
DRAFT_MARKER = "TASK: DRAFT_REPLY"


def classify_messages(subject: str, body: str) -> list[dict[str, str]]:
    intents = "\n".join(f"- {i.value}: {d}" for i, d in INTENT_DESCRIPTIONS.items())
    system = f"""{CLASSIFY_MARKER}
You triage support tickets sent by merchants (online businesses) to Northwind Pay, an Indian
payment gateway. Tickets may be in English or Hinglish. Classify the ticket.

Intents (use exactly one id for "intent"):
{intents}

Return ONLY a JSON object with these keys:
{{"intent": "<intent id>",
  "secondary_intents": ["<other intent ids the ticket ALSO asks about>"],
  "urgency": "low" | "normal" | "high" | "critical",
  "sentiment": "negative" | "neutral" | "positive",
  "confidence": <number 0-1, your probability that "intent" is correct>,
  "rationale": "<one short sentence>"}}

Urgency guide: critical = live payments/settlements broken for the whole business or a security
incident (leaked keys, account takeover) or legal threat; high = money stuck or a deadline within
days; normal = a specific problem without a deadline; low = how-to or general question."""
    user = f"Subject: {subject or '(none)'}\n\n{body}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for c in chunks:
        blocks.append(f"<<ARTICLE {c.article_id} | {c.title} | {c.heading}>>\n{c.content.strip()}\n<<END>>")
    return "\n\n".join(blocks)


def draft_messages(
    subject: str, body: str, intent: str, chunks: list[RetrievedChunk], feedback: str | None = None
) -> list[dict[str, str]]:
    system = f"""{DRAFT_MARKER}
You write replies for Northwind Pay merchant support. Use ONLY the help-center excerpts provided.

Rules:
- Every factual statement (timelines, fees, limits, steps, error meanings) must be followed by a
  citation of the article it came from, written exactly as [ARTICLE-ID], e.g. [REF-02].
- Cite only article ids that appear in the excerpts. Never invent ids, numbers, or policies.
- If the excerpts do not answer the question, or the merchant needs an action only staff can take
  (moving money, changing account data, investigating a specific transaction), say that the
  ticket is being escalated to the right team and set needs_escalation to true.
- Never ask for passwords, OTPs, full card numbers, or API key secrets.
- Plain, friendly, concise (under 180 words). No markdown headings. Sign off as "Northwind Pay Support".

Return ONLY a JSON object: {{"reply": "<text>", "needs_escalation": true|false,
"escalation_reason": "<empty or short reason>"}}"""
    user = (
        f"Detected intent: {intent}\n\nTicket subject: {subject or '(none)'}\nTicket body:\n{body}\n\n"
        f"Help-center excerpts:\n{format_context(chunks) or '(no relevant articles found)'}"
    )
    if feedback:
        user += f"\n\nYour previous draft failed verification: {feedback}\nFix it."
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
