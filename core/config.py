import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres")
    
    # Try reading HF_TOKEN first, then fall back to HUGGINGFACE_API_TOKEN
    HUGGINGFACE_API_TOKEN: str = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Local embedding model for the Vector Engine
    LOCAL_EMBEDDING_MODEL: str = os.getenv("LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
    # Max character threshold for link parsing (Setting a safe default of 10,000)
    MAX_SCRAPE_CHARS: int = int(os.getenv("MAX_SCRAPE_CHARS", 10000))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()