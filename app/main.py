import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import ingest
from .config import BASE_DIR, settings
from .db import close_db, init_db, pool
from .rag import chat_events
from .retrieval import search
from .schemas import ChatRequest, SearchRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("enterprise-rag")

STATIC_DIR = BASE_DIR / "static"
MEDIA_TYPES = {"pdf": "application/pdf", "md": "text/plain; charset=utf-8", "txt": "text/plain; charset=utf-8",
               "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
DOC_COLUMNS = """id, filename, title, file_type, size_bytes, status, error, num_pages, num_chunks,
                 embedding_model, processing_ms, created_at, updated_at"""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    if resumed := ingest.resume_interrupted():
        log.info("Resumed %d interrupted ingestion job(s)", resumed)
    log.info("LLM mode: %s | chat=%s | embeddings=%s",
             "online" if settings.llm_enabled else "offline demo",
             settings.active_chat_model, settings.active_embedding_model)
    yield
    close_db()


app = FastAPI(
    title="Enterprise RAG",
    description="Chat with enterprise documents: ingestion, hybrid retrieval (pgvector + full-text) and cited answers.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/api/health")
def health():
    with pool().connection() as conn:
        counts = conn.execute(
            """SELECT count(*) AS documents,
                      count(*) FILTER (WHERE status = 'ready') AS ready,
                      coalesce(sum(num_chunks) FILTER (WHERE status = 'ready'), 0) AS chunks,
                      count(*) FILTER (WHERE status = 'ready' AND embedding_model <> %s) AS stale
               FROM documents""",
            (settings.active_embedding_model,),
        ).fetchone()
    return {
        "status": "ok",
        "llm_enabled": settings.llm_enabled,
        "embeddings_enabled": settings.embeddings_enabled,
        "chat_model": settings.active_chat_model,
        "embedding_model": settings.active_embedding_model,
        "embedding_dim": settings.embedding_dim,
        **counts,
    }


# ---------------------------------------------------------------- documents

@app.get("/api/documents")
def list_documents():
    with pool().connection() as conn:
        return conn.execute(f"SELECT {DOC_COLUMNS} FROM documents ORDER BY filename").fetchall()


@app.post("/api/documents", status_code=201)
async def upload_documents(files: list[UploadFile] = File(...)):
    limit = settings.max_upload_mb * 1024 * 1024
    results, queued = [], []
    for upload in files:
        name = ingest.safe_display_name(upload.filename or "")
        try:
            data = await upload.read(limit + 1)
            doc, created = ingest.register_upload(name, data)
        except ingest.UploadError as exc:
            results.append({"filename": name, "status": "rejected", "error": str(exc)})
            continue
        if created:
            queued.append(doc["id"])
        results.append({"id": str(doc["id"]), "filename": doc["filename"],
                        "status": "queued" if created else "duplicate"})
    ingest.enqueue(queued)
    return {"results": results}


@app.post("/api/documents/sample")
def load_samples():
    queued, skipped = ingest.load_sample_documents()
    return {"queued": queued, "skipped": skipped}


@app.post("/api/documents/reindex")
def reindex():
    return {"queued": ingest.reindex_all()}


@app.delete("/api/documents")
def delete_all_documents():
    return {"deleted": ingest.delete_all()}


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: uuid.UUID):
    with pool().connection() as conn:
        doc = conn.execute(f"SELECT {DOC_COLUMNS}, content FROM documents WHERE id = %s", (doc_id,)).fetchone()
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc


@app.get("/api/documents/{doc_id}/chunks")
def get_chunks(doc_id: uuid.UUID):
    with pool().connection() as conn:
        return conn.execute(
            """SELECT id, chunk_index, page, heading, content, start_char, end_char,
                      length(content) AS chars
               FROM chunks WHERE document_id = %s ORDER BY chunk_index""",
            (doc_id,),
        ).fetchall()


@app.get("/api/documents/{doc_id}/file")
def get_document_file(doc_id: uuid.UUID):
    with pool().connection() as conn:
        doc = conn.execute(
            "SELECT filename, file_type, stored_name FROM documents WHERE id = %s", (doc_id,)
        ).fetchone()
    if doc is None:
        raise HTTPException(404, "Document not found")
    # stored_name is generated server-side (uuid + extension), never taken from the client.
    path = settings.upload_dir / doc["stored_name"]
    if not path.is_file():
        raise HTTPException(404, "File missing")
    disposition = "attachment" if doc["file_type"] == "docx" else "inline"
    return FileResponse(path, media_type=MEDIA_TYPES[doc["file_type"]], filename=doc["filename"],
                        content_disposition_type=disposition)


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: uuid.UUID):
    if not ingest.delete_document(doc_id):
        raise HTTPException(404, "Document not found")
    return {"deleted": 1}


# ---------------------------------------------------------------- retrieval & chat

@app.post("/api/search")
def search_chunks(body: SearchRequest):
    results, stats = search(body.query, mode=body.mode, top_k=body.top_k,
                            candidates=body.candidates, rrf_k=body.rrf_k)
    return {"results": results, "stats": stats.__dict__}


@app.post("/api/chat")
def chat(body: ChatRequest):
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must come from the user")

    def stream():
        try:
            for event in chat_events(body):
                yield json.dumps(event, default=str) + "\n"
        except Exception as exc:
            log.exception("Chat request failed")
            yield json.dumps({"type": "error", "data": f"{type(exc).__name__}: {exc}"[:500]}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
