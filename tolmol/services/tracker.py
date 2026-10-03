"""Stores comparisons as listings + price snapshots and assembles the product page data."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from tolmol.db.models import listings as listings_table
from tolmol.db.models import price_snapshots, to_plain, tracked_products
from tolmol.db.session import get_engine
from tolmol.errors import NotFound
from tolmol.schemas import ProductIdentity
from tolmol.services.analysis import analyze
from tolmol.services.market import Listing

# Listings seen within this window of the latest comparison count as "current".
CURRENT_WINDOW = timedelta(minutes=15)


def _discount(listing: Dict[str, Any]) -> Optional[float]:
    price, mrp = listing.get("price"), listing.get("mrp")
    return round((mrp - price) / mrp * 100, 1) if price and mrp and mrp > price else None


def fresh_product_id(identity_key: str, max_age_hours: float) -> Optional[int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    with get_engine().connect() as conn:
        return conn.execute(
            select(tracked_products.c.id).where(
                tracked_products.c.identity_key == identity_key, tracked_products.c.last_compared_at >= cutoff
            )
        ).scalar()


def save_comparison(identity: ProductIdentity, found: List[Listing]) -> int:
    product_values = {
        "title": identity.title,
        "brand": identity.brand,
        "model_number": identity.model_number,
        "variant": identity.variant,
        "category": identity.category,
        "image_url": identity.image_url,
        "source_url": identity.source_url,
        "last_compared_at": func.now(),
    }
    with get_engine().begin() as conn:
        stmt = insert(tracked_products).values(identity_key=identity.identity_key(), **product_values)
        keep_known = {
            key: func.coalesce(getattr(stmt.excluded, key), tracked_products.c[key])
            for key in ("brand", "model_number", "variant", "category", "image_url", "source_url")
        }
        product_id = conn.execute(
            stmt.on_conflict_do_update(
                index_elements=["identity_key"],
                set_={"title": stmt.excluded.title, "last_compared_at": func.now(), **keep_known},
            ).returning(tracked_products.c.id)
        ).scalar_one()

        for listing in found:
            values = listing.model_dump()
            stmt = insert(listings_table).values(product_id=product_id, last_seen_at=func.now(), **values)
            listing_id = conn.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_listing_product_platform",
                    set_={**{key: stmt.excluded[key] for key in values}, "last_seen_at": func.now()},
                ).returning(listings_table.c.id)
            ).scalar_one()
            if listing.price is not None:
                conn.execute(
                    insert(price_snapshots).values(
                        listing_id=listing_id, price=listing.price, mrp=listing.mrp, in_stock=listing.in_stock
                    )
                )
    return product_id


def product_identity(product_id: int) -> ProductIdentity:
    with get_engine().connect() as conn:
        row = conn.execute(select(tracked_products).where(tracked_products.c.id == product_id)).mappings().first()
    if row is None:
        raise NotFound("Product not found.")
    return ProductIdentity(
        title=row["title"], brand=row["brand"], model_number=row["model_number"], variant=row["variant"],
        category=row["category"], image_url=row["image_url"], source_url=row["source_url"],
    )


def product_view(product_id: int, cached: bool = False) -> Dict[str, Any]:
    with get_engine().connect() as conn:
        product = conn.execute(select(tracked_products).where(tracked_products.c.id == product_id)).mappings().first()
        if product is None:
            raise NotFound("Product not found.")
        rows = conn.execute(
            select(listings_table).where(listings_table.c.product_id == product_id)
        ).mappings().all()
        history = conn.execute(
            select(listings_table.c.platform, price_snapshots.c.price, price_snapshots.c.captured_at)
            .join(listings_table, price_snapshots.c.listing_id == listings_table.c.id)
            .where(listings_table.c.product_id == product_id)
            .order_by(price_snapshots.c.captured_at)
        ).mappings().all()

    compared_at = product["last_compared_at"]
    current = []
    for row in rows:
        listing = to_plain(row)
        listing["current"] = compared_at is None or row["last_seen_at"] >= compared_at - CURRENT_WINDOW
        listing["discount_pct"] = _discount(listing)
        current.append(listing)
    current.sort(key=lambda l: (not l["current"], l["price"] is None, l["price"] or 0))

    return {
        "product": {
            **{k: product[k] for k in ("id", "title", "brand", "model_number", "variant", "category", "image_url", "source_url")},
            "last_compared_at": compared_at.isoformat() if compared_at else None,
            "tracking": True,
        },
        "listings": current,
        "analysis": analyze([l for l in current if l["current"]], [to_plain(h) for h in history]),
        "insights": {
            "ready": product["insights_ready_at"] is not None,
            "specs": product["specs"],
            "reviews": product["review_summary"],
            "sources": product["insight_sources"],
        },
        "cached": cached,
    }


def ephemeral_view(identity: ProductIdentity, found: List[Listing]) -> Dict[str, Any]:
    """The same page data without a database: today's comparison only, no history or chat."""
    now = datetime.now(timezone.utc).isoformat()
    current = [{**l.model_dump(), "current": True, "last_seen_at": now, "discount_pct": _discount(l.model_dump())} for l in found]
    history = [{"platform": l.platform, "price": l.price, "captured_at": now} for l in found if l.price]
    return {
        "product": {**identity.model_dump(include={"title", "brand", "model_number", "variant", "category", "image_url", "source_url"}),
                    "id": None, "last_compared_at": now, "tracking": False},
        "listings": current,
        "analysis": analyze(current, history),
        "insights": {"ready": False, "specs": None, "reviews": None, "sources": None},
        "cached": False,
    }


def recent_products(limit: int = 8) -> List[Dict[str, Any]]:
    best_price = (
        select(func.min(listings_table.c.price))
        .where(listings_table.c.product_id == tracked_products.c.id, listings_table.c.price.isnot(None))
        .scalar_subquery()
    )
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(
                tracked_products.c.id, tracked_products.c.title, tracked_products.c.image_url,
                tracked_products.c.category, tracked_products.c.last_compared_at, best_price.label("best_price"),
            )
            .where(tracked_products.c.last_compared_at.isnot(None))
            .order_by(tracked_products.c.last_compared_at.desc())
            .limit(limit)
        ).mappings().all()
    return [to_plain(row) for row in rows]


def stale_product_ids(limit: int, older_than_hours: float = 20) -> List[int]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    with get_engine().connect() as conn:
        return list(
            conn.execute(
                select(tracked_products.c.id)
                .where(tracked_products.c.last_compared_at < cutoff)
                .order_by(tracked_products.c.last_compared_at)
                .limit(limit)
            ).scalars()
        )
