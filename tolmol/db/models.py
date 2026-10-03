from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Mapping

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from tolmol.config import settings

metadata = MetaData()


def _created():
    return Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now())


# One row per real-world product (e.g. "Sony WH-1000XM5, Black"), shared by every store selling it.
tracked_products = Table(
    "tracked_products",
    metadata,
    Column("id", Integer, primary_key=True),
    # SHA-256 of brand + model number (+ variant), or of the normalized title when no model is known.
    Column("identity_key", CHAR(64), nullable=False, unique=True),
    Column("title", Text, nullable=False),
    Column("brand", Text),
    Column("model_number", Text),
    Column("variant", Text),
    Column("category", Text),
    Column("image_url", Text),
    Column("source_url", Text),
    Column("specs", JSONB),
    Column("review_summary", JSONB),
    Column("insight_sources", JSONB),
    Column("insights_ready_at", DateTime(timezone=True)),
    Column("last_compared_at", DateTime(timezone=True)),
    _created(),
)

# The product on one store. Stores without a verified product page link to their search page.
listings = Table(
    "listings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("product_id", Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False),
    Column("platform", String(40), nullable=False),
    Column("title", Text),
    Column("url", Text, nullable=False),
    Column("link_type", String(12), nullable=False),  # source | verified | search
    Column("match_score", Float),
    Column("variant_note", Text),
    Column("price", Numeric(12, 2)),
    Column("mrp", Numeric(12, 2)),
    Column("in_stock", Boolean),
    Column("rating", Numeric(3, 2)),
    Column("price_source", String(12), nullable=False),  # live (scraped) | search (Google)
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("product_id", "platform", name="uq_listing_product_platform"),
)

price_snapshots = Table(
    "price_snapshots",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("listing_id", Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False),
    Column("price", Numeric(12, 2), nullable=False),
    Column("mrp", Numeric(12, 2)),
    Column("in_stock", Boolean),
    Column("captured_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
Index("ix_snapshots_listing_time", price_snapshots.c.listing_id, price_snapshots.c.captured_at)

# Spec and review passages for chat: searched by meaning (pgvector) and by keyword (full-text).
product_chunks = Table(
    "product_chunks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("product_id", Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False),
    Column("kind", String(12), nullable=False),  # overview | spec | review
    Column("content", Text, nullable=False),
    Column("embedding", Vector(settings.EMBEDDING_DIM)),
    Column("tsv", TSVECTOR, Computed("to_tsvector('english', content)", persisted=True)),
)
Index("ix_chunks_product", product_chunks.c.product_id)
Index(
    "ix_chunks_embedding_hnsw",
    product_chunks.c.embedding,
    postgresql_using="hnsw",
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
Index("ix_chunks_tsv", product_chunks.c.tsv, postgresql_using="gin")

price_alerts = Table(
    "price_alerts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("product_id", Integer, ForeignKey("tracked_products.id", ondelete="CASCADE"), nullable=False),
    Column("email", Text, nullable=False),
    Column("target_price", Numeric(12, 2), nullable=False),
    Column("active", Boolean, nullable=False, server_default="true"),
    Column("triggered_at", DateTime(timezone=True)),
    _created(),
)

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False),
    Column("key_prefix", String(12), nullable=False),
    Column("key_hash", CHAR(64), nullable=False, unique=True),  # SHA-256; the key itself is never stored
    Column("daily_limit", Integer, nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("last_used_at", DateTime(timezone=True)),
    _created(),
)

search_logs = Table(
    "search_logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("kind", String(16), nullable=False),  # compare | search | photo | chat
    Column("query", Text),
    Column("product_id", Integer, ForeignKey("tracked_products.id", ondelete="SET NULL")),
    Column("success", Boolean, nullable=False),
    Column("detail", Text),
    Column("latency_ms", Integer),
    Column("api_key_id", Integer, ForeignKey("api_keys.id", ondelete="SET NULL")),
    Column("client_hash", CHAR(64)),
    _created(),
)
Index("ix_logs_created", search_logs.c.created_at)
Index("ix_logs_client", search_logs.c.client_hash, search_logs.c.created_at)
Index("ix_logs_key", search_logs.c.api_key_id, search_logs.c.created_at)


def to_plain(mapping: Mapping[str, Any]) -> Dict[str, Any]:
    """Converts a result row into JSON-friendly values (Decimal -> float, datetime -> ISO string)."""
    plain = {}
    for key, value in mapping.items():
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, datetime):
            value = value.isoformat()
        plain[key] = value
    return plain
