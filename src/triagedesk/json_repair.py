"""Best-effort extraction of a JSON object from LLM output.

Handles the failure modes seen in practice: markdown code fences, prose around the
object, trailing commas, smart quotes, Python literals and single-quoted keys.
"""

from __future__ import annotations

import json
import re
from typing import Any


class JsonRepairError(ValueError):
    pass


_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.MULTILINE)
_PY_LITERALS = {r"\bTrue\b": "true", r"\bFalse\b": "false", r"\bNone\b": "null"}


def _balanced_object(text: str) -> str | None:
    """Return the first balanced {...} substring, respecting string literals."""
    start = text.find("{")
    while start != -1:
        depth, in_str, escape, quote = 0, False, False, ""
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == quote:
                    in_str = False
            elif ch in "\"'":
                in_str, quote = True, ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def _candidates(text: str) -> list[str]:
    out = [m.group(1).strip() for m in _FENCE_RE.finditer(text)]
    out.append(text.strip())
    obj = _balanced_object(text)
    if obj:
        out.append(obj)
    return out


def _repairs(s: str) -> list[str]:
    fixed = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    fixed = _LINE_COMMENT_RE.sub("", fixed)
    fixed = _TRAILING_COMMA_RE.sub(r"\1", fixed)
    variants = [fixed]
    py = fixed
    for pat, rep in _PY_LITERALS.items():
        py = re.sub(pat, rep, py)
    variants.append(py)
    if '"' not in py:
        variants.append(py.replace("'", '"'))
    # Unquoted keys: {intent: "x"} -> {"intent": "x"}
    variants.append(re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', py))
    return variants


def extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in `text`, repairing common defects. Raises JsonRepairError."""
    if not text or not text.strip():
        raise JsonRepairError("empty output")
    for cand in _candidates(text):
        for variant in [cand, *_repairs(cand)]:
            try:
                value = json.loads(variant)
            except json.JSONDecodeError:
                obj = _balanced_object(variant)
                if not obj or obj == variant:
                    continue
                try:
                    value = json.loads(obj)
                except json.JSONDecodeError:
                    continue
            if isinstance(value, dict):
                return value
    raise JsonRepairError(f"no JSON object found in output: {text[:120]!r}")


def was_repaired(text: str) -> bool:
    try:
        return not isinstance(json.loads(text), dict)
    except json.JSONDecodeError:
        return True
