"""PII masking for text sent to the LLM and stored for analysis.

Masks emails, Indian mobile numbers, card numbers (Luhn-checked), PAN, Aadhaar, UPI VPAs and
long bank-account-like digit runs. Gateway object ids (pay_..., rfnd_...) are left untouched
because support needs them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
VPA_RE = re.compile(r"\b[A-Za-z0-9._-]{2,}@(?:ok)?[A-Za-z]{2,15}\b(?!\.)")
CARD_RE = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
AADHAAR_RE = re.compile(r"(?<![\w-])[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}(?![\w-])")
AADHAAR_CONTEXT_RE = re.compile(r"(?i)\b(aadhaa?r|uidai|uid)\b")
PHONE_RE = re.compile(r"(?<![\w-])(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\w-])")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
# Bank account numbers are only masked next to an account keyword; bare 12-digit numbers are
# usually UPI RRNs or UTRs, which support needs to trace a payment.
ACCOUNT_RE = re.compile(r"(?i)(\b(?:a/c|acct|account|acc(?:ount)?\s*no|bank)\b\D{0,20}?)(\d{9,18})(?![\w-])")
SECRET_RE = re.compile(r"(?i)\b(key[_ ]?secret|password|passwd|otp)\b(\s*(?:is|:|=)\s*)([^\s,;]+)")


_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_ok(digits: str) -> bool:
    """Aadhaar numbers carry a Verhoeff check digit."""
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


def luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass
class MaskResult:
    text: str
    found: list[str] = field(default_factory=list)  # PII types, in order of appearance


def mask_pii(text: str) -> MaskResult:
    counters: dict[str, int] = {}
    found: list[str] = []

    def placeholder(kind: str) -> str:
        counters[kind] = counters.get(kind, 0) + 1
        found.append(kind)
        return f"[{kind}_{counters[kind]}]"

    def sub(pattern: re.Pattern[str], kind: str, s: str, check=None) -> str:
        def repl(m: re.Match[str]) -> str:
            if check and not check(m.group(0)):
                return m.group(0)
            return placeholder(kind)

        return pattern.sub(repl, s)

    out = SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{placeholder('SECRET')}", text)
    out = sub(EMAIL_RE, "EMAIL", out)
    out = sub(VPA_RE, "UPI_ID", out)
    out = sub(CARD_RE, "CARD", out, lambda s: 13 <= len(re.sub(r"\D", "", s)) <= 19 and luhn_ok(re.sub(r"\D", "", s)))
    aadhaar_context = bool(AADHAAR_CONTEXT_RE.search(text))

    def is_aadhaar(s: str) -> bool:
        digits = re.sub(r"\D", "", s)
        spaced = len(s) == 14  # 4-4-4 with separators, the way Aadhaar is printed
        return len(digits) == 12 and verhoeff_ok(digits) and (aadhaar_context or spaced)

    out = sub(AADHAAR_RE, "AADHAAR", out, is_aadhaar)
    out = sub(PHONE_RE, "PHONE", out)
    out = sub(PAN_RE, "PAN", out)
    out = ACCOUNT_RE.sub(lambda m: m.group(1) + placeholder("ACCOUNT_NUMBER"), out)
    return MaskResult(text=out, found=found)
