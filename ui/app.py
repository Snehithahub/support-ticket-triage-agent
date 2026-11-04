"""TriageDesk review console: queue, ticket review, metrics and a demo ticket form.

Run: API_URL=http://localhost:8401 streamlit run ui/app.py --server.port 8502
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import streamlit as st
from client import ApiError, ApiUnavailable, TriageClient
from helpers import (
    OPEN_STATUSES,
    RESOLVED_STATUSES,
    SLA_LABELS,
    SLA_TARGET_HOURS,
    filter_rows,
    fmt_duration,
    fmt_pct,
    humanize,
    parse_ts,
    queue_rows,
    review_rates,
    sla_state,
)


def api_url() -> str:
    return os.environ.get("API_URL", "http://localhost:8401")


try:
    TZ = ZoneInfo(os.environ.get("UI_TIMEZONE", "Asia/Kolkata"))
except ZoneInfoNotFoundError:
    TZ = ZoneInfo("UTC")

VIEWS = {"Open": OPEN_STATUSES, "Resolved": RESOLVED_STATUSES, "Triage failed": ("triage_failed",), "All": ()}
DECISION_LABELS = {
    "auto_send": ":green[auto send]",
    "human_review": ":orange[human review]",
    "escalate": ":red[escalate]",
}
SAMPLES = {
    "Refund not received": (
        "Refund not credited",
        "Hi team, I refunded order 4521 to my customer on 28 Oct but she says the money has not reached "
        "her card yet. How long do refunds take to show up? You can reach me on 98765 43210.",
    ),
    "Webhook signature failing": (
        "Webhook signature mismatch",
        "Our webhook endpoint rejects every event because signature verification fails. We compute an "
        "HMAC SHA256 of the request body with our webhook secret. What are we doing wrong?",
    ),
    "Settlement delayed (urgent)": (
        "URGENT: settlement not received",
        "Yesterday's settlement has still not hit our bank account and we have salaries to pay today. "
        "This is the second time this month. Please check immediately.",
    ),
}


@st.cache_resource
def get_client(base_url: str) -> TriageClient:
    return TriageClient(base_url)


@st.cache_data(ttl=600, show_spinner=False)
def cited_section(base_url: str, article_id: str, heading: str) -> str | None:
    return get_client(base_url).article_section(article_id, heading)


def local_time(value: str | None) -> str:
    ts = parse_ts(value)
    return ts.astimezone(TZ).strftime("%d %b %Y, %H:%M") if ts else "–"


# ---------------------------------------------------------------- sidebar


def sidebar(client: TriageClient) -> None:
    with st.sidebar:
        st.session_state.setdefault("reviewer", os.environ.get("REVIEWER_ID", ""))
        st.text_input("Reviewer ID", key="reviewer", max_chars=120, help="Recorded with every review action.")
        st.caption(f"API: `{client.base_url}`")
        try:
            health = client.health()
        except ApiError as exc:
            st.error(f"API unreachable. {exc}")
            return
        status = health.get("status", "unknown")
        summary = f"model `{health.get('llm_model', '?')}` · {health.get('kb_chunks', '?')} KB chunks"
        (st.success if status == "ok" else st.warning)(f"API {status} · {summary}")
        if health.get("demo_mode"):
            st.info(health.get("notice") or "Demo mode: fake LLM, outputs are not model generated.")


# ---------------------------------------------------------------- queue + detail


def fetch_queue(client: TriageClient, statuses: tuple[str, ...]) -> list[dict[str, Any]]:
    if not statuses:
        return client.list_tickets(limit=500)
    return [t for s in statuses for t in client.list_tickets(status=s, limit=500)]


def queue_page() -> None:
    client = get_client(api_url())
    st.title("Review queue")
    top = st.columns([1.2, 1.4, 1.6, 1.4, 0.6], vertical_alignment="bottom")
    st.session_state.setdefault("view", "Open")
    view = top[0].segmented_control("View", list(VIEWS), key="view") or "Open"
    rows = queue_rows(fetch_queue(client, VIEWS[view]), datetime.now(UTC))
    decisions = top[1].multiselect("Routing decision", sorted({r["decision"] for r in rows}), format_func=humanize)
    intents = top[2].multiselect("Intent", sorted({r["intent"] for r in rows}), format_func=humanize)
    urgencies = top[3].multiselect("Urgency", [u for u in SLA_TARGET_HOURS if any(r["urgency"] == u for r in rows)])
    if top[4].button("Refresh", width="stretch"):
        st.rerun()
    rows = filter_rows(rows, decisions=decisions, intents=intents, urgencies=urgencies)

    targets = ", ".join(f"{u} {h:g}h" for u, h in SLA_TARGET_HOURS.items())
    st.caption(f"{len(rows)} tickets, most urgent first. SLA targets (first response): {targets}.")
    if rows:
        df = pd.DataFrame(rows).drop(columns=["age_s"])
        event = st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key=f"queue-{st.session_state.get('queue_nonce', 0)}",
            column_order=[
                "sla",
                "age",
                "urgency",
                "intent",
                "confidence",
                "decision",
                "team",
                "status",
                "subject",
            ],
            column_config={
                "sla": st.column_config.TextColumn("SLA", width="small"),
                "age": st.column_config.TextColumn("Age", width="small"),
                "confidence": st.column_config.ProgressColumn(
                    "Confidence", min_value=0, max_value=1, format="%.2f", width="small"
                ),
                "subject": st.column_config.TextColumn("Subject", width="large"),
            },
        )
        if event.selection.rows:
            st.session_state.ticket_id = df.iloc[event.selection.rows[0]]["id"]
    else:
        st.info("No tickets match these filters.")

    ticket_id = st.session_state.get("ticket_id") or st.query_params.get("ticket")
    if ticket_id:
        st.query_params["ticket"] = ticket_id
        st.divider()
        ticket_detail(client, ticket_id)


def ticket_detail(client: TriageClient, ticket_id: str) -> None:
    try:
        t = client.get_ticket(ticket_id)
    except ApiError as exc:
        if isinstance(exc, ApiUnavailable):
            raise
        st.warning(f"Could not load ticket {ticket_id}: {exc}")
        return
    opened_at = st.session_state.setdefault("opened_at", {}).setdefault(ticket_id, datetime.now(UTC))
    cls, draft, routing = t.get("classification") or {}, t.get("draft"), t.get("routing") or {}
    state, age = sla_state({**t, "urgency": cls.get("urgency")}, datetime.now(UTC))

    head, close = st.columns([0.9, 0.1], vertical_alignment="bottom")
    head.subheader(t.get("subject") or "(no subject)")
    if close.button("Close", key="close-ticket"):
        st.session_state.pop("ticket_id", None)
        st.query_params.pop("ticket", None)
        st.session_state["queue_nonce"] = st.session_state.get("queue_nonce", 0) + 1
        st.rerun()
    st.markdown(
        f"`{ticket_id}` · {humanize(t['status'])} · via {t.get('channel')}"
        f" · created {local_time(t['created_at'])}"
        f" · age {fmt_duration(age)} · SLA {SLA_LABELS[state]}"
    )
    if t.get("notice"):
        st.info(t["notice"])
    if flash := st.session_state.pop(f"flash-{ticket_id}", None):
        st.success(flash)
    if t.get("error"):
        st.error(f"Pipeline error: {t['error']}")

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("##### Customer message (PII-masked)")
        with st.container(border=True):
            st.text(t.get("masked_body") or "Masked text unavailable: triage did not complete.")
        if t.get("pii_types"):
            st.caption("Masked: " + ", ".join(t["pii_types"]))
        render_draft(client, draft)
        render_review(client, t, draft, opened_at)
    with right:
        render_classification(cls)
        render_routing(routing)
        render_verification(draft)


def render_draft(client: TriageClient, draft: dict[str, Any] | None) -> None:
    st.markdown("##### Draft reply")
    if not draft:
        st.info("No draft was produced for this ticket.")
        return
    with st.container(border=True):
        st.markdown(draft["body"])
    if draft.get("needs_escalation"):
        st.warning(f"Drafter asked to escalate: {draft.get('escalation_reason') or 'no grounded answer'}")

    checks = {c["article_id"]: c for c in draft.get("citations") or []}
    retrieved = draft.get("retrieved") or []
    st.markdown("##### Sources")
    st.caption("Retrieved help-center chunks. Cited ones are marked; open one to read the passage.")
    for c in retrieved:
        check = checks.get(c["article_id"])
        mark = "cited" if check else "not cited"
        if check and not check["supported"]:
            mark = "cited, weak support"
        with st.expander(f"[{c['article_id']}] {c['heading']}  ·  {mark}  ·  score {c['score']:.3f}"):
            st.markdown(f"[Open {c['article_id']}: {c['title']}]({c['url']})")
            text = c.get("content")
            if text is None:
                try:
                    text = cited_section(client.base_url, c["article_id"], c["heading"])
                except ApiError as exc:
                    st.caption(f"Could not load the passage: {exc}")
            if text:
                st.text(text)
            if check:
                st.caption(
                    f"Citation check: supported={check['supported']}, support score {check['support_score']:.2f}"
                )
    for aid, check in checks.items():
        if not check["in_retrieved"]:
            st.error(f"[{aid}] is cited but was not among the retrieved sources (possible fabrication).")


def render_classification(cls: dict[str, Any]) -> None:
    st.markdown("##### Classification")
    if not cls:
        st.info("Not classified.")
        return
    a, b = st.columns(2)
    a.metric("Intent", humanize(cls["intent"]))
    b.metric("Confidence", f"{cls['confidence']:.2f}")
    a.metric("Urgency", cls["urgency"])
    b.metric("Sentiment", cls["sentiment"])
    if cls.get("secondary_intents"):
        st.caption("Also mentions: " + ", ".join(map(humanize, cls["secondary_intents"])))
    if cls.get("rationale"):
        st.caption(f"Rationale: {cls['rationale']}")
    flags = [f"{cls.get('attempts', 1)} attempt(s)"] + [f for f in ("repaired", "fallback") if cls.get(f)]
    st.caption(f"Model `{cls.get('model', '?')}` · " + " · ".join(flags))


def render_routing(routing: dict[str, Any]) -> None:
    st.markdown("##### Routing")
    if not routing:
        st.info("No routing decision.")
        return
    st.markdown(
        f"**{DECISION_LABELS.get(routing['decision'], routing['decision'])}** to team "
        f"`{routing['team']}` (policy {routing.get('policy_version', '?')})"
    )
    for reason in routing.get("reasons") or []:
        st.markdown(f"- {reason}")


def render_verification(draft: dict[str, Any] | None) -> None:
    st.markdown("##### Verification")
    if not draft:
        st.info("Nothing to verify.")
        return
    verdict = ":green[passed]" if draft.get("verified") else ":red[failed]"
    st.markdown(f"Grounding check **{verdict}** · grounding score {draft.get('grounding_score', 0):.2f}")
    for issue in draft.get("issues") or []:
        st.markdown(f"- {issue}")


def render_review(client: TriageClient, t: dict[str, Any], draft: dict[str, Any] | None, opened_at: datetime) -> None:
    st.markdown("##### Review")
    if review := t.get("review"):
        st.markdown(
            f"**{review['action']}** by `{review['reviewer']}` at {local_time(review['created_at'])}"
            f" · handling {fmt_duration(review.get('handling_seconds'))}"
            + (f" · edit ratio {review['edit_ratio']:.2f}" if review.get("edit_ratio") is not None else "")
        )
        if review.get("reason"):
            st.caption(f"Reason: {review['reason']}")
        if review.get("final_body"):
            with st.expander("Sent reply"):
                st.markdown(review["final_body"])
        return
    if t["status"] not in OPEN_STATUSES:
        st.info(f"This ticket is {humanize(t['status'])} and cannot be reviewed.")
        return
    reviewer = (st.session_state.get("reviewer") or "").strip()
    if not reviewer:
        st.warning("Enter your reviewer ID in the sidebar to review tickets.")
    st.caption(
        f"Opened in this console at {opened_at.astimezone(TZ):%H:%M:%S}; handling time is measured "
        "from then until you submit."
    )
    tid = str(t["id"])
    approve, edit, reject = st.tabs(["Approve", "Edit and approve", "Reject"])
    with approve:
        if st.button("Approve draft as is", type="primary", disabled=not (reviewer and draft), key=f"ap-{tid}"):
            submit_review(client, tid, opened_at, action="approve", reviewer=reviewer)
    with edit:
        text = st.text_area("Final reply", value=draft["body"] if draft else "", height=260, key=f"ed-{tid}")
        if st.button("Send edited reply", type="primary", disabled=not reviewer, key=f"eb-{tid}"):
            if not text.strip():
                st.error("The edited reply is empty.")
            else:
                submit_review(client, tid, opened_at, action="edit", reviewer=reviewer, final_body=text)
    with reject:
        reason = st.text_input("Reason", key=f"rr-{tid}", placeholder="e.g. wrong intent, needs ops investigation")
        if st.button("Reject draft", disabled=not reviewer, key=f"rb-{tid}"):
            submit_review(client, tid, opened_at, action="reject", reviewer=reviewer, reason=reason or None)


def submit_review(client: TriageClient, ticket_id: str, opened_at: datetime, **kwargs: Any) -> None:
    handling = (datetime.now(UTC) - opened_at).total_seconds()
    try:
        out = client.review(ticket_id, started_at=opened_at, handling_seconds=handling, **kwargs)
    except ApiUnavailable:
        raise
    except ApiError as exc:
        if exc.status_code == 409:
            st.warning(f"Someone already resolved this ticket: {exc.detail}")
        else:
            st.error(str(exc))
        return
    msg = f"Recorded **{kwargs['action']}** in {fmt_duration(handling)}."
    if warnings := out.get("citation_warnings"):
        msg += " Citation warnings on your edit: " + "; ".join(warnings)
    st.session_state[f"flash-{ticket_id}"] = msg
    st.session_state["opened_at"].pop(ticket_id, None)
    st.session_state["queue_nonce"] = st.session_state.get("queue_nonce", 0) + 1  # reset table selection
    st.rerun()


# ---------------------------------------------------------------- metrics


def metrics_page() -> None:
    m = get_client(api_url()).metrics()
    st.title("Metrics")
    if m.get("demo_mode"):
        st.info("Demo mode: these numbers come from the fake heuristic LLM, not a real model.")
    reviews = m.get("reviews") or {}
    rates = review_rates(reviews)
    k = st.columns(4)
    k[0].metric("Tickets", m.get("tickets_total", 0))
    k[1].metric("Auto-send eligible", fmt_pct(m.get("auto_send_rate")))
    k[2].metric("Reviewed", reviews.get("total", 0))
    k[3].metric(
        "Median handling time",
        fmt_duration(reviews.get("median_handling_s")),
        help=f"p90 {fmt_duration(reviews.get('p90_handling_s'))}",
    )
    k = st.columns(4)
    k[0].metric("Approved as is", fmt_pct(rates["approved"]))
    k[1].metric("Edited", fmt_pct(rates["edited"]))
    k[2].metric("Rejected", fmt_pct(rates["rejected"]))
    lat = m.get("triage_latency_ms") or {}
    p50, p95 = (lat.get(q) for q in ("p50", "p95"))
    k[3].metric(
        "Triage latency p50",
        "–" if p50 is None else f"{p50 / 1000:.1f}s",
        help="p95 " + ("–" if p95 is None else f"{p95 / 1000:.1f}s"),
    )

    per_intent = pd.DataFrame(m.get("per_intent") or [])
    if per_intent.empty:
        st.info("No triaged tickets yet. Submit one from the Test ticket page.")
        return
    a, b = st.columns(2)
    with a:
        st.markdown("##### Tickets by intent")
        st.bar_chart(
            per_intent.set_index("intent")["tickets"].sort_values(),
            horizontal=True,
            height=320,
            x_label="tickets",
            y_label="",
        )
    with b:
        st.markdown("##### Routing mix")
        routing = pd.Series(m.get("routing") or {}, name="tickets")
        st.bar_chart(routing, height=320, x_label="", y_label="tickets")
        total = routing.sum()
        st.caption(" · ".join(f"{humanize(d)} {n / total:.0%}" for d, n in routing.items()) if total else "")

    st.markdown("##### Per intent")
    st.dataframe(
        per_intent,
        hide_index=True,
        width="stretch",
        column_order=[
            "intent",
            "tickets",
            "avg_confidence",
            "auto_send",
            "human_review",
            "escalate",
            "approved",
            "edited",
            "light_edits",
            "rejected",
            "draft_acceptance_rate",
            "mean_edit_ratio",
            "median_handling_s",
        ],
        column_config={
            "avg_confidence": st.column_config.NumberColumn("avg conf", format="%.2f"),
            "draft_acceptance_rate": st.column_config.NumberColumn(
                "draft accepted", format="percent", help="Approved as is, or edited lightly (<= 30% changed)"
            ),
            "mean_edit_ratio": st.column_config.NumberColumn("mean edit ratio", format="%.2f"),
            "median_handling_s": st.column_config.NumberColumn("median handling (s)", format="%.0f"),
        },
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Handling time by action")
        st.dataframe(
            pd.DataFrame(m.get("handling_seconds_by_action") or []),
            hide_index=True,
            width="stretch",
            column_config={
                "mean_s": st.column_config.NumberColumn("mean (s)", format="%.1f"),
                "median_s": st.column_config.NumberColumn("median (s)", format="%.1f"),
            },
        )
    with c2:
        st.markdown("##### Draft quality")
        drafts, cites = m.get("drafts") or {}, m.get("citations") or {}
        n_cites = cites.get("total", 0)
        grounding = drafts.get("mean_grounding")
        st.markdown(
            "\n".join(
                [
                    f"- Drafts passing verification: {drafts.get('verified', 0)} of {drafts.get('total', 0)}",
                    f"- Mean grounding score: {'–' if grounding is None else f'{grounding:.2f}'}",
                    f"- Citations pointing at retrieved sources: {cites.get('valid', 0)} of {n_cites}",
                    f"- Citations supported by the cited passage: {cites.get('supported', 0)} of {n_cites}",
                ]
            )
        )
        st.caption("Policy version " + str(m.get("policy_version", "?")))


# ---------------------------------------------------------------- test ticket


def submit_page() -> None:
    client = get_client(api_url())
    st.title("Submit a test ticket")
    st.caption("Sends the ticket through the full triage pipeline, exactly as an inbound channel would.")
    sample = st.selectbox("Start from a sample", ["(blank)", *SAMPLES])
    subject, body = SAMPLES.get(sample, ("", ""))
    with st.form("new-ticket"):
        subject = st.text_input("Subject", value=subject, max_chars=500)
        body = st.text_area("Message", value=body, height=180, max_chars=20_000)
        c1, c2 = st.columns(2)
        channel = c1.selectbox("Channel", ["web", "email", "chat", "api"])
        email = c2.text_input("Customer email (optional)")
        sent = st.form_submit_button("Submit and triage", type="primary")
    if sent:
        if not body.strip():
            st.error("The message cannot be empty.")
            return
        try:
            with st.spinner("Triaging..."):
                t = client.create_ticket(
                    subject=subject,
                    body=body,
                    channel=channel,
                    customer_email=email or None,
                    idempotency_key=f"ui-{uuid.uuid4()}",
                )
        except ApiUnavailable:
            raise
        except ApiError as exc:
            st.error(str(exc))
            return
        st.session_state.created_ticket = t
    if t := st.session_state.get("created_ticket"):
        cls, routing = t.get("classification") or {}, t.get("routing") or {}
        st.success(
            f"Ticket `{t['id']}`: {humanize(cls.get('intent'))} (confidence "
            f"{cls.get('confidence', 0):.2f}), routed to "
            f"{DECISION_LABELS.get(routing.get('decision'), '–')}."
        )
        if st.button("Open it in the queue"):
            st.session_state.ticket_id = t["id"]
            st.session_state.view = "All"
            st.session_state.pop("created_ticket")
            st.switch_page(QUEUE)


# ---------------------------------------------------------------- main

QUEUE = st.Page(queue_page, title="Queue", default=True)
PAGES = [
    QUEUE,
    st.Page(metrics_page, title="Metrics", url_path="metrics"),
    st.Page(submit_page, title="Test ticket", url_path="submit"),
]


def render(page: Callable[[], None]) -> None:
    """Draw the sidebar, then the page; API failures become messages instead of tracebacks."""
    sidebar(get_client(api_url()))
    try:
        page()
    except ApiUnavailable as exc:
        st.error(f"The TriageDesk API is not reachable, so this page cannot load. {exc}")
        st.caption("Start it with `docker compose up` (or set API_URL), then retry.")
        st.button("Retry")
    except ApiError as exc:
        st.error(f"The API returned an error: {exc}")
        st.button("Retry")


if __name__ == "__main__":  # streamlit runs the entry script as __main__
    st.set_page_config(page_title="TriageDesk review console", layout="wide")
    render(st.navigation(PAGES).run)
