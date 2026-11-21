"""The chat pipeline: rewrite -> retrieve -> build grounded prompt -> stream answer."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

from .config import settings
from .llm import get_chat
from .retrieval import search
from .schemas import ChatRequest

SYSTEM_PROMPT = """You are Helios Assistant, the internal knowledge assistant of Helios Dynamics.
Answer the employee's question using ONLY the numbered sources provided with the question.
- Cite every fact with its source number in square brackets, e.g. [1] or [2][3].
- If the sources do not contain the answer, say you don't know. Never invent facts or citations.
- When plans, tiers or options differ, explain the difference clearly (a short list or table is fine).
- Be concise and answer in the language of the question."""


def format_sources(sources: list[dict]) -> str:
    blocks = []
    for n, s in enumerate(sources, start=1):
        location = f", page {s['page']}" if s.get("page") else ""
        blocks.append(f"[{n}] {s['filename']}{location} | {s['heading']}\n{s['content']}")
    return "\n\n".join(blocks)


def chat_events(request: ChatRequest) -> Iterator[dict]:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    llm = get_chat()
    opts = request.settings

    messages = [m.model_dump() for m in request.messages]
    question = messages[-1]["content"].strip()
    history = messages[:-1]

    search_query = question
    if opts.query_rewrite and history:
        t0 = time.perf_counter()
        search_query = llm.rewrite_query(history, question)
        timings["query_rewrite"] = round((time.perf_counter() - t0) * 1000, 1)

    sources, stats = search(
        search_query, mode=opts.mode, top_k=opts.top_k, candidates=opts.candidates, rrf_k=opts.rrf_k
    )
    timings.update(stats.timings_ms)

    prompt_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    prompt_messages += [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
    prompt_messages.append({
        "role": "user",
        "content": f"{question}\n\nSources:\n{format_sources(sources) if sources else '(no sources found)'}",
    })

    yield {
        "type": "thought",
        "data": {
            "question": question,
            "search_query": search_query,
            "keyword_query": stats.keyword_query,
            "mode": opts.mode,
            "top_k": opts.top_k,
            "candidates": opts.candidates,
            "rrf_k": opts.rrf_k,
            "vector_candidates": stats.vector_candidates,
            "keyword_candidates": stats.keyword_candidates,
            "chat_model": settings.active_chat_model,
            "embedding_model": settings.active_embedding_model,
            "prompt": prompt_messages,
        },
    }
    yield {"type": "sources", "data": sources}

    t0 = time.perf_counter()
    answer = ""
    if not sources:
        answer = "I couldn't find any relevant documents. Try uploading documents or rephrasing the question."
        yield {"type": "delta", "data": answer}
    else:
        for token in llm.stream(prompt_messages, opts.temperature, sources):
            answer += token
            yield {"type": "delta", "data": token}
    timings["generation"] = round((time.perf_counter() - t0) * 1000, 1)
    timings["total"] = round((time.perf_counter() - started) * 1000, 1)

    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 0 < int(n) <= len(sources)})
    yield {"type": "done", "data": {"timings_ms": timings, "cited": cited}}
