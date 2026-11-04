"""Tests for the review console's HTTP client (ui/client.py), using httpx.MockTransport."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui.client import ApiError, ApiUnavailable, TriageClient, extract_section

BASE = "http://api.test"
TID = "6f1c2b9e-0d7a-4c43-9a51-1f0e2d3c4b5a"


def make_client(handler) -> tuple[TriageClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return TriageClient(BASE + "/", transport=httpx.MockTransport(record)), seen


def test_list_tickets_sends_only_set_filters_and_returns_items():
    client, seen = make_client(lambda r: httpx.Response(200, json={"items": [{"id": TID}], "count": 1}))
    assert client.list_tickets(decision="escalate", limit=50) == [{"id": TID}]
    params = dict(seen[0].url.params)
    assert params == {"decision": "escalate", "limit": "50", "offset": "0"}
    assert seen[0].url.path == "/tickets"


def test_review_payload_includes_reviewer_edit_and_handling_time():
    client, seen = make_client(lambda r: httpx.Response(200, json={"review": {}, "citation_warnings": []}))
    started = datetime(2026, 11, 4, 10, 0, tzinfo=UTC)
    client.review(
        TID,
        action="edit",
        reviewer="agent-7",
        final_body="Hello [REF-01]",
        started_at=started,
        handling_seconds=42.123456,
    )
    req = seen[0]
    assert req.method == "POST" and req.url.path == f"/tickets/{TID}/review"
    assert json.loads(req.content) == {
        "action": "edit",
        "reviewer": "agent-7",
        "final_body": "Hello [REF-01]",
        "started_at": "2026-11-04T10:00:00+00:00",
        "handling_seconds": 42.12,
    }


def test_review_approve_omits_optional_fields_and_clamps_negative_time():
    client, seen = make_client(lambda r: httpx.Response(200, json={"review": {}}))
    client.review(TID, action="approve", reviewer="a", handling_seconds=-3)
    assert json.loads(seen[0].content) == {"action": "approve", "reviewer": "a", "handling_seconds": 0.0}


def test_review_conflict_raises_api_error_with_status_and_detail():
    client, _ = make_client(lambda r: httpx.Response(409, json={"detail": "ticket is approved; it cannot be reviewed"}))
    with pytest.raises(ApiError) as exc_info:
        client.review(TID, action="approve", reviewer="a")
    err = exc_info.value
    assert not isinstance(err, ApiUnavailable)
    assert err.status_code == 409
    assert "cannot be reviewed" in str(err)


def test_validation_error_detail_is_readable():
    detail = [{"loc": ["body", "reviewer"], "msg": "String should have at least 1 character", "type": "x"}]
    client, _ = make_client(lambda r: httpx.Response(422, json={"detail": detail}))
    with pytest.raises(ApiError, match=r"body\.reviewer: String should have at least 1 character"):
        client.review(TID, action="approve", reviewer="")


def test_non_json_error_body_is_reported():
    client, _ = make_client(lambda r: httpx.Response(502, text="Bad Gateway"))
    with pytest.raises(ApiError, match=r"502.*Bad Gateway"):
        client.metrics()


def test_connection_refused_raises_api_unavailable():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = make_client(refuse)
    with pytest.raises(ApiUnavailable, match=r"cannot reach the API at http://api\.test"):
        client.list_tickets()


def test_timeout_raises_api_unavailable():
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, _ = make_client(slow)
    with pytest.raises(ApiUnavailable, match="timed out"):
        client.get_ticket(TID)


def test_real_unreachable_port_is_api_unavailable():
    client = TriageClient("http://127.0.0.1:9", timeout=2)  # discard port: nothing listens
    with pytest.raises(ApiUnavailable):
        client.health()


def test_health_returns_degraded_body_on_503():
    client, _ = make_client(lambda r: httpx.Response(503, json={"status": "degraded", "database": "error: x"}))
    assert client.health()["status"] == "degraded"


def test_create_ticket_sends_idempotency_key_and_uses_long_timeout():
    client, seen = make_client(lambda r: httpx.Response(201, json={"id": TID, "status": "pending_review"}))
    out = client.create_ticket(
        subject="s", body="b", channel="email", customer_email="m@x.in", idempotency_key="ui-123"
    )
    assert out["id"] == TID
    req = seen[0]
    assert req.headers["idempotency-key"] == "ui-123"
    assert json.loads(req.content) == {
        "subject": "s",
        "body": "b",
        "channel": "email",
        "customer_email": "m@x.in",
    }
    assert req.extensions["timeout"]["read"] == client.triage_timeout


def test_create_ticket_without_optional_fields():
    client, seen = make_client(lambda r: httpx.Response(201, json={"id": TID}))
    client.create_ticket(body="b")
    assert "idempotency-key" not in seen[0].headers
    assert json.loads(seen[0].content) == {"subject": "", "body": "b", "channel": "web"}


def test_triage_failure_surfaces_structured_detail():
    body = {"detail": {"error": "triage_failed", "ticket_id": TID, "detail": "llm down"}}
    client, _ = make_client(lambda r: httpx.Response(502, json=body))
    with pytest.raises(ApiError) as exc_info:
        client.create_ticket(body="b")
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["ticket_id"] == TID


ARTICLE = """<!doctype html><html><head><title>Refund timelines</title></head><body>
<p><small>Help Center (fictional) &middot; REF-02</small></p>
<h1>Refund timelines</h1><p>Intro text.</p>
<h2>How long refunds take</h2><p>Card refunds take 5&ndash;7 business days.</p>
<ul><li>UPI: 1&ndash;3 days</li><li>Net banking: 5 days</li></ul>
<h2>Instant refunds</h2><p>Instant refunds settle in minutes.</p>
</body></html>"""


def test_article_section_extracts_deepest_heading_text():
    client, seen = make_client(lambda r: httpx.Response(200, text=ARTICLE, headers={"content-type": "text/html"}))
    text = client.article_section("REF-02", "Refund timelines > How long refunds take")
    assert seen[0].url.path == "/kb/REF-02"
    assert text is not None
    assert "Card refunds take 5–7 business days." in text
    assert "UPI: 1–3 days" in text
    assert "Instant refunds" not in text


def test_extract_section_last_section_and_missing_heading():
    assert extract_section(ARTICLE, "Refund timelines > Instant refunds") == "Instant refunds settle in minutes."
    assert extract_section(ARTICLE, "Refund timelines > Nope") is None
    assert extract_section(ARTICLE, "refund timelines") == "Intro text."


def test_article_404_is_api_error():
    client, _ = make_client(lambda r: httpx.Response(404, json={"detail": "article not found"}))
    with pytest.raises(ApiError, match="article not found"):
        client.article_section("XXX-99", "x")
