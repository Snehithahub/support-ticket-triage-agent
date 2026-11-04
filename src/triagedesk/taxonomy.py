"""Fixed intent taxonomy. Intent ids double as knowledge-base article categories."""

from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    REFUNDS = "refunds"
    FAILED_PAYMENTS = "failed_payments"
    SETTLEMENTS = "settlements"
    KYC = "kyc"
    API_KEYS = "api_keys"
    WEBHOOKS = "webhooks"
    DISPUTES = "disputes"
    ACCOUNT_ACCESS = "account_access"
    CHECKOUT = "checkout"
    PAYOUTS = "payouts"
    BILLING = "billing"
    OTHER = "other"


INTENT_DESCRIPTIONS: dict[Intent, str] = {
    Intent.REFUNDS: "Issuing refunds, refund status/timelines, failed or stuck refunds, instant refunds.",
    Intent.FAILED_PAYMENTS: "Customer payments failing, declined, pending, or debited-but-failed.",
    Intent.SETTLEMENTS: "Payouts to the merchant bank account: schedule, delays, holds, reconciliation.",
    Intent.KYC: "Merchant onboarding verification documents, KYC rejection, re-KYC.",
    Intent.API_KEYS: "API key generation/regeneration, 401/403/429 API errors, test vs live mode.",
    Intent.WEBHOOKS: (
        "Webhook setup, signature verification, delivery failures, retries, events, "
        "payment captured but order not updated."
    ),
    Intent.DISPUTES: "Chargebacks, disputes raised by banks, evidence submission, dispute fees.",
    Intent.ACCOUNT_ACCESS: "Login, password reset, 2FA, locked accounts, team members and roles.",
    Intent.CHECKOUT: "Checkout/order integration errors (order_id, amount, signature), payment links.",
    Intent.PAYOUTS: "Payouts to vendors/customers via IMPS/NEFT/RTGS/UPI: failed, reversed, queued, fees.",
    Intent.BILLING: "Pricing plans, MDR and fees, GST tax invoices, credit notes, plan changes.",
    Intent.OTHER: "Anything not covered above (feature requests, partnerships, spam, unclear).",
}

URGENCIES = ("low", "normal", "high", "critical")
SENTIMENTS = ("negative", "neutral", "positive")

# Common synonyms an LLM may emit instead of the canonical id.
INTENT_SYNONYMS: dict[str, Intent] = {
    "refund": Intent.REFUNDS,
    "refund_request": Intent.REFUNDS,
    "failed_payment": Intent.FAILED_PAYMENTS,
    "payment_failure": Intent.FAILED_PAYMENTS,
    "payments": Intent.FAILED_PAYMENTS,
    "settlement": Intent.SETTLEMENTS,
    "settlement_delay": Intent.SETTLEMENTS,
    "kyc_verification": Intent.KYC,
    "onboarding": Intent.KYC,
    "api_key": Intent.API_KEYS,
    "api": Intent.API_KEYS,
    "webhook": Intent.WEBHOOKS,
    "dispute": Intent.DISPUTES,
    "chargeback": Intent.DISPUTES,
    "chargebacks": Intent.DISPUTES,
    "dispute_chargeback": Intent.DISPUTES,
    "login": Intent.ACCOUNT_ACCESS,
    "account": Intent.ACCOUNT_ACCESS,
    "invoice": Intent.BILLING,
    "invoices": Intent.BILLING,
    "billing_invoice": Intent.BILLING,
    "pricing": Intent.BILLING,
    "price": Intent.BILLING,
    "pricing_plans": Intent.BILLING,
    "fees": Intent.BILLING,
    "payment_links": Intent.CHECKOUT,
    "integration": Intent.CHECKOUT,
    "checkout_integration": Intent.CHECKOUT,
    "payout": Intent.PAYOUTS,
    "payout_failure": Intent.PAYOUTS,
    "general": Intent.OTHER,
    "unknown": Intent.OTHER,
}


def parse_intent(value: object) -> Intent:
    """Map a free-form label to a canonical Intent. Raises ValueError if unknown."""
    key = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    try:
        return Intent(key)
    except ValueError:
        if key in INTENT_SYNONYMS:
            return INTENT_SYNONYMS[key]
    raise ValueError(f"unknown intent {value!r}")
