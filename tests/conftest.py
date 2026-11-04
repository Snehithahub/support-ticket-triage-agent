from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from triagedesk.chunking import chunk_article, load_articles
from triagedesk.config import Settings
from triagedesk.embeddings import HashEmbedder
from triagedesk.policy import AutomationPolicy
from triagedesk.retrieval import InMemoryHybridRetriever


class ScriptedLLM:
    """Returns queued responses in order; records every call."""

    demo = False
    model = "scripted"

    def __init__(self, responses: list[str | Exception]):
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages, *, json_mode=False):
        self.calls.append(messages)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(llm_provider="fake", embeddings_provider="hash", log_json=False, _env_file=None)


@pytest.fixture(scope="session")
def articles(settings):
    return load_articles(settings.kb_dir)


@pytest.fixture(scope="session")
def retriever(settings, articles):
    chunks = [c for a in articles for c in chunk_article(a)]
    return InMemoryHybridRetriever(articles, chunks, HashEmbedder(settings.embeddings_dim), settings.article_url)


@pytest.fixture(scope="session")
def policy(settings):
    return AutomationPolicy.load(settings.policy_path)


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """A Postgres+pgvector URL: TEST_DATABASE_URL if set (CI service), else a testcontainer."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        yield url
        return
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed and TEST_DATABASE_URL not set")
    try:
        container = PostgresContainer("pgvector/pgvector:pg16", driver=None)
        container.start()
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - no Docker
        pytest.skip(f"Docker not available for integration tests: {exc}")
    try:
        yield container.get_connection_url()
    finally:
        container.stop()
