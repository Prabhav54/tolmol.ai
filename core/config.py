from functools import lru_cache
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend configuration, read from environment variables or a local `.env` file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database (Supabase PostgreSQL + pgvector) ---
    # Supabase exposes the session pooler / direct connection on 5432 and the
    # transaction pooler on 6543. Either works with psycopg2; 5432 is the safer default.
    DATABASE_URL: str = "postgresql://user:password@localhost:5433/ecommerce_rag"
    DB_CONNECT_TIMEOUT: int = 10
    DB_POOL_SIZE: int = 5
    # Create the extension, tables and indexes on startup. Disable on serverless hosts and run
    # `python -m scripts.init_db` once instead.
    AUTO_INIT_DB: bool = True
    # Vercel sets VERCEL=1; serverless functions should not hold a connection pool open.
    VERCEL: bool = False

    # --- API ---
    CORS_ORIGINS: List[str] = ["*"]
    # Enables /admin endpoints (send as the X-Admin-Token header). Unset = admin endpoints disabled.
    ADMIN_TOKEN: Optional[str] = None

    # --- Providers ---
    GOOGLE_API_KEY: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY")
    )
    HUGGINGFACE_API_TOKEN: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("HUGGINGFACE_API_TOKEN", "HF_TOKEN")
    )

    # "gemini" or "huggingface"
    LLM_PROVIDER: str = "gemini"
    GEMINI_CHAT_MODEL: str = "gemini-2.5-flash"
    HF_CHAT_MODEL: str = "meta-llama/Meta-Llama-3-8B-Instruct"

    # "gemini" or "huggingface". Changing the provider or dimension requires re-creating
    # the products table, since the vector column has a fixed size.
    EMBEDDING_PROVIDER: str = "gemini"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    HF_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 768

    # --- Retrieval ---
    SEARCH_TOP_K: int = 6
    # Semantic hits below this cosine similarity are treated as "not in the catalog".
    SEMANTIC_MIN_SIMILARITY: float = 0.3
    HNSW_EF_SEARCH: int = 40

    # --- Ingestion ---
    SCRAPE_TIMEOUT: float = 15.0
    MAX_SCRAPE_CHARS: int = 8000
    EMBED_BATCH_SIZE: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
