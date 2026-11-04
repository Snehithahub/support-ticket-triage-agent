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
PHONE_RE = re.compile(r"(?<![\w-])(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\w-])")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
ACCOUNT_RE = re.compile(r"(?<![\w-])\d{9,18}(?![\w-])")
SECRET_RE = re.compile(r"(?i)\b(key[_ ]?secret|password|passwd|otp)\b(\s*(?:is|:|=)\s*)(\S+)")


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
    out = sub(CARD_RE, "CARD", out, lambda s: 13 <= len(re.sub(r"\D", "", s)) <= 19
              and luhn_ok(re.sub(r"\D", "", s)))
    out = sub(AADHAAR_RE, "AADHAAR", out, lambda s: len(re.sub(r"\D", "", s)) == 12)
    out = sub(PHONE_RE, "PHONE", out)
    out = sub(PAN_RE, "PAN", out)
    out = sub(ACCOUNT_RE, "ACCOUNT_NUMBER", out)
    return MaskResult(text=out, found=found)
