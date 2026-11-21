from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class RetrievalSettings(BaseModel):
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    top_k: int = Field(5, ge=1, le=20)
    candidates: int = Field(20, ge=5, le=100)
    rrf_k: int = Field(60, ge=1, le=200)
    temperature: float = Field(0.2, ge=0, le=1.5)
    query_rewrite: bool = True


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    settings: RetrievalSettings = RetrievalSettings()


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["hybrid", "vector", "keyword"] = "hybrid"
    top_k: int = Field(5, ge=1, le=20)
    candidates: int = Field(20, ge=5, le=100)
    rrf_k: int = Field(60, ge=1, le=200)
