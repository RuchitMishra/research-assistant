from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_api_key: str = "AQ.Ab8RN6KBTctvCD7E6LV2B5HZ2eHyUithYKn5MBqUByev__YDDg"
    tavily_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "kb"

    llm_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    chunk_size: int = 800
    chunk_overlap: int = 100
    max_upload_mb: int = 20
    top_k: int = 5
    max_retries: int = 1  # retrieval retry loops before web fallback


@lru_cache
def get_settings() -> Settings:
    return Settings()
