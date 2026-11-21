"""Embedding providers.

`OpenAIEmbedder` calls any OpenAI-compatible embeddings endpoint.
`HashingEmbedder` is a dependency-free fallback so the demo runs without an
API key: a signed feature-hashing bag of word unigrams and bigrams. It is a
lexical approximation, not a semantic model, and is labelled as such in the UI.
"""

from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from .config import settings
from .text_utils import STOPWORDS, stem


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[np.ndarray]: ...


class OpenAIEmbedder:
    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.name = settings.embedding_model

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        vectors: list[np.ndarray] = []
        extra = {"dimensions": settings.embedding_dim} if self.name.startswith("text-embedding-3") else {}
        for i in range(0, len(texts), 96):
            batch = [t.replace("\n", " ")[:8000] for t in texts[i:i + 96]]
            response = self.client.embeddings.create(model=self.name, input=batch, **extra)
            vectors.extend(np.asarray(item.embedding, dtype=np.float32) for item in response.data)
        return vectors


class HashingEmbedder:
    name = "local-hashing-v1"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _features(self, text: str) -> list[tuple[str, float]]:
        words = [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]
        feats = [(w, 1.0) for w in words]
        feats += [(f"{a}_{b}", 0.5) for a, b in zip(words, words[1:])]
        return feats

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat, weight in self._features(text):
            digest = hashlib.blake2b(feat.encode(), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign * weight
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 and math.isfinite(norm) else vec

    def embed(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vector(t) for t in texts]


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return OpenAIEmbedder() if settings.llm_enabled else HashingEmbedder(settings.embedding_dim)
