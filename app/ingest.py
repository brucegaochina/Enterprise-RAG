"""Upload handling and the ingestion pipeline: parse -> chunk -> embed -> index."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .chunking import chunk_text
from .config import settings
from .db import pool
from .embeddings import get_embedder
from .parsing import SUPPORTED_TYPES, parse_file

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingest")


class UploadError(ValueError):
    pass


def safe_display_name(name: str) -> str:
    """Keep only the base name of a client-supplied filename, for display purposes.
    It is never used to build a filesystem path."""
    name = re.split(r"[\\/]", name or "")[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()
    return name[:200] or "untitled"


def file_type_for(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED_TYPES:
        raise UploadError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_TYPES))}")
    return SUPPORTED_TYPES[ext]


def register_upload(filename: str, data: bytes) -> tuple[dict, bool]:
    """Store the file under a server-generated name and create the document row.
    Returns (document, created). Identical files are de-duplicated by SHA-256."""
    display_name = safe_display_name(filename)
    file_type = file_type_for(display_name)
    if not data:
        raise UploadError("File is empty")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadError(f"File is larger than {settings.max_upload_mb} MB")

    digest = hashlib.sha256(data).hexdigest()
    with pool().connection() as conn:
        existing = conn.execute(
            "SELECT id, filename, status FROM documents WHERE sha256 = %s", (digest,)
        ).fetchone()
        if existing:
            return existing, False

        doc_id = uuid.uuid4()
        stored_name = f"{doc_id}.{file_type}"
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        (settings.upload_dir / stored_name).write_bytes(data)

        row = conn.execute(
            """INSERT INTO documents (id, filename, file_type, stored_name, sha256, size_bytes, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'queued')
               RETURNING id, filename, status""",
            (doc_id, display_name, file_type, stored_name, digest, len(data)),
        ).fetchone()
    return row, True


def enqueue(doc_ids: list[uuid.UUID]) -> None:
    for doc_id in doc_ids:
        _executor.submit(ingest_document, doc_id)


def _set_status(doc_id, status: str, **fields) -> None:
    assignments = ", ".join(f"{k} = %({k})s" for k in fields)
    sql = f"UPDATE documents SET status = %(status)s, updated_at = now(){', ' + assignments if assignments else ''} WHERE id = %(id)s"
    with pool().connection() as conn:
        conn.execute(sql, {"status": status, "id": doc_id, **fields})


def ingest_document(doc_id: uuid.UUID) -> None:
    started = time.perf_counter()
    try:
        with pool().connection() as conn:
            doc = conn.execute(
                "SELECT id, filename, file_type, stored_name FROM documents WHERE id = %s", (doc_id,)
            ).fetchone()
        if doc is None:
            return

        _set_status(doc_id, "parsing")
        parsed = parse_file(settings.upload_dir / doc["stored_name"], doc["file_type"])
        if not parsed.text.strip():
            raise ValueError("No extractable text found (scanned PDFs need OCR)")
        title = parsed.title or Path(doc["filename"]).stem.replace("_", " ")
        if title.isupper():
            title = title.title()

        _set_status(doc_id, "chunking", content=parsed.text, title=title, num_pages=parsed.num_pages)
        chunks = chunk_text(
            parsed.text,
            parsed.page_starts,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
            min_chunk=settings.min_chunk_size,
        )

        _set_status(doc_id, "embedding", num_chunks=len(chunks))
        embedder = get_embedder()
        # Prepend document title and section so each chunk is self-describing.
        vectors = embedder.embed([f"{title}\n{c.heading or ''}\n\n{c.content}" for c in chunks])

        with pool().connection() as conn, conn.transaction():
            conn.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO chunks (document_id, chunk_index, page, heading, content,
                                           start_char, end_char, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (doc_id, c.index, c.page,
                         f"{title} › {c.heading}" if c.heading and c.heading.lower() != title.lower() else title,
                         c.content, c.start_char, c.end_char, v)
                        for c, v in zip(chunks, vectors)
                    ],
                )
            conn.execute(
                """UPDATE documents SET status = 'ready', error = NULL, num_chunks = %s,
                          embedding_model = %s, processing_ms = %s, updated_at = now()
                   WHERE id = %s""",
                (len(chunks), embedder.name, int((time.perf_counter() - started) * 1000), doc_id),
            )
        log.info("Indexed %s (%d chunks)", doc["filename"], len(chunks))
    except Exception as exc:
        log.exception("Ingestion failed for document %s", doc_id)
        _set_status(doc_id, "failed", error=str(exc)[:500])


def load_sample_documents() -> tuple[int, int]:
    """Register the bundled sample documents. Returns (queued, skipped)."""
    queued, skipped = [], 0
    for path in sorted(settings.sample_docs_dir.iterdir()):
        if path.suffix.lower() not in SUPPORTED_TYPES:
            continue
        doc, created = register_upload(path.name, path.read_bytes())
        if created:
            queued.append(doc["id"])
        else:
            skipped += 1
    enqueue(queued)
    return len(queued), skipped


def resume_interrupted() -> int:
    """Re-queue documents left mid-pipeline by a previous shutdown."""
    with pool().connection() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM documents WHERE status IN ('queued', 'parsing', 'chunking', 'embedding')"
        ).fetchall()]
    enqueue(ids)
    return len(ids)


def reindex_all() -> int:
    with pool().connection() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM documents ORDER BY created_at").fetchall()]
        conn.execute("UPDATE documents SET status = 'queued', updated_at = now()")
    enqueue(ids)
    return len(ids)


def delete_document(doc_id: uuid.UUID) -> bool:
    with pool().connection() as conn:
        row = conn.execute("DELETE FROM documents WHERE id = %s RETURNING stored_name", (doc_id,)).fetchone()
    if row:
        (settings.upload_dir / row["stored_name"]).unlink(missing_ok=True)
    return row is not None


def delete_all() -> int:
    with pool().connection() as conn:
        rows = conn.execute("DELETE FROM documents RETURNING stored_name").fetchall()
    for row in rows:
        (settings.upload_dir / row["stored_name"]).unlink(missing_ok=True)
    return len(rows)
