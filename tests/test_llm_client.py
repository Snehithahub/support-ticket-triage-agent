import httpx
import pytest

from triagedesk.config import Settings
from triagedesk.fake_llm import FakeLLM
from triagedesk.llm import LLMError, OpenAICompatibleClient, build_llm

OK = {"choices": [{"message": {"content": '{"ok": true}'}}]}


def client(handler, **kw):
    return OpenAICompatibleClient(
        base_url="https://llm.test/v1",
        api_key="k",
        model="m",
        transport=httpx.MockTransport(handler),
        sleep=lambda s: None,
        **kw,
    )


def test_success_sends_openai_shape():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"] = str(req.url)
        seen["auth"] = req.headers["authorization"]
        seen["body"] = req.read()
        return httpx.Response(200, json=OK)

    assert client(handler).chat([{"role": "user", "content": "hi"}], json_mode=True) == '{"ok": true}'
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k"
    assert b'"response_format"' in seen["body"]


def test_retries_on_429_and_5xx_then_succeeds():
    codes = iter([429, 503, 200])

    def handler(req):
        c = next(codes)
        return httpx.Response(c, json=OK if c == 200 else {"error": "x"}, headers={"retry-after": "1"})

    assert client(handler, max_retries=3).chat([{"role": "user", "content": "x"}]) == '{"ok": true}'


def test_gives_up_after_max_retries():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(LLMError, match="after 3 attempts"):
        client(handler, max_retries=2).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 3


def test_timeouts_are_retried():
    calls = []

    def handler(req):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(LLMError):
        client(handler, max_retries=1).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 2


def test_non_retryable_error_raises_immediately():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    with pytest.raises(LLMError, match="401"):
        client(handler).chat([{"role": "user", "content": "x"}])
    assert len(calls) == 1


def test_json_mode_rejected_falls_back_to_plain():
    bodies = []

    def handler(req):
        bodies.append(req.read())
        return (
            httpx.Response(400, text="response_format unsupported")
            if len(bodies) == 1
            else httpx.Response(200, json=OK)
        )

    c = client(handler)
    assert c.chat([{"role": "user", "content": "x"}], json_mode=True)
    assert b"response_format" not in bodies[1]


def test_azure_url_and_header():
    seen = {}

    def handler(req):
        seen["url"], seen["key"] = str(req.url), req.headers.get("api-key")
        return httpx.Response(200, json=OK)

    c = OpenAICompatibleClient(
        base_url="https://res.openai.azure.com",
        api_key="az",
        model="dep",
        azure_api_version="2024-10-21",
        transport=httpx.MockTransport(handler),
    )
    c.chat([{"role": "user", "content": "x"}])
    assert seen["url"] == "https://res.openai.azure.com/openai/deployments/dep/chat/completions?api-version=2024-10-21"
    assert seen["key"] == "az"


def test_presets_and_build():
    s = Settings(llm_provider="gemini", llm_api_key="x", _env_file=None)
    assert s.llm_base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert s.llm_model.startswith("gemini")
    assert Settings(llm_provider="groq", _env_file=None).llm_base_url == "https://api.groq.com/openai/v1"
    assert isinstance(build_llm(Settings(llm_provider="fake", _env_file=None)), FakeLLM)
    with pytest.raises(ValueError, match="LLM_API_KEY"):
        build_llm(Settings(llm_provider="groq", _env_file=None))
