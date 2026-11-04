"""Ticket normalisation: strip quoted replies and signatures, detect language, mask PII."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from langdetect import DetectorFactory, LangDetectException, detect_langs

from triagedesk.pii import mask_pii

DetectorFactory.seed = 0

_QUOTE_HEADERS = [
    re.compile(r"^On .{5,200}wrote:\s*$", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^-{2,}\s*Forwarded message\s*-{2,}", re.IGNORECASE),
    re.compile(r"^From:\s.+", re.IGNORECASE),
    re.compile(r"^_{5,}\s*$"),
]
_SIGNATURE_STARTS = [
    re.compile(r"^--\s*$"),
    re.compile(r"^(?:Sent from my|Get Outlook for)\b", re.IGNORECASE),
    re.compile(
        r"^(?:best regards|kind regards|warm regards|regards|thanks(?: and| &) regards|thanks|"
        r"thank you|cheers|sincerely|best|dhanyavaad|shukriya)[,.!]?\s*$",
        re.IGNORECASE,
    ),
]
# Common Hinglish markers; langdetect has no Hinglish model and tends to say "id"/"so"/"tl".
_HINGLISH = re.compile(
    r"\b(hai|nahi|nahin|kya|kab|kyun|kyu|mera|meri|mere|humara|hamara|abhi|tak|ho gaya|hua|"
    r"karo|kijiye|bhai|paisa|paise|wapas|jaldi|kal|aaj|raha|rahi|gaya)\b",
    re.IGNORECASE,
)


@dataclass
class Normalized:
    clean_text: str
    masked_text: str
    language: str
    pii_types: list[str] = field(default_factory=list)


def strip_quoted_and_signature(text: str) -> str:
    lines = text.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    for line in lines:
        s = line.strip()
        if any(p.match(s) for p in _QUOTE_HEADERS):
            break
        if s.startswith(">"):
            continue
        kept.append(line.rstrip())
    # A signature starts at a sign-off line in the last part of the message.
    cut = len(kept)
    tail_start = max(0, len(kept) - 8)
    for i in range(tail_start, len(kept)):
        if any(p.match(kept[i].strip()) for p in _SIGNATURE_STARTS):
            cut = i
            break
    body = "\n".join(kept[:cut]).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body or text.strip()


def detect_language(text: str) -> str:
    words = re.findall(r"[A-Za-z]+", text)
    if len(_HINGLISH.findall(text)) >= 2 and len(words) > 3:
        return "hinglish"
    if len(text.strip()) < 20:
        return "en"
    try:
        best = detect_langs(text)[0]
    except LangDetectException:
        return "unknown"
    # Short, jargon-heavy English is often misdetected; trust only confident non-English calls.
    if best.lang != "en" and best.prob < 0.9:
        return "en"
    return best.lang


def normalize_ticket(subject: str, body: str) -> Normalized:
    clean = strip_quoted_and_signature(body)
    full = f"{subject}\n\n{clean}" if subject else clean
    masked = mask_pii(full)
    return Normalized(
        clean_text=clean,
        masked_text=masked.text,
        language=detect_language(clean),
        pii_types=sorted(set(masked.found)),
    )
