"""Postgres persistence for tickets, classifications, drafts, citations, routing and reviews."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from rapidfuzz.distance import Levenshtein

from triagedesk.pii import mask_pii
from triagedesk.schemas import ReviewIn, TicketIn

DECISION_TO_STATUS = {"auto_send": "auto_send_eligible", "human_review": "pending_review", "escalate": "escalated"}
REVIEWABLE = {"auto_send_eligible", "pending_review", "escalated"}
LIGHT_EDIT_RATIO = 0.3  # edits changing <= 30% of characters count as "draft accepted"
ACTION_TO_STATUS = {"approve": "approved", "edit": "edited", "reject": "rejected"}


class ConflictError(Exception):
    pass


def create_ticket(conn: Connection, t: TicketIn, *, demo_mode: bool) -> tuple[UUID, bool]:
    """Insert a ticket; with an external_id this is idempotent. Returns (id, created)."""
    row = conn.execute(
        """INSERT INTO tickets (external_id, channel, customer_email, subject, body, demo_mode)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (external_id) DO NOTHING RETURNING id""",
        (t.external_id, t.channel, t.customer_email, t.subject, t.body, demo_mode),
    ).fetchone()
    if row:
        conn.commit()
        return row["id"], True
    existing = conn.execute("SELECT id FROM tickets WHERE external_id = %s", (t.external_id,)).fetchone()
    conn.commit()
    return existing["id"], False


def save_triage(conn: Connection, ticket_id: UUID, state: dict[str, Any], *, model: str, triage_ms: int) -> None:
    cls, meta = state["classification"], state["classify_meta"]
    routing = state["routing"]
    with conn.transaction():
        conn.execute(
            """UPDATE tickets SET clean_body = %s, masked_body = %s, language = %s, pii_types = %s,
                 status = %s, triage_ms = %s, triaged_at = now(), error = %s WHERE id = %s""",
            (
                state["clean_text"],
                state["masked_text"],
                state["language"],
                Jsonb(state["pii_types"]),
                DECISION_TO_STATUS[routing["decision"]],
                triage_ms,
                "; ".join(state.get("errors", [])) or None,
                ticket_id,
            ),
        )
        conn.execute(
            """INSERT INTO classifications (ticket_id, intent, secondary_intents, urgency, sentiment,
                 confidence, rationale, model, attempts, repaired, fallback)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                ticket_id,
                cls["intent"],
                Jsonb(cls["secondary_intents"]),
                cls["urgency"],
                cls["sentiment"],
                cls["confidence"],
                cls["rationale"],
                model,
                meta["attempts"],
                meta["repaired"],
                meta["fallback"],
            ),
        )
        draft, ver = state.get("draft"), state.get("verification")
        if draft:
            retrieved = [
                {
                    k: c[k]
                    for k in (
                        "chunk_id",
                        "article_id",
                        "title",
                        "url",
                        "heading",
                        "score",
                        "vector_rank",
                        "fts_rank",
                        "content",
                    )
                }
                for c in state.get("retrieved", [])
            ]
            draft_id = conn.execute(
                """INSERT INTO drafts (ticket_id, body, needs_escalation, escalation_reason, model, attempts,
                     retrieved, verified, grounding_score, issues)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    ticket_id,
                    draft.get("reply_rendered", draft["reply"]),
                    draft["needs_escalation"],
                    draft["escalation_reason"],
                    model,
                    state.get("draft_meta", {}).get("attempts", 1),
                    Jsonb(retrieved),
                    bool(ver and ver["passed"]),
                    ver["grounding_score"] if ver else 0.0,
                    Jsonb(ver["issues"] if ver else []),
                ),
            ).fetchone()["id"]
            for c in (ver or {}).get("citations", []):
                conn.execute(
                    """INSERT INTO citations (draft_id, article_id, url, in_retrieved, supported, support_score)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (draft_id, c["article_id"], c["url"], c["in_retrieved"], c["supported"], c["support_score"]),
                )
        conn.execute(
            """INSERT INTO routing_decisions (ticket_id, decision, team, reasons, policy_version)
               VALUES (%s, %s, %s, %s, %s)""",
            (ticket_id, routing["decision"], routing["team"], Jsonb(routing["reasons"]), routing["policy_version"]),
        )


def mark_failed(conn: Connection, ticket_id: UUID, error: str) -> None:
    conn.execute("UPDATE tickets SET status = 'triage_failed', error = %s WHERE id = %s", (error[:2000], ticket_id))
    conn.commit()


_SUMMARY_SQL = """
SELECT t.id, t.external_id, t.channel, t.subject, t.status, t.language, t.demo_mode, t.created_at,
       t.triaged_at, t.resolved_at, c.intent, c.urgency, c.sentiment, c.confidence,
       r.decision, r.team
FROM tickets t
LEFT JOIN LATERAL (SELECT * FROM classifications WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) c ON true
LEFT JOIN LATERAL (SELECT * FROM routing_decisions WHERE ticket_id = t.id ORDER BY id DESC LIMIT 1) r ON true
"""


def list_tickets(
    conn: Connection,
    *,
    status: str | None,
    intent: str | None,
    decision: str | None,
    limit: int,
    offset: int,
    urgency: str | None = None,
) -> list[dict[str, Any]]:
    clauses, params = [], []
    filters = (("t.status", status), ("c.intent", intent), ("r.decision", decision), ("c.urgency", urgency))
    for col, val in filters:
        if val:
            clauses.append(f"{col} = %s")
            params.append(val)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    # Most urgent first within the review queue, then oldest first.
    order = """ORDER BY CASE c.urgency WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END,
               t.created_at"""
    rows = conn.execute(f"{_SUMMARY_SQL} {where} {order} LIMIT %s OFFSET %s", (*params, limit, offset)).fetchall()
    conn.commit()
    for row in rows:  # the queue never shows raw PII
        row["subject"] = mask_pii(row["subject"] or "").text
    return rows


def get_ticket(conn: Connection, ticket_id: UUID) -> dict[str, Any] | None:
    t = conn.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
    if not t:
        conn.commit()
        return None
    t["classification"] = conn.execute(
        "SELECT * FROM classifications WHERE ticket_id = %s ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    draft = conn.execute("SELECT * FROM drafts WHERE ticket_id = %s ORDER BY id DESC LIMIT 1", (ticket_id,)).fetchone()
    if draft:
        draft["citations"] = conn.execute(
            "SELECT article_id, url, in_retrieved, supported, support_score FROM citations WHERE draft_id = %s "
            "ORDER BY id",
            (draft["id"],),
        ).fetchall()
    t["draft"] = draft
    t["routing"] = conn.execute(
        "SELECT * FROM routing_decisions WHERE ticket_id = %s ORDER BY id DESC LIMIT 1", (ticket_id,)
    ).fetchone()
    t["review"] = conn.execute("SELECT * FROM review_actions WHERE ticket_id = %s", (ticket_id,)).fetchone()
    t["events"] = conn.execute(
        "SELECT source, event, payload, created_at FROM ticket_events WHERE ticket_id = %s ORDER BY id", (ticket_id,)
    ).fetchall()
    conn.commit()
    return t


def record_review(
    conn: Connection, ticket_id: UUID, review: ReviewIn, *, now: datetime | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    with conn.transaction():
        t = conn.execute("SELECT status, created_at FROM tickets WHERE id = %s FOR UPDATE", (ticket_id,)).fetchone()
        if t is None:
            raise KeyError(str(ticket_id))
        if t["status"] not in REVIEWABLE:
            raise ConflictError(f"ticket is {t['status']}; it cannot be reviewed")
        draft = conn.execute(
            "SELECT id, body FROM drafts WHERE ticket_id = %s ORDER BY id DESC LIMIT 1", (ticket_id,)
        ).fetchone()
        draft_body = draft["body"] if draft else ""
        if review.action == "edit":
            if not review.final_body or not review.final_body.strip():
                raise ValueError("final_body is required for an edit")
            final = review.final_body
        elif review.action == "approve":
            if not draft:
                raise ValueError("there is no draft to approve; use edit with final_body")
            final = draft_body
        else:
            final = None
        distance = Levenshtein.distance(draft_body, final) if final is not None else None
        ratio = round(distance / max(len(draft_body), len(final), 1), 4) if final is not None else None
        handling = review.handling_seconds
        if handling is None and review.started_at is not None:
            started = review.started_at if review.started_at.tzinfo else review.started_at.replace(tzinfo=UTC)
            handling = max(0.0, (now - started).total_seconds())
        row = conn.execute(
            """INSERT INTO review_actions (ticket_id, draft_id, action, reviewer, final_body, reason, edit_distance,
                 edit_ratio, handling_seconds, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (
                ticket_id,
                draft["id"] if draft else None,
                review.action,
                review.reviewer,
                final,
                review.reason,
                distance,
                ratio,
                handling,
                now,
            ),
        ).fetchone()
        conn.execute(
            "UPDATE tickets SET status = %s, resolved_at = %s WHERE id = %s",
            (ACTION_TO_STATUS[review.action], now, ticket_id),
        )
    row["time_to_resolution_seconds"] = round((now - t["created_at"]).total_seconds(), 1)
    return row


def add_event(conn: Connection, ticket_id: UUID | None, source: str, event: str, payload: dict) -> int:
    row = conn.execute(
        "INSERT INTO ticket_events (ticket_id, source, event, payload) VALUES (%s, %s, %s, %s) RETURNING id",
        (ticket_id, source, event, Jsonb(payload)),
    ).fetchone()
    conn.commit()
    return row["id"]


def metrics(conn: Connection) -> dict[str, Any]:
    q = conn.execute
    out: dict[str, Any] = {}
    out["tickets_total"] = q("SELECT count(*) AS n FROM tickets").fetchone()["n"]
    out["by_status"] = {r["status"]: r["n"] for r in q("SELECT status, count(*) AS n FROM tickets GROUP BY 1")}
    out["triage_latency_ms"] = q(
        """SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY triage_ms) AS p50,
                  percentile_cont(0.95) WITHIN GROUP (ORDER BY triage_ms) AS p95
           FROM tickets WHERE triage_ms IS NOT NULL"""
    ).fetchone()
    per_intent = q(
        """WITH c AS (SELECT DISTINCT ON (ticket_id) * FROM classifications ORDER BY ticket_id, id DESC),
                r AS (SELECT DISTINCT ON (ticket_id) * FROM routing_decisions ORDER BY ticket_id, id DESC)
           SELECT c.intent, count(*) AS tickets, round(avg(c.confidence)::numeric, 3) AS avg_confidence,
                  count(*) FILTER (WHERE r.decision = 'auto_send') AS auto_send,
                  count(*) FILTER (WHERE r.decision = 'human_review') AS human_review,
                  count(*) FILTER (WHERE r.decision = 'escalate') AS escalate,
                  count(*) FILTER (WHERE ra.action = 'approve') AS approved,
                  count(*) FILTER (WHERE ra.action = 'edit') AS edited,
                  count(*) FILTER (WHERE ra.action = 'edit' AND ra.edit_ratio <= %(light)s) AS light_edits,
                  count(*) FILTER (WHERE ra.action = 'reject') AS rejected,
                  round(avg(ra.edit_ratio) FILTER (WHERE ra.action IN ('approve', 'edit'))::numeric, 3)
                    AS mean_edit_ratio,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY ra.handling_seconds) AS median_handling_s
           FROM c JOIN r USING (ticket_id) LEFT JOIN review_actions ra USING (ticket_id)
           GROUP BY c.intent ORDER BY tickets DESC""",
        {"light": LIGHT_EDIT_RATIO},
    ).fetchall()
    for row in per_intent:
        reviewed = row["approved"] + row["edited"] + row["rejected"]
        # A draft counts as accepted if approved as-is or sent after a light edit.
        accepted = row["approved"] + row["light_edits"]
        row["draft_acceptance_rate"] = round(accepted / reviewed, 3) if reviewed else None
        row["auto_send_rate"] = round(row["auto_send"] / row["tickets"], 3) if row["tickets"] else None
        for k in ("avg_confidence", "mean_edit_ratio"):
            row[k] = float(row[k]) if row[k] is not None else None
    out["per_intent"] = per_intent
    triaged = sum(r["tickets"] for r in per_intent)
    out["routing"] = {d: sum(r[d] for r in per_intent) for d in ("auto_send", "human_review", "escalate")}
    out["auto_send_rate"] = round(out["routing"]["auto_send"] / triaged, 3) if triaged else None
    out["reviews"] = q(
        """SELECT count(*) AS total,
                  count(*) FILTER (WHERE action = 'approve') AS approved,
                  count(*) FILTER (WHERE action = 'edit') AS edited,
                  count(*) FILTER (WHERE action = 'reject') AS rejected,
                  avg(edit_distance) FILTER (WHERE action = 'edit') AS mean_edit_distance,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY handling_seconds) AS median_handling_s,
                  percentile_cont(0.9) WITHIN GROUP (ORDER BY handling_seconds) AS p90_handling_s
           FROM review_actions"""
    ).fetchone()
    out["handling_seconds_by_action"] = q(
        """SELECT action, count(*) AS n, avg(handling_seconds) AS mean_s,
                  percentile_cont(0.5) WITHIN GROUP (ORDER BY handling_seconds) AS median_s
           FROM review_actions WHERE handling_seconds IS NOT NULL GROUP BY action"""
    ).fetchall()
    out["citations"] = q(
        """SELECT count(*) AS total, count(*) FILTER (WHERE in_retrieved) AS valid,
                  count(*) FILTER (WHERE supported) AS supported FROM citations"""
    ).fetchone()
    out["drafts"] = q(
        """SELECT count(*) AS total, count(*) FILTER (WHERE verified) AS verified,
                  avg(grounding_score) AS mean_grounding FROM drafts"""
    ).fetchone()
    conn.commit()
    return out
