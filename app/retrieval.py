"""Hybrid retrieval: pgvector cosine similarity + PostgreSQL full-text search,
fused with Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal

from .config import settings
from .db import pool
from .embeddings import get_embedder
from .text_utils import keywords

Mode = Literal["hybrid", "vector", "keyword"]

VECTOR_SQL = """
SELECT c.id, 1 - (c.embedding <=> %(emb)s) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE d.status = 'ready' AND d.embedding_model = %(model)s
ORDER BY c.embedding <=> %(emb)s
LIMIT %(n)s
"""

# OR-query over the question's keywords; ts_rank_cd normalisation 32 maps rank into [0, 1).
KEYWORD_SQL = """
SELECT c.id, ts_rank_cd(c.tsv, q, 32) AS score
FROM chunks c JOIN documents d ON d.id = c.document_id,
     to_tsquery('english', %(tsq)s) q
WHERE d.status = 'ready' AND c.tsv @@ q
ORDER BY score DESC
LIMIT %(n)s
"""

DETAILS_SQL = """
SELECT c.id, c.document_id, c.chunk_index, c.page, c.heading, c.content, c.start_char, c.end_char,
       d.filename, d.title, d.file_type
FROM chunks c JOIN documents d ON d.id = c.document_id
WHERE c.id = ANY(%(ids)s)
"""


@dataclass
class SearchStats:
    mode: str
    query: str
    keyword_query: str
    vector_candidates: int = 0
    keyword_candidates: int = 0
    timings_ms: dict[str, float] = field(default_factory=dict)


def search(
    query: str,
    mode: Mode = "hybrid",
    top_k: int = 5,
    candidates: int = 20,
    rrf_k: int = 60,
) -> tuple[list[dict], SearchStats]:
    terms = keywords(query)
    tsquery = " | ".join(terms)
    stats = SearchStats(mode=mode, query=query, keyword_query=tsquery)
    vec_hits: list[dict] = []
    kw_hits: list[dict] = []

    with pool().connection() as conn:
        if mode in ("hybrid", "vector"):
            t0 = time.perf_counter()
            emb = get_embedder().embed([query])[0]
            stats.timings_ms["embed_query"] = _ms(t0)
            t0 = time.perf_counter()
            vec_hits = conn.execute(
                VECTOR_SQL, {"emb": emb, "model": settings.active_embedding_model, "n": candidates}
            ).fetchall()
            stats.timings_ms["vector_search"] = _ms(t0)

        if mode in ("hybrid", "keyword") and tsquery:
            t0 = time.perf_counter()
            kw_hits = conn.execute(KEYWORD_SQL, {"tsq": tsquery, "n": candidates}).fetchall()
            stats.timings_ms["keyword_search"] = _ms(t0)

        stats.vector_candidates, stats.keyword_candidates = len(vec_hits), len(kw_hits)

        t0 = time.perf_counter()
        fused: dict[int, dict] = {}
        for rank, hit in enumerate(vec_hits, start=1):
            entry = fused.setdefault(hit["id"], {"id": hit["id"]})
            entry.update(vector_rank=rank, vector_score=float(hit["score"]))
        for rank, hit in enumerate(kw_hits, start=1):
            entry = fused.setdefault(hit["id"], {"id": hit["id"]})
            entry.update(keyword_rank=rank, keyword_score=float(hit["score"]))

        lists_used = (mode in ("hybrid", "vector")) + (mode in ("hybrid", "keyword"))
        best_possible = lists_used / (rrf_k + 1)
        for entry in fused.values():
            rrf = sum(1.0 / (rrf_k + entry[k]) for k in ("vector_rank", "keyword_rank") if k in entry)
            entry["rrf_score"] = rrf
            entry["relevance"] = rrf / best_possible if best_possible else 0.0

        ranked = sorted(fused.values(), key=lambda e: e["rrf_score"], reverse=True)[:top_k]
        stats.timings_ms["fusion"] = _ms(t0)

        if not ranked:
            return [], stats
        details = {
            row["id"]: row
            for row in conn.execute(DETAILS_SQL, {"ids": [e["id"] for e in ranked]}).fetchall()
        }

    results = []
    for position, entry in enumerate(ranked, start=1):
        row = details[entry["id"]]
        results.append({
            "rank": position,
            "chunk_id": row["id"],
            "document_id": str(row["document_id"]),
            "filename": row["filename"],
            "title": row["title"],
            "file_type": row["file_type"],
            "page": row["page"],
            "heading": row["heading"],
            "chunk_index": row["chunk_index"],
            "content": row["content"],
            "start_char": row["start_char"],
            "end_char": row["end_char"],
            "vector_rank": entry.get("vector_rank"),
            "vector_score": entry.get("vector_score"),
            "keyword_rank": entry.get("keyword_rank"),
            "keyword_score": entry.get("keyword_score"),
            "rrf_score": entry["rrf_score"],
            "relevance": round(entry["relevance"], 4),
        })
    return results, stats


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
