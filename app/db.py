import logging
import time
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

log = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def _configure(conn: psycopg.Connection) -> None:
    register_vector(conn)


def init_db(retries: int = 30) -> None:
    global _pool
    schema = (Path(__file__).parent / "schema.sql").read_text()
    schema = schema.replace("{dim}", str(int(settings.embedding_dim)))

    for attempt in range(1, retries + 1):
        try:
            with psycopg.connect(settings.database_url, autocommit=True) as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.execute(schema)
                dim = conn.execute(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'"
                ).fetchone()[0]
            break
        except psycopg.OperationalError:
            if attempt == retries:
                raise
            log.info("Waiting for database (%s/%s)...", attempt, retries)
            time.sleep(2)

    if dim != settings.embedding_dim:
        log.error(
            "chunks.embedding has %s dimensions but EMBEDDING_DIM=%s. "
            "Run `docker compose down -v` to reset the database.", dim, settings.embedding_dim,
        )

    _pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=10,
        configure=_configure,
        kwargs={"row_factory": dict_row},
        open=True,
    )


def pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database is not initialised")
    return _pool


def close_db() -> None:
    if _pool is not None:
        _pool.close()
