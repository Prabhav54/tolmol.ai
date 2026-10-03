from functools import lru_cache
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database (Supabase PostgreSQL + pgvector) ---
    DATABASE_URL: str = "postgresql://user:password@localhost:5433/ecommerce_rag"
    DB_CONNECT_TIMEOUT: int = 10
    DB_POOL_SIZE: int = 5
    # Create tables on startup. Disable on serverless and call POST /api/admin/setup once instead.
    AUTO_INIT_DB: bool = True
    # Vercel sets VERCEL=1; serverless functions should not keep a connection pool.
    VERCEL: bool = False

    # --- AI providers ---
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY")
    )
    HUGGINGFACE_API_TOKEN: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("HUGGINGFACE_API_TOKEN", "HF_TOKEN")
    )
    # Model used to write chat answers: "gemini" or "huggingface" (LLaMA-3).
    LLM_PROVIDER: str = "gemini"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    # Model used with Google Search grounding to find listings, specs and reviews.
    GEMINI_SEARCH_MODEL: str = "gemini-2.5-flash"
    HF_CHAT_MODEL: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    EMBED_BATCH_SIZE: int = 100

    # --- Comparison ---
    SCRAPE_TIMEOUT: float = 8.0
    LINK_CHECK_TIMEOUT: float = 5.0
    # Re-use a comparison younger than this instead of searching again.
    COMPARE_CACHE_HOURS: float = 6.0

    # --- Chat retrieval ---
    CHAT_TOP_K: int = 6
    RERANK: bool = True

    # --- Access control ---
    ANON_HOURLY_LIMIT: int = 30
    DEFAULT_KEY_DAILY_LIMIT: int = 1000
    ADMIN_TOKEN: Optional[str] = None
    CORS_ORIGINS: List[str] = ["*"]

    # --- Daily refresh + price alerts ---
    CRON_SECRET: Optional[str] = None
    CRON_BATCH: int = 3
    RESEND_API_KEY: Optional[str] = None
    ALERT_FROM_EMAIL: str = "tolmol.ai <onboarding@resend.dev>"
    PUBLIC_BASE_URL: str = "https://tolmol-ai.vercel.app"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
