"""Integration tests against real PostgreSQL + pgvector (testcontainers or TEST_DATABASE_URL)."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from triagedesk.api import create_app
from triagedesk.config import Settings
from triagedesk.db import make_pool
from triagedesk.embeddings import HashEmbedder
from triagedesk.fake_llm import FakeLLM
from triagedesk.ingest import ingest
from triagedesk.retrieval import PgHybridRetriever

pytestmark = pytest.mark.integration

WEBHOOK_TICKET = {
    "subject": "Webhook signature mismatch",
    "body": "Our endpoint rejects every event because the X-Northwind-Signature HMAC never matches. "
    "We compute it on the parsed JSON body. What are we doing wrong?",
    "channel": "email",
}
REFUND_TICKET = {"subject": "Refund ARN", "body": "Refund for pay_N3x9QbV2kL7mTz not received. Please share ARN."}


@pytest.fixture(scope="module")
def pg_settings(pg_url):
    s = Settings(database_url=pg_url, llm_provider="fake", embeddings_provider="hash", log_json=False, _env_file=None)
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    return s


@pytest.fixture(scope="module")
def client(pg_settings):
    app = create_app(pg_settings, llm=FakeLLM(), embedder=HashEmbedder(pg_settings.embeddings_dim))
    with TestClient(app) as c:
        yield c


def test_ingest_is_incremental(pg_settings, client):
    emb = HashEmbedder(pg_settings.embeddings_dim)
    stats = ingest(pg_settings, emb)  # the app already ingested on startup
    assert stats["updated"] == 0 and stats["unchanged"] == stats["articles"] >= 40
    assert stats["total_chunks"] > stats["articles"]


def test_pg_hybrid_retrieval(pg_settings, client):
    pool = make_pool(pg_settings.database_url, 2)
    try:
        r = PgHybridRetriever(pool, HashEmbedder(pg_settings.embeddings_dim))
        hits = r.search("webhook signature HMAC raw body mismatch", category="webhooks", top_k=5)
        assert hits[0].article_id == "WHK-02"
        assert all(h.category == "webhooks" for h in hits)
        assert any(h.vector_rank and h.fts_rank for h in hits)  # fused from both lists
        fts_only = r.search("chargeback evidence deadline", mode="fts", top_k=3)
        assert fts_only and all(h.vector_rank is None for h in fts_only)
        # identifiers survive query parsing exactly as at index time
        ids = [h.article_id for h in r.search("payment.captured not firing", mode="fts", top_k=5)]
        assert any(a.startswith("WHK") for a in ids)
        sig = r.search("X-Northwind-Signature", mode="fts", top_k=3)
        assert sig and sig[0].article_id.startswith("WHK")
        assert r.search("INSUFFICIENT_BALANCE on payout", mode="fts", top_k=5)
        # tsquery operators and quotes in user text must not break the query
        assert r.search("it's \\ back'slash '' & | !", mode="fts", top_k=3) is not None
        assert r.search("refund ' & | ! ( :* <->", top_k=3) is not None
    finally:
        pool.close()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["demo_mode"] and body["kb_chunks"] > 0
    assert "DEMO MODE" in body["notice"]


def test_create_triage_and_get(client):
    resp = client.post("/tickets", json=WEBHOOK_TICKET)
    assert resp.status_code == 201
    t = resp.json()
    assert t["status"] == "auto_send_eligible"
    assert t["classification"]["intent"] == "webhooks"
    assert t["routing"]["decision"] == "auto_send"
    assert t["draft"]["verified"] and t["draft"]["citations"]
    assert all(c["in_retrieved"] for c in t["draft"]["citations"])
    assert "DEMO MODE" in t["notice"]
    got = client.get(f"/tickets/{t['id']}").json()
    assert got["id"] == t["id"] and got["draft"]["body"] == t["draft"]["body"]
    assert all(r["content"] for r in got["draft"]["retrieved"])


def test_raw_pii_hidden_by_default(client):
    t = client.post(
        "/tickets",
        json={
            "subject": "Call me on 9876543210",
            "body": "Refund query, email me at a.b@shop.in",
            "customer_email": "a.b@shop.in",
            "external_id": "pii-1",
        },
    ).json()
    assert "body" not in t and "customer_email" not in t
    assert "9876543210" not in t["subject"] and "[PHONE_1]" in t["subject"]
    assert "a.b@shop.in" not in t["masked_body"]
    listed = client.get("/tickets", params={"limit": 500}).json()["items"]
    assert all("9876543210" not in i["subject"] for i in listed)
    raw = client.get(f"/tickets/{t['id']}", params={"include_raw": True}).json()
    assert raw["customer_email"] == "a.b@shop.in" and "a.b@shop.in" in raw["body"]
    assert client.get("/tickets", params={"urgency": "critical"}).status_code == 200


def test_idempotency_key(client):
    a = client.post("/tickets", json=REFUND_TICKET, headers={"Idempotency-Key": "ext-1"})
    b = client.post("/tickets", json=REFUND_TICKET, headers={"Idempotency-Key": "ext-1"})
    assert a.status_code == 201 and b.status_code == 200
    assert a.json()["id"] == b.json()["id"] and b.json()["idempotent_replay"] is True


def test_list_filters(client):
    items = client.get("/tickets", params={"decision": "human_review"}).json()["items"]
    assert items and all(i["decision"] == "human_review" for i in items)
    assert client.get("/tickets", params={"limit": 0}).status_code == 422


def test_review_edit_records_distance_and_time(client):
    tid = client.post("/tickets", json={**REFUND_TICKET, "external_id": "ext-2"}).json()["id"]
    started = (datetime.now(UTC) - timedelta(seconds=90)).isoformat()
    resp = client.post(
        f"/tickets/{tid}/review",
        json={
            "action": "edit",
            "reviewer": "asha",
            "started_at": started,
            "final_body": "Hi, refunds to UPI take 2-3 business days [REF-02]. Also see [ABC-01].",
        },
    )
    assert resp.status_code == 200, resp.text
    review = resp.json()["review"]
    assert review["edit_distance"] > 0 and 0 < review["edit_ratio"] <= 1
    assert 85 <= review["handling_seconds"] < 300
    assert any("ABC-01" in w for w in resp.json()["citation_warnings"])
    assert client.get(f"/tickets/{tid}").json()["status"] == "edited"
    # second review is a conflict
    again = client.post(f"/tickets/{tid}/review", json={"action": "approve", "reviewer": "b"})
    assert again.status_code == 409


def test_review_approve_and_reject(client):
    t1 = client.post("/tickets", json={**WEBHOOK_TICKET, "external_id": "ext-3"}).json()["id"]
    r1 = client.post(f"/tickets/{t1}/review", json={"action": "approve", "reviewer": "a", "handling_seconds": 42})
    assert r1.json()["review"]["edit_distance"] == 0 and r1.json()["review"]["handling_seconds"] == 42
    t2 = client.post("/tickets", json={**WEBHOOK_TICKET, "external_id": "ext-4"}).json()["id"]
    r2 = client.post(f"/tickets/{t2}/review", json={"action": "reject", "reviewer": "a", "reason": "wrong"})
    assert r2.json()["review"]["final_body"] is None


def test_review_validation_errors(client):
    tid = client.post("/tickets", json={**WEBHOOK_TICKET, "external_id": "ext-5"}).json()["id"]
    assert client.post(f"/tickets/{tid}/review", json={"action": "edit", "reviewer": "a"}).status_code == 422
    assert client.post(f"/tickets/{tid}/review", json={"action": "nope", "reviewer": "a"}).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/tickets/{missing}/review", json={"action": "approve", "reviewer": "a"}).status_code == 404
    assert client.get(f"/tickets/{missing}").status_code == 404
    assert client.get("/tickets/not-a-uuid").status_code == 422


def test_ticket_validation(client):
    assert client.post("/tickets", json={"body": ""}).status_code == 422
    assert client.post("/tickets", json={"body": "x", "unknown": 1}).status_code == 422
    assert client.post("/tickets", json={"body": "x" * 20_001}).status_code == 422


def test_events_and_metrics(client):
    tid = client.post("/tickets", json={**WEBHOOK_TICKET, "external_id": "ext-6"}).json()["id"]
    assert (
        client.post(
            f"/tickets/{tid}/events", json={"event": "reviewer_notified", "payload": {"via": "log"}}
        ).status_code
        == 201
    )
    assert client.get(f"/tickets/{tid}").json()["events"][0]["event"] == "reviewer_notified"
    m = client.get("/metrics").json()
    assert m["tickets_total"] >= 5 and m["demo_mode"] is True
    assert m["reviews"]["total"] >= 3
    assert m["citations"]["total"] >= m["citations"]["valid"] > 0
    intents = {r["intent"] for r in m["per_intent"]}
    assert {"webhooks", "refunds"} <= intents


def test_kb_article_page(client):
    r = client.get("/kb/WHK-02")
    assert r.status_code == 200 and "Verifying webhook signatures" in r.text
    assert client.get("/kb/NOPE-00").status_code == 404
