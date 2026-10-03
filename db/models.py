from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Mapping

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    func,
)

from core.config import settings

metadata = MetaData()

products = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True),
    # SHA-256 of the normalized product URL: the deduplication key.
    Column("url_hash", CHAR(64), nullable=False, unique=True),
    Column("url", Text, nullable=False),
    Column("platform", String(50), nullable=False),
    Column("title", Text, nullable=False),
    Column("brand", Text),
    Column("category", Text),
    Column("description", Text),
    Column("price", Numeric(12, 2)),
    Column("currency", String(8), nullable=False, server_default="INR"),
    Column("rating", Numeric(3, 2)),
    Column("rating_count", Integer),
    Column("image_url", Text),
    Column("in_stock", Boolean),
    # SHA-256 of the embedded text, so unchanged products are never re-embedded.
    Column("content_hash", CHAR(64)),
    Column("embedding", Vector(settings.EMBEDDING_DIM)),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

Index(
    "ix_products_embedding_hnsw",
    products.c.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_cosine_ops"},
)
Index("ix_products_price", products.c.price)
Index("ix_products_rating", products.c.rating)
Index("ix_products_platform", products.c.platform)
Index("ix_products_category", products.c.category)

price_history = Table(
    "price_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
    Column("price", Numeric(12, 2), nullable=False),
    Column("recorded_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

Index("ix_price_history_product", price_history.c.product_id, price_history.c.recorded_at)

# Columns returned to clients as a product card (everything except internal hashes and the vector).
CARD_COLUMNS = [
    products.c.id,
    products.c.title,
    products.c.brand,
    products.c.category,
    products.c.platform,
    products.c.price,
    products.c.currency,
    products.c.rating,
    products.c.rating_count,
    products.c.in_stock,
    products.c.url,
    products.c.image_url,
]


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
