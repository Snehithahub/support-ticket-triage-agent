"""Thin HTTP client for the TriageDesk API, kept free of Streamlit so it can be unit-tested."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Literal

import httpx

ReviewAction = Literal["approve", "edit", "reject"]

_HEADING_TAG_RE = re.compile(r"<h([1-6])[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


class ApiError(Exception):
    """The API answered with an error status. `detail` is the server's message."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ApiUnavailable(ApiError):
    """The API could not be reached (connection refused, DNS failure, timeout)."""


def _error_detail(resp: httpx.Response) -> Any:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or resp.reason_phrase
    if isinstance(body, dict):
        return body.get("detail", body.get("error", body))
    return body


def _describe(detail: Any) -> str:
    if isinstance(detail, list):  # FastAPI validation errors
        return "; ".join(
            f"{'.'.join(map(str, d.get('loc', [])))}: {d.get('msg')}" for d in detail if isinstance(d, dict)
        ) or str(detail)
    if isinstance(detail, dict):
        return str(detail.get("detail") or detail.get("error") or detail)
    return str(detail)


class TriageClient:
    """Synchronous client. Pass `transport` (e.g. httpx.MockTransport) in tests."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        triage_timeout: float = 90.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.triage_timeout = triage_timeout
        # retries=2 only re-attempts failed connections, so it is safe for POSTs too.
        self._http = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=2),
            headers={"user-agent": "triagedesk-ui"},
        )

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, *, ok: tuple[int, ...] = (), **kwargs: Any) -> httpx.Response:
        try:
            resp = self._http.request(method, path, **kwargs)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ApiUnavailable(f"cannot reach the API at {self.base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise ApiUnavailable(f"the API at {self.base_url} timed out on {method} {path}") from exc
        except httpx.TransportError as exc:
            raise ApiUnavailable(f"network error talking to {self.base_url}: {exc}") from exc
        if resp.is_error and resp.status_code not in ok:
            detail = _error_detail(resp)
            raise ApiError(
                f"{method} {path} failed ({resp.status_code}): {_describe(detail)}",
                status_code=resp.status_code,
                detail=detail,
            )
        return resp

    def health(self) -> dict[str, Any]:
        # /health answers 503 with a JSON body when degraded; that is still useful status.
        return self._request("GET", "/health", ok=(503,)).json()

    def list_tickets(
        self,
        *,
        status: str | None = None,
        intent: str | None = None,
        decision: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params = {k: v for k, v in {"status": status, "intent": intent, "decision": decision}.items() if v}
        params |= {"limit": limit, "offset": offset}
        return self._request("GET", "/tickets", params=params).json()["items"]

    def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tickets/{ticket_id}").json()

    def review(
        self,
        ticket_id: str,
        *,
        action: ReviewAction,
        reviewer: str,
        final_body: str | None = None,
        reason: str | None = None,
        started_at: datetime | None = None,
        handling_seconds: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"action": action, "reviewer": reviewer}
        if final_body is not None:
            payload["final_body"] = final_body
        if reason:
            payload["reason"] = reason
        if started_at is not None:
            payload["started_at"] = started_at.isoformat()
        if handling_seconds is not None:
            payload["handling_seconds"] = round(max(0.0, handling_seconds), 2)
        return self._request("POST", f"/tickets/{ticket_id}/review", json=payload).json()

    def create_ticket(
        self,
        *,
        body: str,
        subject: str = "",
        channel: str = "web",
        customer_email: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"subject": subject, "body": body, "channel": channel}
        if customer_email:
            payload["customer_email"] = customer_email
        headers = {"idempotency-key": idempotency_key} if idempotency_key else {}
        return self._request("POST", "/tickets", json=payload, headers=headers, timeout=self.triage_timeout).json()

    def metrics(self) -> dict[str, Any]:
        return self._request("GET", "/metrics").json()

    def article_section(self, article_id: str, heading: str) -> str | None:
        """Plain text of the article section a retrieved chunk came from.

        `heading` is the chunk's heading path ("Title > Section > Sub"); the deepest
        heading is located in the rendered article and its text returned up to the next heading.
        """
        page = self._request("GET", f"/kb/{article_id}").text
        return extract_section(page, heading)


def extract_section(page_html: str, heading: str) -> str | None:
    target = _norm(heading.split(">")[-1])
    matches = list(_HEADING_TAG_RE.finditer(page_html))
    for i, m in enumerate(matches):
        if _norm(_TAG_RE.sub("", m.group(2))) != target:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else page_html.find("</body>")
        segment = page_html[m.end() : end if end != -1 else len(page_html)]
        segment = re.sub(r"</(p|li|tr|pre|h[1-6])>|<br\s*/?>", "\n", segment, flags=re.IGNORECASE)
        text = html.unescape(_TAG_RE.sub("", segment))
        return re.sub(r"\n{3,}", "\n\n", text).strip() or None
    return None


def _norm(s: str) -> str:
    return " ".join(html.unescape(s).split()).lower()
