"""Chat model access. Uses an OpenAI-compatible API when a key is configured,
otherwise falls back to a simple extractive answerer so the demo works offline."""

from __future__ import annotations

import math
import re
import time
from collections.abc import Iterator
from functools import lru_cache

from .config import settings
from .text_utils import keywords, stem

REWRITE_PROMPT = (
    "You rewrite the user's latest message into a standalone search query for an enterprise "
    "knowledge base (HR, IT, finance, security and product documents). Use the conversation to "
    "resolve pronouns and follow-ups such as 'how about hearing?'. Return only the query text."
)


class OpenAIChat:
    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.chat_model

    def rewrite_query(self, history: list[dict], question: str) -> str:
        transcript = "\n".join(f"{m['role']}: {m['content'][:600]}" for m in history[-6:])
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=80,
            messages=[
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": f"Conversation:\n{transcript}\n\nLatest message: {question}"},
            ],
        )
        return (response.choices[0].message.content or question).strip().strip('"')

    def stream(self, messages: list[dict], temperature: float, sources: list[dict]) -> Iterator[str]:
        response = self.client.chat.completions.create(
            model=self.model, temperature=temperature, messages=messages, stream=True
        )
        for event in response:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content


class OfflineChat:
    """Picks the sentences that best match the question from the top sources."""

    model = "offline-extractive"

    def rewrite_query(self, history: list[dict], question: str) -> str:
        previous = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        extra = [w for w in keywords(previous) if w not in keywords(question)]
        return f"{question} {' '.join(extra[:6])}".strip()

    def stream(self, messages: list[dict], temperature: float, sources: list[dict]) -> Iterator[str]:
        question = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        question = question.split("\n\nSources:", 1)[0]
        terms = {stem(w) for w in keywords(question)}
        min_score = max(1, math.ceil(len(terms) * 0.3))

        picked: list[str] = []
        for n, src in enumerate(sources[:3], start=1):
            # Drop heading-like lines, then re-join wrapped lines before splitting sentences.
            lines = [l for l in src["content"].splitlines()
                     if len(l.strip()) >= 60 or l.strip().endswith((".", ":", ";", "%"))]
            sentences = re.split(r"(?<=[.!?])\s+", " ".join(l.strip() for l in lines))
            scored = sorted(
                ((len(terms & {stem(w) for w in keywords(s)}), s) for s in sentences if len(s) > 25),
                key=lambda x: x[0], reverse=True,
            )
            picked += [f"- {s.strip()} [{n}]" for score, s in scored[:2] if score >= min_score]

        if picked:
            text = "Here is what I found in the documents:\n\n" + "\n".join(picked)
        else:
            text = "I couldn't find this in the indexed documents."
        text += ("\n\n_Offline demo mode: sentences are extracted verbatim from the top sources. "
                 "Add an API key in `.env` to generate answers with an LLM._")
        for token in re.findall(r"\S+\s*", text):
            time.sleep(0.012)
            yield token


@lru_cache(maxsize=1)
def get_chat():
    return OpenAIChat() if settings.llm_enabled else OfflineChat()
