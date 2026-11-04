"""Embedding providers: local fastembed (default), an OpenAI-compatible API, or a hashing
embedder for offline tests."""

from __future__ import annotations

import hashlib
import itertools
import math
from typing import Protocol

import httpx

from triagedesk.config import Settings
from triagedesk.text import content_tokens


class Embedder(Protocol):
    dim: int
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    def __init__(self, model: str = "BAAI/bge-small-en-v1.5", dim: int = 384, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model, cache_dir=cache_dir)
        self.dim = dim
        self.name = f"fastembed:{model}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts, batch_size=32)]

    def embed_query(self, text: str) -> list[float]:
        # query_embed applies the model's retrieval instruction prefix where one is defined.
        return next(iter(self._model.query_embed(text))).tolist()


class ApiEmbedder:
    """OpenAI-compatible /embeddings endpoint (OpenAI, Gemini's compatibility layer, etc.)."""

    def __init__(self, base_url: str, api_key: str, model: str, dim: int, timeout_s: float = 30.0):
        self.dim = dim
        self.name = f"api:{model}"
        self._model = model
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._http = httpx.Client(timeout=timeout_s, headers={"Authorization": f"Bearer {api_key}"})

    def _embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 64):
            resp = self._http.post(
                self._url, json={"model": self._model, "input": texts[i : i + 64], "dimensions": self.dim}
            )
            resp.raise_for_status()
            out.extend(d["embedding"] for d in sorted(resp.json()["data"], key=lambda d: d["index"]))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]


class HashEmbedder:
    """Deterministic bag-of-words feature hashing. Offline and fast; lexical only."""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.name = f"hash:{dim}"

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        toks = content_tokens(text)
        feats = toks + [f"{a} {b}" for a, b in itertools.pairwise(toks)]
        for f in feats:
            h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def build_embedder(settings: Settings) -> Embedder:
    if settings.embeddings_provider == "hash":
        return HashEmbedder(settings.embeddings_dim)
    if settings.embeddings_provider == "api":
        if settings.llm_api_key is None or not settings.llm_base_url:
            raise ValueError("EMBEDDINGS_PROVIDER=api needs LLM_BASE_URL and LLM_API_KEY")
        return ApiEmbedder(
            settings.llm_base_url,
            settings.llm_api_key.get_secret_value(),
            settings.embeddings_model,
            settings.embeddings_dim,
        )
    return FastEmbedEmbedder(settings.embeddings_model, settings.embeddings_dim, settings.embeddings_cache_dir)
