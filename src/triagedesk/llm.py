"""Minimal OpenAI-compatible chat client (Gemini, Groq, OpenAI, Azure OpenAI, custom).

One code path for every provider: POST {base_url}/chat/completions. Azure differs only in
URL shape and auth header. Retries with exponential backoff on 429/5xx/timeouts.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Protocol

import httpx

from triagedesk.config import Settings

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """The provider could not produce a completion (after retries)."""


class LLMClient(Protocol):
    model: str
    demo: bool

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str: ...


class OpenAICompatibleClient:
    demo = False

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        json_mode_supported: bool = True,
        azure_api_version: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: callable = time.sleep,  # type: ignore[valid-type]
    ) -> None:
        if not base_url or not model:
            raise ValueError("LLM_BASE_URL and LLM_MODEL are required for a real provider")
        self.model = model
        self.max_retries = max_retries
        self.json_mode_supported = json_mode_supported
        self._sleep = sleep
        if azure_api_version:
            self._url = (
                f"{base_url.rstrip('/')}/openai/deployments/{model}/chat/completions?api-version={azure_api_version}"
            )
            headers = {"api-key": api_key}
        else:
            self._url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
        self._http = httpx.Client(timeout=httpx.Timeout(timeout_s, connect=10.0), headers=headers, transport=transport)

    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        body: dict = {"model": self.model, "messages": messages, "temperature": 0.0}
        if json_mode and self.json_mode_supported:
            body["response_format"] = {"type": "json_object"}
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._http.post(self._url, json=body)
            except httpx.TimeoutException as exc:
                last_err = exc
            except httpx.TransportError as exc:
                last_err = exc
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()["choices"][0]["message"]["content"] or ""
                    except (KeyError, IndexError, ValueError) as exc:
                        raise LLMError(f"malformed provider response: {resp.text[:200]}") from exc
                if resp.status_code == 400 and "response_format" in body:
                    # Some models reject JSON mode; fall back to prompt-only JSON.
                    log.warning("provider rejected response_format; retrying without it")
                    body.pop("response_format")
                    self.json_mode_supported = False
                    continue
                if resp.status_code not in RETRYABLE_STATUS:
                    raise LLMError(f"provider returned {resp.status_code}: {resp.text[:300]}")
                last_err = LLMError(f"provider returned {resp.status_code}")
                retry_after = resp.headers.get("retry-after")
                if retry_after and retry_after.replace(".", "", 1).isdigit() and attempt < self.max_retries:
                    self._sleep(min(float(retry_after), 30.0))
                    continue
            if attempt < self.max_retries:
                delay = min(2**attempt, 16) * (0.5 + random.random() / 2)
                log.info("llm retry", extra={"attempt": attempt + 1, "delay_s": round(delay, 2)})
                self._sleep(delay)
        raise LLMError(f"LLM call failed after {self.max_retries + 1} attempts: {last_err}")


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "fake":
        from triagedesk.fake_llm import FakeLLM

        return FakeLLM()
    if settings.llm_api_key is None:
        raise ValueError(f"LLM_API_KEY is required for provider {settings.llm_provider!r}")
    return OpenAICompatibleClient(
        base_url=settings.llm_base_url or "",
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model or "",
        timeout_s=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
        json_mode_supported=settings.llm_json_mode,
        azure_api_version=settings.azure_api_version if settings.llm_provider == "azure" else None,
    )
