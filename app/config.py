from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # Any OpenAI-compatible endpoint works (OpenAI, Azure OpenAI v1, DeepSeek, Groq, Ollama, ...).
    # Leave the key empty to run in offline demo mode.
    openai_api_key: str = ""
    openai_base_url: str | None = None
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    upload_dir: Path = BASE_DIR / "data" / "uploads"
    sample_docs_dir: Path = BASE_DIR / "sample_data" / "documents"
    max_upload_mb: int = 20

    chunk_size: int = 900
    chunk_overlap: int = 150
    min_chunk_size: int = 250

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key.strip())

    @property
    def active_embedding_model(self) -> str:
        return self.embedding_model if self.llm_enabled else "local-hashing-v1"

    @property
    def active_chat_model(self) -> str:
        return self.chat_model if self.llm_enabled else "offline-extractive"


settings = Settings()
