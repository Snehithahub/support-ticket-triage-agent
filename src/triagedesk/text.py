"""Small text utilities shared by retrieval, verification and the fake LLM."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an and are as at be been but by can could do does for from had has have hi hello how i if in
    into is it its me my no not of on or our please so than that the their them then there these
    they this to us was we were what when where which who why will with would you your yours also
    any all just get got thanks thank team regards dear sir madam hai ka ki ke ko se""".split()
)
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+.\-]*[a-z0-9]|[a-z0-9]")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"(])")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 1]


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER_RE.findall(text)}


def strip_markdown(line: str) -> str:
    line = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)
    line = re.sub(r"^#+\s*", "", line)
    return line.replace("**", "").replace("__", "").strip()


def split_sentences(text: str) -> list[str]:
    """Split markdown-ish text into sentences; list items and table rows count as sentences.

    Lines inside fenced code blocks are skipped.
    """
    out: list[str] = []
    in_code = False
    para: list[str] = []

    def flush() -> None:
        if para:
            out.extend(s.strip() for s in _SENT_SPLIT_RE.split(" ".join(para)) if s.strip())
            para.clear()

    for raw in text.splitlines():
        if raw.strip().startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        line = raw.strip()
        if not line or set(line) <= set("|-: "):
            flush()
            continue
        if re.match(r"^(?:[-*+]|\d+\.)\s+", line) or line.startswith("|") or line.startswith("#"):
            flush()
            cleaned = strip_markdown(line).strip("| ").replace(" | ", ": ")
            if cleaned:
                out.extend(s.strip() for s in _SENT_SPLIT_RE.split(cleaned) if s.strip())
            continue
        para.append(line)
    flush()
    return out
