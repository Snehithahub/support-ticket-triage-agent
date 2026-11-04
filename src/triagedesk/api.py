"""FastAPI service: ingest and triage tickets, list/inspect them, record reviews, expose metrics."""

from __future__ import annotations

import html
import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import markdown as md
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg_pool import ConnectionPool

from triagedesk import __version__, store
from triagedesk.config import Settings, get_settings
from triagedesk.db import apply_schema, make_pool
from triagedesk.embeddings import Embedder, build_embedder
from triagedesk.graph import TriageDeps, build_graph, run_triage
from triagedesk.llm import LLMClient, build_llm
from triagedesk.logging_setup import configure_logging, request_id_var
from triagedesk.pii import mask_pii
from triagedesk.policy import AutomationPolicy
from triagedesk.retrieval import PgHybridRetriever
from triagedesk.schemas import EventIn, RetrievedChunk, ReviewIn, TicketIn
from triagedesk.verify import verify_draft

log = logging.getLogger(__name__)

DEMO_BANNER = "DEMO MODE: fake heuristic LLM (no model calls). Classifications and drafts are not LLM output."


@dataclass
class AppState:
    settings: Settings
    pool: ConnectionPool
    llm: LLMClient
    embedder: Embedder
    policy: AutomationPolicy
    graph: Any


def create_app(
    settings: Settings | None = None,
    *,
    llm: LLMClient | None = None,
    embedder: Embedder | None = None,
    auto_ingest: bool = True,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level, settings.log_json)
        emb = embedder or build_embedder(settings)
        apply_schema(settings.database_url, emb.dim)
        if auto_ingest:
            from triagedesk.ingest import ingest

            stats = ingest(settings, emb)
            log.info("knowledge base ready", extra=stats)
        pool = make_pool(settings.database_url, settings.db_pool_max)
        client = llm or build_llm(settings)
        policy = AutomationPolicy.load(settings.policy_path)
        retriever = PgHybridRetriever(pool, emb, candidates=settings.retrieval_candidates, rrf_k=settings.rrf_k)
        graph = build_graph(TriageDeps(client, retriever, policy, settings))
        app.state.s = AppState(settings, pool, client, emb, policy, graph)
        if client.demo:
            log.warning(DEMO_BANNER)
        log.info(
            "api started", extra={"llm_provider": settings.llm_provider, "model": client.model, "embedder": emb.name}
        )
        try:
            yield
        finally:
            pool.close()

    app = FastAPI(
        title="TriageDesk",
        version=__version__,
        lifespan=lifespan,
        description="Support ticket triage agent for Northwind Pay merchant support.",
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = rid
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "request_id": rid,
                "ms": round((time.perf_counter() - t0) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": str(exc)[:300], "request_id": request_id_var.get()},
        )

    def st(request: Request) -> AppState:
        return request.app.state.s

    @app.get("/health")
    def health(request: Request, response: Response) -> dict:
        s = st(request)
        body: dict[str, Any] = {
            "status": "ok",
            "version": __version__,
            "demo_mode": s.llm.demo,
            "llm_provider": s.settings.llm_provider,
            "llm_model": s.llm.model,
            "embedder": s.embedder.name,
        }
        try:
            with s.pool.connection(timeout=5) as conn:
                body["kb_chunks"] = conn.execute("SELECT count(*) AS n FROM kb_chunks").fetchone()["n"]
            body["database"] = "ok"
        except Exception as exc:  # noqa: BLE001 - health must report, not raise
            body.update(status="degraded", database=f"error: {exc}"[:200])
            response.status_code = 503
        if body.get("kb_chunks") == 0:
            body["status"] = "degraded"
            response.status_code = 503
        if s.llm.demo:
            body["notice"] = DEMO_BANNER
        return body

    @app.post("/tickets", status_code=201)
    def create_ticket(
        ticket: TicketIn,
        request: Request,
        response: Response,
        idempotency_key: str | None = Header(default=None, max_length=200),
    ) -> dict:
        s = st(request)
        if idempotency_key and not ticket.external_id:
            ticket = ticket.model_copy(update={"external_id": idempotency_key})
        with s.pool.connection() as conn:
            ticket_id, created = store.create_ticket(conn, ticket, demo_mode=s.llm.demo)
        if not created:
            response.status_code = 200
            return _ticket_out(s, ticket_id, replay=True)
        t0 = time.perf_counter()
        try:
            state = run_triage(s.graph, ticket.subject, ticket.body)
        except Exception as exc:
            log.exception("triage failed", extra={"ticket_id": str(ticket_id)})
            with s.pool.connection() as conn:
                store.mark_failed(conn, ticket_id, str(exc))
            raise HTTPException(
                status_code=502,
                detail={"error": "triage_failed", "ticket_id": str(ticket_id), "detail": str(exc)[:300]},
            ) from exc
        triage_ms = int((time.perf_counter() - t0) * 1000)
        with s.pool.connection() as conn:
            store.save_triage(conn, ticket_id, state, model=s.llm.model, triage_ms=triage_ms)
        log.info(
            "ticket triaged",
            extra={
                "ticket_id": str(ticket_id),
                "intent": state["classification"]["intent"],
                "decision": state["routing"]["decision"],
                "ms": triage_ms,
            },
        )
        return _ticket_out(s, ticket_id, replay=False)

    @app.get("/tickets")
    def list_tickets(
        request: Request,
        status: str | None = None,
        intent: str | None = None,
        urgency: str | None = None,
        decision: str | None = None,
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ) -> dict:
        s = st(request)
        with s.pool.connection() as conn:
            rows = store.list_tickets(
                conn, status=status, intent=intent, decision=decision, urgency=urgency, limit=limit, offset=offset
            )
        return jsonable_encoder(
            {"items": rows, "count": len(rows), "limit": limit, "offset": offset, "demo_mode": s.llm.demo}
        )

    @app.get("/tickets/{ticket_id}")
    def get_ticket(
        ticket_id: UUID,
        request: Request,
        include_raw: bool = Query(default=False, description="Include the unmasked body and customer email"),
    ) -> dict:
        return _ticket_out(st(request), ticket_id, include_raw=include_raw)

    @app.post("/tickets/{ticket_id}/review")
    def review_ticket(ticket_id: UUID, review: ReviewIn, request: Request) -> dict:
        s = st(request)
        try:
            with s.pool.connection() as conn:
                row = store.record_review(conn, ticket_id, review)
                draft = conn.execute(
                    "SELECT retrieved FROM drafts WHERE ticket_id = %s ORDER BY id DESC LIMIT 1", (ticket_id,)
                ).fetchone()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="ticket not found") from exc
        except store.ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        warnings: list[str] = []
        if review.action == "edit" and draft:
            # Re-check citations in the edited text against what was retrieved for this ticket.
            with s.pool.connection() as conn:
                ids = [c["chunk_id"] for c in draft["retrieved"]]
                chunks = conn.execute(
                    """SELECT c.id AS chunk_id, c.article_id, a.title, a.url, c.heading, c.category, c.content,
                              0.0 AS score FROM kb_chunks c JOIN kb_articles a ON a.id = c.article_id
                       WHERE c.id = ANY(%s)""",
                    (ids,),
                ).fetchall()
                conn.commit()
            v = verify_draft(
                review.final_body or "",
                [RetrievedChunk.model_validate(c) for c in chunks],
                min_support=s.settings.grounding_min_support,
            )
            warnings = v.issues
        return jsonable_encoder({"review": row, "citation_warnings": warnings})

    @app.post("/tickets/{ticket_id}/events", status_code=201)
    def add_event(ticket_id: UUID, event: EventIn, request: Request) -> dict:
        s = st(request)
        with s.pool.connection() as conn:
            if not conn.execute("SELECT 1 FROM tickets WHERE id = %s", (ticket_id,)).fetchone():
                raise HTTPException(status_code=404, detail="ticket not found")
            event_id = store.add_event(conn, ticket_id, event.source, event.event, event.payload)
        return {"id": event_id}

    @app.get("/metrics")
    def metrics(request: Request) -> dict:
        s = st(request)
        with s.pool.connection() as conn:
            m = store.metrics(conn)
        m["demo_mode"] = s.llm.demo
        m["policy_version"] = s.policy.version
        return jsonable_encoder(m)

    @app.get("/policy")
    def policy(request: Request) -> dict:
        return st(request).policy.model_dump()

    @app.get("/kb")
    def kb_index(request: Request) -> dict:
        with st(request).pool.connection() as conn:
            rows = conn.execute("SELECT id, title, category, url FROM kb_articles ORDER BY id").fetchall()
            conn.commit()
        return {"items": rows}

    @app.get("/kb/{article_id}", response_class=HTMLResponse)
    def kb_article(article_id: str, request: Request) -> HTMLResponse:
        with st(request).pool.connection() as conn:
            a = conn.execute("SELECT id, title, body FROM kb_articles WHERE id = %s", (article_id,)).fetchone()
            conn.commit()
        if not a:
            raise HTTPException(status_code=404, detail="article not found")
        body_html = md.markdown(a["body"], extensions=["fenced_code", "tables"])
        return HTMLResponse(
            f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(a['title'])}</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;"
            "line-height:1.55}code,pre{background:#f3f3f3}pre{padding:.75rem;overflow:auto}"
            "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:.3rem .6rem}</style></head>"
            f"<body><p><small>Northwind Pay Help Center (fictional) &middot; {html.escape(a['id'])}</small></p>"
            f"{body_html}</body></html>"
        )

    return app


def _ticket_out(s: AppState, ticket_id: UUID, *, replay: bool | None = None, include_raw: bool = False) -> dict:
    with s.pool.connection() as conn:
        t = store.get_ticket(conn, ticket_id)
    if t is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    if not include_raw:
        # Raw text and contact details stay out of default responses; masked_body is the safe view.
        for key in ("body", "clean_body", "customer_email"):
            t.pop(key, None)
        t["subject"] = mask_pii(t["subject"] or "").text
    out = jsonable_encoder(t)
    if replay is not None:
        out["idempotent_replay"] = replay
    if t["demo_mode"]:
        out["notice"] = DEMO_BANNER
    return out


def main() -> None:
    import uvicorn

    uvicorn.run("triagedesk.api:create_app", factory=True, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
