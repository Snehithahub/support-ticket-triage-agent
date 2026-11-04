"""Ingest the markdown knowledge base into Postgres (chunks + embeddings).

Usage: python -m triagedesk.ingest [--kb-dir kb/articles] [--force]

Incremental: an article is re-chunked and re-embedded only when its content hash changed (or
the embedding model changed). Articles removed from disk are deleted from the index.
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from triagedesk.chunking import chunk_article, load_articles
from triagedesk.config import Settings, get_settings
from triagedesk.db import apply_schema
from triagedesk.embeddings import Embedder, build_embedder
from triagedesk.logging_setup import configure_logging

log = logging.getLogger(__name__)


def ingest(settings: Settings, embedder: Embedder, kb_dir: Path | None = None, force: bool = False) -> dict:
    t0 = time.perf_counter()
    apply_schema(settings.database_url, embedder.dim)
    articles = load_articles(kb_dir or settings.kb_dir)
    stats = {"articles": len(articles), "updated": 0, "unchanged": 0, "deleted": 0, "chunks_written": 0}
    with psycopg.connect(settings.database_url) as conn:
        register_vector(conn)
        meta = conn.execute("SELECT value FROM kb_meta WHERE key = 'embedder'").fetchone()
        if meta and meta[0] != embedder.name:
            log.info("embedder changed; re-embedding everything", extra={"old": meta[0], "new": embedder.name})
            force = True
        existing = dict(conn.execute("SELECT id, content_hash FROM kb_articles").fetchall())
        for article in articles:
            if not force and existing.get(article.id) == article.content_hash:
                stats["unchanged"] += 1
                continue
            chunks = chunk_article(article)
            vectors = embedder.embed_documents([c.embedding_text for c in chunks])
            with conn.transaction():
                conn.execute(
                    """INSERT INTO kb_articles (id, title, category, url, body, content_hash, updated)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, category = EXCLUDED.category,
                         url = EXCLUDED.url, body = EXCLUDED.body, content_hash = EXCLUDED.content_hash,
                         updated = EXCLUDED.updated, ingested_at = now()""",
                    (
                        article.id,
                        article.title,
                        article.category,
                        settings.article_url(article.id),
                        article.body,
                        article.content_hash,
                        article.updated,
                    ),
                )
                conn.execute("DELETE FROM kb_chunks WHERE article_id = %s", (article.id,))
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO kb_chunks (article_id, chunk_index, category, heading, content, embedding)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        [
                            (c.article_id, c.chunk_index, article.category, c.heading, c.content, v)
                            for c, v in zip(chunks, vectors, strict=True)
                        ],
                    )
            stats["updated"] += 1
            stats["chunks_written"] += len(chunks)
        stale = set(existing) - {a.id for a in articles}
        if stale:
            conn.execute("DELETE FROM kb_articles WHERE id = ANY(%s)", (list(stale),))
            stats["deleted"] = len(stale)
        conn.execute(
            "INSERT INTO kb_meta (key, value) VALUES ('embedder', %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (embedder.name,),
        )
        conn.commit()
        stats["total_chunks"] = conn.execute("SELECT count(*) FROM kb_chunks").fetchone()[0]
    stats["seconds"] = round(time.perf_counter() - t0, 2)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb-dir", type=Path, default=None)
    parser.add_argument("--force", action="store_true", help="re-embed every article")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stats = ingest(settings, build_embedder(settings), args.kb_dir, args.force)
    log.info("ingest complete", extra=stats)
    print(stats)


if __name__ == "__main__":
    main()
