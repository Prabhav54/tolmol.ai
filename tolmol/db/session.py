from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from tolmol.config import settings
from tolmol.db.models import metadata
from tolmol.errors import DatabaseUnavailable
from tolmol.logger import get_logger

logger = get_logger(__name__)


def _normalize_url(raw_url: str):
    # Supabase hands out "postgres://" URLs, which SQLAlchemy no longer accepts.
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://"):]
    url = make_url(raw_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    return url


@lru_cache
def get_engine() -> Engine:
    url = _normalize_url(settings.DATABASE_URL)
    connect_args = {"connect_timeout": settings.DB_CONNECT_TIMEOUT}
    if url.host and "supabase" in url.host and "sslmode" not in url.query:
        connect_args["sslmode"] = "require"

    if settings.VERCEL:
        # Short-lived serverless invocations: let Supabase's pooler (port 6543) do the pooling.
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    return create_engine(
        url, pool_size=settings.DB_POOL_SIZE, pool_pre_ping=True, pool_recycle=300, connect_args=connect_args
    )


def init_db() -> None:
    """Enables pgvector and creates any missing tables and indexes."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        metadata.create_all(engine)
        _check_embedding_dimension(engine)
    except DatabaseUnavailable:
        raise
    except Exception as exc:
        raise DatabaseUnavailable(
            f"Could not initialise the database at {engine.url.render_as_string(hide_password=True)}: {exc}"
        ) from exc
    logger.info("Database ready.")


def _check_embedding_dimension(engine: Engine) -> None:
    with engine.connect() as conn:
        stored_dim = conn.execute(
            text(
                "SELECT a.atttypmod FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname = 'product_chunks' AND a.attname = 'embedding' "
                "AND c.relnamespace = current_schema()::regnamespace"
            )
        ).scalar()
    if stored_dim and stored_dim != settings.EMBEDDING_DIM:
        raise DatabaseUnavailable(
            f"product_chunks.embedding is vector({stored_dim}) but EMBEDDING_DIM={settings.EMBEDDING_DIM}."
        )
