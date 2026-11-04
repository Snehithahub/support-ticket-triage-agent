"""Deterministic stand-in for an LLM, used in demo mode and tests.

It is NOT a model: classification is a keyword scorer and drafting copies the best-matching
sentences from the retrieved excerpts with their citations. It exists so the whole pipeline
(graph, API, n8n, UI, eval plumbing) runs offline and reproducibly. Its keyword lists were
written from the help-center vocabulary before the evaluation set was built.
"""

from __future__ import annotations

import json
import re

from triagedesk.prompts import CLASSIFY_MARKER, DRAFT_MARKER
from triagedesk.text import content_tokens, split_sentences

KEYWORDS: dict[str, dict[str, float]] = {
    "refunds": {"refund": 3, "refunded": 3, "rfnd_": 3, "arn": 2, "money back": 2, "paisa wapas": 2,
                "instant refund": 2, "partial refund": 2, "return the amount": 1.5},
    "failed_payments": {"payment failed": 3, "failed payment": 3, "declined": 2.5, "decline": 2,
                        "debited": 2, "deducted but": 2, "kat gaya": 2, "insufficient_funds": 2,
                        "gateway_timeout": 2, "upi": 1, "pending": 1, "otp": 1, "success rate": 2,
                        "authentication_failed": 2, "invalid_vpa": 2, "collect": 1, "not going through": 2,
                        "authorized": 1, "failing": 1.5},
    "settlements": {"settlement": 3, "settled": 2.5, "setl_": 3, "utr": 1.5, "t+2": 2, "on hold": 1.5,
                    "not received in bank": 2, "mdr": 1.5, "instant settlement": 2,
                    "less amount": 2, "lower than expected": 2, "reconcil": 2, "bank account change": 1},
    "payouts": {"payout": 3, "pout_": 3, "imps": 2, "neft": 2, "rtgs": 2, "beneficiary": 2,
                "vendor payment": 2, "reversed": 1.5, "penny drop": 2, "payout balance": 2, "ifsc": 1.5},
    "disputes": {"chargeback": 3, "dispute": 3, "disp_": 3, "evidence": 2, "retrieval request": 2,
                 "arbitration": 2, "fraudulent transaction": 1.5, "unauthorized transaction": 1.5},
    "kyc": {"kyc": 3, "documents": 1.5, "pan": 1.5, "gstin": 1, "activation": 2, "verification": 1,
            "rejected": 1, "onboarding": 2, "re-kyc": 3, "account not activated": 2, "live mode": 0.5},
    "account_access": {"password": 3, "login": 2.5, "log in": 2.5, "2fa": 3, "two-factor": 3,
                       "locked": 2.5, "otp not": 1.5, "authenticator": 2.5, "team member": 2,
                       "invite": 1.5, "role": 1, "owner": 1, "registered email": 2, "backup code": 2},
    "api_keys": {"api key": 3, "key secret": 3, "key id": 2, "401": 2.5, "authentication_error": 3,
                 "429": 2, "rate limit": 2.5, "403": 1.5, "ip_not_allowed": 3, "allowlist": 2,
                 "whitelist": 2, "test mode": 1.5, "nw_live": 2, "nw_test": 2, "regenerate": 2},
    "webhooks": {"webhook": 3, "x-northwind-signature": 3, "signature mismatch": 2, "event": 1,
                 "callback": 1.5, "endpoint": 1.5, "order not updated": 2.5, "order status not": 2,
                 "payment.captured": 2, "order.paid": 2, "retries": 1, "delivery": 1},
    "checkout": {"checkout": 3, "checkout.js": 3, "payment link": 3, "order_id": 2, "integration": 2,
                 "integrate": 2, "bad_request_error": 2.5, "amount must be at least": 3, "paise": 2,
                 "signature verification failed": 2, "popup": 2, "not opening": 2, "csp": 2},
    "billing": {"invoice": 3, "gst": 1.5, "pricing": 3, "plan": 1.5, "fees": 2, "fee": 1.5, "mdr": 1,
                "credit note": 3, "charges": 1.5, "growth plan": 3, "enterprise": 2, "custom pricing": 3,
                "tax invoice": 3, "commission": 1.5, "rate": 0.5},
}

CRITICAL = ("all payments failing", "all payments are failing", "production down", "site down",
            "leaked", "compromised", "hacked", "legal notice", "lawyer", "consumer court", "police",
            "account takeover", "sab payments fail")
HIGH = ("urgent", "asap", "immediately", "jaldi", "today", "deadline", "escalate", "stuck",
        "still not", "since 3 days", "since last week", "salary", "kal tak", "abhi tak")
LOW = ("how do i", "how to", "how can i", "can i ", "is it possible", "what is", "kaise", "question",
       "wondering", "documentation")
NEGATIVE = ("worst", "frustrat", "angry", "unacceptable", "pathetic", "disappoint", "ridiculous",
            "bakwas", "terrible", "horrible", "useless", "fed up", "!!!", "no response", "third time")
POSITIVE = ("thank you so much", "great service", "appreciate", "love ")


class FakeLLM:
    model = "fake-heuristic-v1"
    demo = True

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        system = messages[0]["content"]
        user = messages[-1]["content"]
        if CLASSIFY_MARKER in system:
            return json.dumps(self._classify(user))
        if DRAFT_MARKER in system:
            return json.dumps(self._draft(user))
        return "{}"

    @staticmethod
    def _classify(text: str) -> dict:
        t = text.lower()
        scores = {intent: sum(w for kw, w in kws.items() if kw in t) for intent, kws in KEYWORDS.items()}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        top_intent, top = ranked[0]
        total = sum(s for _, s in ranked)
        if top == 0:
            intent, confidence = "other", 0.3
        else:
            intent = top_intent
            confidence = round(min(0.97, max(0.2, top / (total + 0.5))), 2)
        secondary = [i for i, s in ranked[1:] if top and s >= 0.6 * top and s >= 2.5]
        if any(k in t for k in CRITICAL):
            urgency = "critical"
        elif any(k in t for k in HIGH):
            urgency = "high"
        elif any(k in t for k in LOW):
            urgency = "low"
        else:
            urgency = "normal"
        if any(k in t for k in NEGATIVE):
            sentiment = "negative"
        elif any(k in t for k in POSITIVE):
            sentiment = "positive"
        else:
            sentiment = "neutral"
        return {"intent": intent, "secondary_intents": secondary, "urgency": urgency,
                "sentiment": sentiment, "confidence": confidence,
                "rationale": f"keyword match (demo mode): {intent}"}

    @staticmethod
    def _draft(user: str) -> dict:
        ticket = user.split("Help-center excerpts:")[0]
        q = set(content_tokens(ticket))
        blocks = re.findall(r"<<ARTICLE (\S+) \| [^\n]*>>\n(.*?)\n<<END>>", user, re.DOTALL)
        candidates: list[tuple[float, int, str, str]] = []
        for rank, (aid, content) in enumerate(blocks):
            for sent in split_sentences(content):
                toks = set(content_tokens(sent))
                if len(sent.split()) < 6 or not toks:
                    continue
                score = len(q & toks) / (len(toks) ** 0.5) - 0.15 * rank
                candidates.append((score, rank, aid, sent))
        if not candidates:
            return {"reply": "Hi,\n\nThanks for reaching out. We could not find a help-center answer for "
                    "this, so we are escalating your ticket to the right team.\n\nNorthwind Pay Support",
                    "needs_escalation": True, "escalation_reason": "no relevant articles"}
        candidates.sort(key=lambda c: (-c[0], c[1]))
        chosen = sorted(candidates[:3], key=lambda c: c[1])
        body = " ".join(f"{s.rstrip()} [{aid}]" for _, _, aid, s in chosen)
        reply = (f"Hi,\n\nThanks for writing to Northwind Pay Support. {body}\n\n"
                 "If this does not resolve it, reply to this email with the relevant IDs and "
                 "we will look into it.\n\nNorthwind Pay Support")
        return {"reply": reply, "needs_escalation": False, "escalation_reason": ""}
