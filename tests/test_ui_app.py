"""Render the Streamlit console headlessly (AppTest) against a stub API speaking the real response shapes."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "ui" / "app.py")
TID = "6f1c2b9e-0d7a-4c43-9a51-1f0e2d3c4b5a"
CREATED = (datetime.now(UTC) - timedelta(minutes=50)).isoformat()

SUMMARY = {
    "id": TID,
    "external_id": None,
    "channel": "web",
    "subject": "Refund not credited",
    "status": "pending_review",
    "language": "en",
    "demo_mode": True,
    "created_at": CREATED,
    "triaged_at": CREATED,
    "resolved_at": None,
    "intent": "refunds",
    "urgency": "high",
    "sentiment": "neutral",
    "confidence": 0.82,
    "decision": "human_review",
    "team": "payments-ops",
}
DETAIL = {
    **{k: SUMMARY[k] for k in ("id", "channel", "subject", "status", "demo_mode", "created_at", "resolved_at")},
    "body": "RAW BODY with 9876543210",
    "masked_body": "Refund for order 4521 not received. Call me on [PHONE].",
    "pii_types": ["phone"],
    "error": None,
    "notice": "DEMO MODE: fake heuristic LLM.",
    "classification": {
        "intent": "refunds",
        "secondary_intents": [],
        "urgency": "high",
        "sentiment": "neutral",
        "confidence": 0.82,
        "rationale": "mentions refund",
        "model": "fake-heuristic",
        "attempts": 1,
        "repaired": False,
        "fallback": False,
    },
    "draft": {
        "id": 1,
        "body": "Refunds take 5-7 business days [REF-02](http://kb.test/kb/REF-02).",
        "needs_escalation": False,
        "escalation_reason": "",
        "verified": True,
        "grounding_score": 0.91,
        "issues": [],
        "retrieved": [
            {
                "chunk_id": 7,
                "article_id": "REF-02",
                "title": "Refund timelines",
                "url": "http://kb.test/kb/REF-02",
                "heading": "Refund timelines > How long refunds take",
                "score": 0.0312,
                "vector_rank": 1,
                "fts_rank": 2,
            }
        ],
        "citations": [
            {
                "article_id": "REF-02",
                "url": "http://kb.test/kb/REF-02",
                "in_retrieved": True,
                "supported": True,
                "support_score": 0.8,
            }
        ],
    },
    "routing": {
        "decision": "human_review",
        "team": "payments-ops",
        "policy_version": "2026-11-04",
        "reasons": ["refunds is money_movement; policy never auto-sends it"],
    },
    "review": None,
    "events": [],
}
METRICS = {
    "tickets_total": 1,
    "by_status": {"pending_review": 1},
    "triage_latency_ms": {"p50": 120.0, "p95": 300.0},
    "per_intent": [
        {
            "intent": "refunds",
            "tickets": 1,
            "avg_confidence": 0.82,
            "auto_send": 0,
            "human_review": 1,
            "escalate": 0,
            "approved": 0,
            "edited": 0,
            "light_edits": 0,
            "rejected": 0,
            "mean_edit_ratio": None,
            "median_handling_s": None,
            "draft_acceptance_rate": None,
            "auto_send_rate": 0.0,
        }
    ],
    "routing": {"auto_send": 0, "human_review": 1, "escalate": 0},
    "auto_send_rate": 0.0,
    "reviews": {
        "total": 0,
        "approved": 0,
        "edited": 0,
        "rejected": 0,
        "mean_edit_distance": None,
        "median_handling_s": None,
        "p90_handling_s": None,
    },
    "handling_seconds_by_action": [],
    "citations": {"total": 1, "valid": 1, "supported": 1},
    "drafts": {"total": 1, "verified": 1, "mean_grounding": 0.91},
    "demo_mode": True,
    "policy_version": "2026-11-04",
}
ARTICLE = "<html><body><h1>Refund timelines</h1><h2>How long refunds take</h2><p>Card refunds: 5-7 days.</p></body>"


class StubApi(BaseHTTPRequestHandler):
    reviews: ClassVar[list[dict]] = []

    def _send(self, code: int, body: object, ctype: str = "application/json") -> None:
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        routes = {
            "/health": {"status": "ok", "demo_mode": True, "llm_model": "fake", "kb_chunks": 40},
            "/tickets": {"items": [SUMMARY], "count": 1},
            f"/tickets/{TID}": DETAIL,
            "/metrics": METRICS,
        }
        if path in routes:
            self._send(200, routes[path])
        elif path.startswith("/kb/"):
            self._send(200, ARTICLE, "text/html")
        else:
            self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        StubApi.reviews.append(body)
        self._send(200, {"review": {"action": body["action"]}, "citation_warnings": []})

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def api_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    StubApi.reviews.clear()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


def run_app(monkeypatch: pytest.MonkeyPatch, url: str, ticket: str | None = None) -> AppTest:
    monkeypatch.setenv("API_URL", url)
    at = AppTest.from_file(APP, default_timeout=20)
    if ticket:
        at.query_params["ticket"] = ticket
    return at.run()


def all_text(at: AppTest) -> str:
    parts = [
        e.value
        for kind in ("markdown", "caption", "text", "info", "success", "warning", "error")
        for e in getattr(at, kind)
    ]
    return "\n".join(map(str, parts))


def test_queue_and_detail_render_masked_text_only(monkeypatch, api_url):
    at = run_app(monkeypatch, api_url, ticket=TID)
    assert not at.exception
    text = all_text(at)
    assert "Review queue" in [t.value for t in at.title]
    assert "[PHONE]" in text and "9876543210" not in text  # never shows the raw body
    assert "payments-ops" in text and "policy never auto-sends" in text
    assert "Card refunds: 5-7 days." in text  # cited passage pulled from /kb/REF-02
    assert any("REF-02" in e.label for e in at.expander)


def test_approve_posts_reviewer_and_handling_time(monkeypatch, api_url):
    at = run_app(monkeypatch, api_url, ticket=TID)
    at.sidebar.text_input[0].set_value("agent-7").run()
    at.button(key=f"ap-{TID}").click().run()
    assert not at.exception
    assert len(StubApi.reviews) == 1
    sent = StubApi.reviews[0]
    assert sent["action"] == "approve" and sent["reviewer"] == "agent-7"
    assert sent["handling_seconds"] >= 0 and "started_at" in sent


def test_edit_sends_final_body(monkeypatch, api_url):
    at = run_app(monkeypatch, api_url, ticket=TID)
    at.sidebar.text_input[0].set_value("agent-7").run()
    at.text_area(key=f"ed-{TID}").set_value("Edited reply [REF-02]").run()
    at.button(key=f"eb-{TID}").click().run()
    assert StubApi.reviews[-1] | {"handling_seconds": 0, "started_at": ""} == {
        "action": "edit",
        "reviewer": "agent-7",
        "final_body": "Edited reply [REF-02]",
        "handling_seconds": 0,
        "started_at": "",
    }


def test_review_buttons_disabled_without_reviewer(monkeypatch, api_url):
    at = run_app(monkeypatch, api_url, ticket=TID)
    assert at.button(key=f"ap-{TID}").disabled


def test_metrics_page_renders(monkeypatch, api_url):
    monkeypatch.setenv("API_URL", api_url)
    ui_dir = str(Path(APP).parent)
    script = f"import sys\nsys.path.insert(0, {ui_dir!r})\nimport app\napp.render(app.metrics_page)\n"
    at = AppTest.from_string(script, default_timeout=20).run()
    assert not at.exception
    assert "Metrics" in [t.value for t in at.title]
    assert any(m.label == "Tickets" and m.value == "1" for m in at.metric)
    assert "Mean grounding score: 0.91" in all_text(at)


def test_api_down_shows_error_instead_of_crashing(monkeypatch):
    at = run_app(monkeypatch, "http://127.0.0.1:9")
    assert not at.exception
    assert any("not reachable" in e.value for e in at.error)
