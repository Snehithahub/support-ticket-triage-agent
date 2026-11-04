"""Pure formatting and SLA logic for the review console (no Streamlit, no HTTP)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

# First-response targets the console measures queue age against. These are console defaults,
# not contractual SLAs; change them here if your support team uses different targets.
SLA_TARGET_HOURS: dict[str, float] = {"critical": 1, "high": 4, "normal": 24, "low": 72}
AT_RISK_FRACTION = 0.75

OPEN_STATUSES = ("pending_review", "escalated", "auto_send_eligible")
RESOLVED_STATUSES = ("approved", "edited", "rejected")
URGENCY_RANK = {"critical": 0, "high": 1, "normal": 2, "low": 3}

SLA_LABELS = {
    "breached": ":red[● Breached]",
    "at_risk": ":orange[▲ At risk]",
    "on_track": ":green[○ On track]",
    "met": ":green[✓ Met]",
    "missed": ":red[✕ Missed]",
    "n/a": "–",
}
SLA_TEXT = {
    "breached": "● Breached",
    "at_risk": "▲ At risk",
    "on_track": "○ On track",
    "met": "✓ Met",
    "missed": "✕ Missed",
    "n/a": "–",
}


def parse_ts(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def sla_state(ticket: dict[str, Any], now: datetime) -> tuple[str, float | None]:
    """Return (state, age_seconds). Open tickets age until now; resolved ones until resolved_at."""
    created = parse_ts(ticket.get("created_at"))
    if created is None:
        return "n/a", None
    resolved = parse_ts(ticket.get("resolved_at"))
    age = ((resolved or now) - created).total_seconds()
    target_h = SLA_TARGET_HOURS.get(ticket.get("urgency") or "")
    if target_h is None:
        return "n/a", age
    target = target_h * 3600
    if resolved is not None:
        return ("met" if age <= target else "missed"), age
    if ticket.get("status") not in OPEN_STATUSES:
        return "n/a", age
    if age > target:
        return "breached", age
    return ("at_risk" if age > target * AT_RISK_FRACTION else "on_track"), age


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    s = int(max(0, round(seconds)))
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s" if m < 10 else f"{m}m"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h {m:02d}m"
    d, h = divmod(h, 24)
    return f"{d}d {h}h"


def fmt_pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def humanize(value: str | None) -> str:
    return (value or "–").replace("_", " ")


def queue_rows(items: Iterable[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Shape /tickets items into table rows, most urgent then oldest first."""
    rows = []
    for t in items:
        state, age = sla_state(t, now)
        rows.append(
            {
                "id": str(t["id"]),
                "sla": SLA_TEXT[state],
                "age": fmt_duration(age),
                "age_s": age,
                "urgency": t.get("urgency") or "–",
                "intent": t.get("intent") or "–",
                "confidence": t.get("confidence"),
                "decision": t.get("decision") or "–",
                "team": t.get("team") or "–",
                "status": t.get("status"),
                "subject": t.get("subject") or "(no subject)",
                "channel": t.get("channel"),
            }
        )
    rows.sort(key=lambda r: (URGENCY_RANK.get(r["urgency"], 9), -(r["age_s"] or 0)))
    return rows


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    decisions: Iterable[str] = (),
    intents: Iterable[str] = (),
    urgencies: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Empty filter = no constraint on that column."""
    d, i, u = set(decisions), set(intents), set(urgencies)
    return [
        r
        for r in rows
        if (not d or r["decision"] in d) and (not i or r["intent"] in i) and (not u or r["urgency"] in u)
    ]


def review_rates(reviews: dict[str, Any] | None) -> dict[str, float | None]:
    total = (reviews or {}).get("total") or 0
    return {k: (reviews[k] / total if total else None) for k in ("approved", "edited", "rejected")}
