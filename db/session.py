from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from core.config import settings
from core.exceptions import DatabaseConnectionError
from core.logger import get_logger
from db.models import metadata

logger = get_logger(__name__)


def _normalize_url(raw_url: str):
    # Supabase and Render hand out "postgres://" URLs, which SQLAlchemy no longer accepts.
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
        # Each serverless invocation is short-lived; let Supabase's pooler (port 6543) do the pooling.
        return create_engine(url, poolclass=NullPool, connect_args=connect_args)
    return create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )


def init_db() -> None:
    """Enables pgvector and creates the catalog tables and indexes if they do not exist."""
    engine = get_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        metadata.create_all(engine)
        _check_existing_schema(engine)
    except DatabaseConnectionError:
        raise
    except Exception as exc:
        raise DatabaseConnectionError(
            f"Could not initialise the database at {engine.url.render_as_string(hide_password=True)}: {exc}"
        ) from exc
    logger.info("Database ready (pgvector enabled, catalog schema verified).")


def _check_existing_schema(engine: Engine) -> None:
    """create_all() skips tables that already exist, so catch tables left over from an older layout."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.relname, a.attname, a.atttypmod FROM pg_attribute a "
                "JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname IN ('products', 'price_history') AND c.relkind = 'r' "
                "AND c.relnamespace = current_schema()::regnamespace "
                "AND a.attnum > 0 AND NOT a.attisdropped"
            )
        ).fetchall()

    columns = {(table, column) for table, column, _ in rows}
    for table in metadata.sorted_tables:
        missing = [col.name for col in table.columns if (table.name, col.name) not in columns]
        if missing:
            raise DatabaseConnectionError(
                f"Table '{table.name}' exists with an older layout (missing columns: {', '.join(missing)}). "
                "Drop or rename the legacy tables (products, product_links, price_history) and restart."
            )

    stored_dim = next(
        (typmod for table, column, typmod in rows if (table, column) == ("products", "embedding")), None
    )
    if stored_dim and stored_dim != settings.EMBEDDING_DIM:
        raise DatabaseConnectionError(
            f"products.embedding is vector({stored_dim}) but EMBEDDING_DIM={settings.EMBEDDING_DIM}. "
            "Recreate the products table or set EMBEDDING_DIM to match."
        )
