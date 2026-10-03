from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, func, select

from db.models import CARD_COLUMNS, price_history, products, to_plain
from db.session import get_engine

router = APIRouter(prefix="/products", tags=["Catalog"])

PRICE_BUCKETS = [(0, 500), (500, 1000), (1000, 2000), (2000, 5000), (5000, 10000), (10000, 25000), (25000, None)]


@router.get("")
def list_products(
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
    platform: Optional[str] = None,
):
    stmt = select(*CARD_COLUMNS).order_by(products.c.updated_at.desc(), products.c.id.desc())
    count = select(func.count(products.c.id))
    if platform:
        stmt = stmt.where(products.c.platform == platform)
        count = count.where(products.c.platform == platform)
    with get_engine().connect() as conn:
        items = [to_plain(row) for row in conn.execute(stmt.limit(limit).offset(offset)).mappings()]
        total = conn.execute(count).scalar()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
def catalog_stats():
    """Dashboard numbers for operators: catalog size, platform/category mix, price and rating distribution."""
    bucket = case(
        *[
            ((products.c.price >= low) & (products.c.price < high), f"₹{low:,}–{high:,}")
            if high
            else (products.c.price >= low, f"₹{low:,}+")
            for low, high in PRICE_BUCKETS
        ],
        else_="Unknown",
    )
    bucket_order = {f"₹{low:,}–{high:,}" if high else f"₹{low:,}+": i for i, (low, high) in enumerate(PRICE_BUCKETS)}

    with get_engine().connect() as conn:
        totals = conn.execute(
            select(
                func.count(products.c.id).label("products"),
                func.count(products.c.embedding).label("embedded"),
                func.round(func.avg(products.c.price), 2).label("average_price"),
                func.round(func.avg(products.c.rating), 2).label("average_rating"),
                func.count(func.distinct(products.c.platform)).label("platforms"),
            )
        ).mappings().one()
        by_platform = conn.execute(
            select(
                products.c.platform,
                func.count(products.c.id).label("products"),
                func.round(func.avg(products.c.price), 2).label("average_price"),
                func.round(func.avg(products.c.rating), 2).label("average_rating"),
            )
            .group_by(products.c.platform)
            .order_by(func.count(products.c.id).desc())
        ).mappings().all()
        category = func.coalesce(products.c.category, "Uncategorized")
        by_category = conn.execute(
            select(category.label("category"), func.count(products.c.id).label("products"))
            .group_by(category)
            .order_by(func.count(products.c.id).desc())
            .limit(10)
        ).mappings().all()
        price_bands = conn.execute(
            select(bucket.label("band"), func.count(products.c.id).label("products"))
            .where(products.c.price.isnot(None))
            .group_by(bucket)
        ).mappings().all()
        price_points = conn.execute(select(func.count(price_history.c.id))).scalar()

    return {
        "totals": {**to_plain(totals), "price_points": price_points},
        "by_platform": [to_plain(row) for row in by_platform],
        "by_category": [to_plain(row) for row in by_category],
        "price_bands": sorted((to_plain(row) for row in price_bands), key=lambda r: bucket_order.get(r["band"], 99)),
    }


@router.get("/{product_id}")
def get_product(product_id: int):
    with get_engine().connect() as conn:
        product = conn.execute(
            select(*CARD_COLUMNS, products.c.description, products.c.created_at, products.c.updated_at).where(
                products.c.id == product_id
            )
        ).mappings().first()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        history = conn.execute(
            select(price_history.c.price, price_history.c.recorded_at)
            .where(price_history.c.product_id == product_id)
            .order_by(price_history.c.recorded_at)
        ).mappings().all()
    return {**to_plain(product), "price_history": [to_plain(row) for row in history]}
