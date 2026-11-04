"""PostgreSQL connection pool and schema management."""

from __future__ import annotations

import logging
from importlib.resources import files

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


def _configure(conn: Connection) -> None:
    register_vector(conn)


def schema_sql(dim: int) -> str:
    return files("triagedesk").joinpath("schema.sql").read_text().replace("{dim}", str(int(dim)))


def apply_schema(conninfo: str, dim: int) -> None:
    """Create the extension and tables. Fails loudly if the stored vector size differs."""
    import psycopg

    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(schema_sql(dim))
        row = conn.execute(
            "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'kb_chunks'::regclass AND attname = 'embedding'"
        ).fetchone()
        if row and row[0] != dim:
            raise RuntimeError(
                f"kb_chunks.embedding has dimension {row[0]} but EMBEDDINGS_DIM={dim}; "
                "drop the kb tables (or the volume) and re-ingest"
            )


def make_pool(conninfo: str, max_size: int = 10, open_timeout: float = 30.0) -> ConnectionPool:
    pool = ConnectionPool(
        conninfo,
        min_size=1,
        max_size=max_size,
        kwargs={"row_factory": dict_row, "autocommit": False},
        configure=_configure,
        open=False,
    )
    pool.open(wait=True, timeout=open_timeout)
    return pool
