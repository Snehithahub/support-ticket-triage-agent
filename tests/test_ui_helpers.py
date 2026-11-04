"""Tests for the review console's pure SLA and formatting helpers (ui/helpers.py)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.helpers import filter_rows, fmt_duration, parse_ts, queue_rows, review_rates, sla_state

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def ticket(
    urgency: str,
    age: timedelta,
    status: str = "pending_review",
    resolved_after: timedelta | None = None,
    **extra,
) -> dict:
    created = NOW - age
    return {
        "id": f"t-{urgency}-{age.total_seconds():.0f}",
        "urgency": urgency,
        "status": status,
        "created_at": created.isoformat(),
        "resolved_at": (created + resolved_after).isoformat() if resolved_after else None,
        **extra,
    }


@pytest.mark.parametrize(
    ("urgency", "age", "expected"),
    [
        ("critical", timedelta(minutes=30), "on_track"),
        ("critical", timedelta(minutes=50), "at_risk"),
        ("critical", timedelta(minutes=61), "breached"),
        ("high", timedelta(hours=3, minutes=30), "at_risk"),
        ("normal", timedelta(hours=2), "on_track"),
        ("low", timedelta(days=4), "breached"),
    ],
)
def test_sla_state_for_open_tickets(urgency, age, expected):
    state, age_s = sla_state(ticket(urgency, age), NOW)
    assert state == expected
    assert age_s == pytest.approx(age.total_seconds())


def test_sla_state_resolved_uses_resolution_time_not_now():
    met = ticket("high", timedelta(days=2), status="approved", resolved_after=timedelta(hours=1))
    missed = ticket("high", timedelta(days=2), status="rejected", resolved_after=timedelta(hours=5))
    assert sla_state(met, NOW) == ("met", 3600)
    assert sla_state(missed, NOW)[0] == "missed"


def test_sla_state_unknown_urgency_or_failed_ticket():
    assert sla_state(ticket("", timedelta(hours=1)), NOW)[0] == "n/a"
    assert sla_state(ticket("high", timedelta(hours=9), status="triage_failed"), NOW)[0] == "n/a"
    assert sla_state({"urgency": "high"}, NOW) == ("n/a", None)


def test_parse_ts_accepts_z_suffix_and_naive_values():
    assert parse_ts("2026-11-04T12:00:00Z") == NOW
    assert parse_ts("2026-11-04T12:00:00") == NOW
    assert parse_ts("2026-11-04T17:30:00+05:30") == NOW
    assert parse_ts(None) is None


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (None, "–"),
        (-5, "0s"),
        (42, "42s"),
        (125, "2m 05s"),
        (1500, "25m"),
        (3720, "1h 02m"),
        (90_000, "1d 1h"),
    ],
)
def test_fmt_duration(seconds, text):
    assert fmt_duration(seconds) == text


def test_queue_rows_orders_by_urgency_then_oldest_and_filters():
    items = [
        ticket("normal", timedelta(hours=1), intent="refunds", decision="human_review"),
        ticket("critical", timedelta(minutes=5), intent="settlements", decision="escalate"),
        ticket("normal", timedelta(hours=5), intent="webhooks", decision="auto_send"),
        ticket("low", timedelta(hours=1), intent=None, decision=None),
    ]
    rows = queue_rows(items, NOW)
    assert [(r["urgency"], r["age"]) for r in rows] == [
        ("critical", "5m 00s"),
        ("normal", "5h 00m"),
        ("normal", "1h 00m"),
        ("low", "1h 00m"),
    ]
    assert rows[-1]["intent"] == "–" and rows[-1]["subject"] == "(no subject)"
    assert [r["intent"] for r in filter_rows(rows, decisions=["auto_send", "escalate"])] == [
        "settlements",
        "webhooks",
    ]
    assert [r["intent"] for r in filter_rows(rows, intents=["refunds"], urgencies=["normal"])] == ["refunds"]
    assert filter_rows(rows) == rows


def test_review_rates():
    assert review_rates({"total": 4, "approved": 2, "edited": 1, "rejected": 1}) == {
        "approved": 0.5,
        "edited": 0.25,
        "rejected": 0.25,
    }
    assert review_rates({"total": 0, "approved": 0, "edited": 0, "rejected": 0})["approved"] is None
    assert review_rates(None)["edited"] is None
