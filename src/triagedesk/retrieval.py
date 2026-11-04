"""Hybrid retrieval: pgvector cosine similarity + Postgres full-text search, fused with RRF."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from psycopg_pool import ConnectionPool

from triagedesk.chunking import Article, Chunk
from triagedesk.embeddings import Embedder
from triagedesk.schemas import RetrievedChunk
from triagedesk.text import content_tokens

MAX_QUERY_TERMS = 64


class Retriever(Protocol):
    def search(
        self, query: str, *, category: str | None = None, top_k: int = 5, mode: str = "hybrid"
    ) -> list[RetrievedChunk]: ...


def rrf_fuse(rankings: Sequence[Sequence[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k + rank), rank starting at 1."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] = scores.get(doc, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


# OR-query built from Postgres's own parser, so query lexemes are normalised exactly like the
# indexed tsvector (identifiers such as payment.captured or X-Northwind-Signature survive).
# Ticket text is long, so AND semantics (plainto/websearch_to_tsquery) would match almost nothing.
# Lexemes are passed through quote_literal and cast, so no tsquery operators can be injected.
OR_TSQUERY_SQL = """
    SELECT (string_agg(quote_literal(lexeme), ' | ' ORDER BY pos))::tsquery AS q
    FROM (SELECT lexeme, positions[1] AS pos FROM unnest(to_tsvector('english', %(text)s))
          WHERE lexeme !~ '[\\\\]' ORDER BY positions[1] LIMIT %(max_terms)s) l
"""


def _dedupe_by_article(chunks: list[RetrievedChunk], top_k: int, max_per_article: int = 2) -> list[RetrievedChunk]:
    out: list[RetrievedChunk] = []
    per: Counter[str] = Counter()
    for c in chunks:
        if per[c.article_id] >= max_per_article:
            continue
        per[c.article_id] += 1
        out.append(c)
        if len(out) == top_k:
            break
    return out


class PgHybridRetriever:
    def __init__(
        self,
        pool: ConnectionPool,
        embedder: Embedder,
        *,
        candidates: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self.pool = pool
        self.embedder = embedder
        self.candidates = candidates
        self.rrf_k = rrf_k

    def _vector_ids(self, conn, qvec: list[float], category: str | None) -> list[int]:
        where = "WHERE category = %(cat)s" if category else ""
        rows = conn.execute(
            f"SELECT id FROM kb_chunks {where} ORDER BY embedding <=> %(q)s::vector LIMIT %(n)s",
            {"q": qvec, "cat": category, "n": self.candidates},
        ).fetchall()
        return [r["id"] for r in rows]

    def _fts_ids(self, conn, query: str, category: str | None) -> list[int]:
        cat = "AND category = %(cat)s" if category else ""
        rows = conn.execute(
            f"""WITH q AS ({OR_TSQUERY_SQL})
                SELECT id FROM kb_chunks, q
                WHERE q.q IS NOT NULL AND tsv @@ q.q {cat}
                ORDER BY ts_rank_cd(tsv, q.q, 32) DESC, id LIMIT %(n)s""",
            {"text": query, "max_terms": MAX_QUERY_TERMS, "cat": category, "n": self.candidates},
        ).fetchall()
        return [r["id"] for r in rows]

    def search(
        self, query: str, *, category: str | None = None, top_k: int = 5, mode: str = "hybrid"
    ) -> list[RetrievedChunk]:
        with self.pool.connection() as conn:
            vec_ids = self._vector_ids(conn, self.embedder.embed_query(query), category) if mode != "fts" else []
            fts_ids = self._fts_ids(conn, query, category) if mode != "vector" else []
            fused = rrf_fuse([r for r in (vec_ids, fts_ids) if r], k=self.rrf_k)
            if not fused:
                return []
            ids = [doc for doc, _ in fused]
            rows = conn.execute(
                """SELECT c.id, c.article_id, c.heading, c.category, c.content, a.title, a.url
                   FROM kb_chunks c JOIN kb_articles a ON a.id = c.article_id WHERE c.id = ANY(%s)""",
                (ids,),
            ).fetchall()
        by_id = {r["id"]: r for r in rows}
        vrank = {d: i for i, d in enumerate(vec_ids, 1)}
        frank = {d: i for i, d in enumerate(fts_ids, 1)}
        ranked = [
            RetrievedChunk(
                chunk_id=d,
                article_id=by_id[d]["article_id"],
                title=by_id[d]["title"],
                url=by_id[d]["url"],
                heading=by_id[d]["heading"],
                category=by_id[d]["category"],
                content=by_id[d]["content"],
                score=round(s, 6),
                vector_rank=vrank.get(d),
                fts_rank=frank.get(d),
            )
            for d, s in fused
            if d in by_id
        ]
        return _dedupe_by_article(ranked, top_k)


class InMemoryHybridRetriever:
    """Same fusion logic over an in-process index (BM25 + cosine). Used for tests and offline demos."""

    def __init__(
        self,
        articles: list[Article],
        chunks: list[Chunk],
        embedder: Embedder,
        url_for,
        *,
        candidates: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self.articles = {a.id: a for a in articles}
        self.chunks = chunks
        self.embedder = embedder
        self.url_for = url_for
        self.candidates = candidates
        self.rrf_k = rrf_k
        self.vectors = embedder.embed_documents([c.embedding_text for c in chunks])
        self.doc_tokens = [Counter(content_tokens(c.embedding_text)) for c in chunks]
        self.avgdl = sum(sum(t.values()) for t in self.doc_tokens) / max(len(chunks), 1)
        df: Counter[str] = Counter()
        for t in self.doc_tokens:
            df.update(t.keys())
        n = len(chunks)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def _bm25(self, i: int, q: list[str], k1: float = 1.2, b: float = 0.75) -> float:
        tf = self.doc_tokens[i]
        dl = sum(tf.values())
        return sum(
            self.idf.get(w, 0.0) * tf[w] * (k1 + 1) / (tf[w] + k1 * (1 - b + b * dl / self.avgdl)) for w in q if w in tf
        )

    def search(
        self, query: str, *, category: str | None = None, top_k: int = 5, mode: str = "hybrid"
    ) -> list[RetrievedChunk]:
        idx = [i for i, c in enumerate(self.chunks) if not category or self.articles[c.article_id].category == category]
        qv = self.embedder.embed_query(query)
        q = list(dict.fromkeys(content_tokens(query)))
        vec = sorted(idx, key=lambda i: -sum(a * b for a, b in zip(qv, self.vectors[i], strict=True)))
        lex = sorted((i for i in idx if self._bm25(i, q) > 0), key=lambda i: -self._bm25(i, q))
        lists = []
        if mode != "fts":
            lists.append(vec[: self.candidates])
        if mode != "vector":
            lists.append(lex[: self.candidates])
        vrank = {d: r for r, d in enumerate(vec[: self.candidates], 1)}
        frank = {d: r for r, d in enumerate(lex[: self.candidates], 1)}
        out = []
        for i, s in rrf_fuse([lst for lst in lists if lst], k=self.rrf_k):
            c = self.chunks[i]
            a = self.articles[c.article_id]
            out.append(
                RetrievedChunk(
                    chunk_id=i,
                    article_id=a.id,
                    title=a.title,
                    url=self.url_for(a.id),
                    heading=c.heading,
                    category=a.category,
                    content=c.content,
                    score=round(s, 6),
                    vector_rank=vrank.get(i),
                    fts_rank=frank.get(i),
                )
            )
        return _dedupe_by_article(out, top_k)
