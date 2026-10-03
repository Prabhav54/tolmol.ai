"""Builds parameterized SQL from QueryFilters. User text only ever reaches the database as bound values."""

import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Select

from db.models import CARD_COLUMNS, products, to_plain
from db.session import get_engine
from engines.query_parser import QueryFilters, keyword_stems

AGGREGATE_LABELS = {
    "count": "product_count",
    "avg_price": "average_price",
    "min_price": "minimum_price",
    "max_price": "maximum_price",
    "avg_rating": "average_rating",
}

MAX_GROUPS = 50


def _aggregate_expression(aggregate: str):
    return {
        "count": func.count(products.c.id),
        "avg_price": func.round(func.avg(products.c.price), 2),
        "min_price": func.min(products.c.price),
        "max_price": func.max(products.c.price),
        "avg_rating": func.round(func.avg(products.c.rating), 2),
    }[aggregate]


def build_conditions(filters: QueryFilters) -> list:
    conditions = []
    if filters.min_price is not None:
        conditions.append(products.c.price >= filters.min_price)
    if filters.max_price is not None:
        conditions.append(products.c.price <= filters.max_price)
    if filters.min_rating is not None:
        conditions.append(products.c.rating >= filters.min_rating)
    if filters.max_rating is not None:
        conditions.append(products.c.rating <= filters.max_rating)
    if filters.platforms:
        conditions.append(products.c.platform.in_(filters.platforms))
    if filters.in_stock_only:
        conditions.append(products.c.in_stock.is_(True))

    stems = keyword_stems(filters.keywords)
    if stems:
        searchable = func.concat_ws(" ", products.c.title, products.c.brand, products.c.category, products.c.description)
        conditions.append(or_(*[searchable.ilike(f"%{stem}%") for stem in stems]))
    return conditions


def render_sql(stmt: Select) -> str:
    """Readable SQL for the UI. Values are shown inline here, but are executed as bound parameters."""
    dialect = postgresql.dialect()
    try:
        sql = str(stmt.compile(dialect=dialect, compile_kwargs={"literal_binds": True}))
    except Exception:
        # The query embedding has no literal form; show placeholders instead.
        sql = str(stmt.compile(dialect=dialect)).replace("%(", ":").replace(")s", "")
    # A 768-float literal is noise to a reader; show the embedding as a named parameter.
    sql = re.sub(r"'\[[-0-9.,eE ]{200,}\]'", ":query_embedding", sql)
    return sql.replace("%%", "%")


def search(
    filters: QueryFilters, query_vector: Optional[List[float]], limit: int
) -> Tuple[List[Dict[str, Any]], str]:
    """Exact relational filtering, ranked by an explicit sort or by semantic similarity to the leftover keywords."""
    conditions = build_conditions(filters)
    sort_columns = {
        "price_asc": products.c.price.asc().nulls_last(),
        "price_desc": products.c.price.desc().nulls_last(),
        "rating_desc": products.c.rating.desc().nulls_last(),
    }

    if query_vector is not None and not filters.sort:
        # Materialize the filtered rows first so the ranking is an exact scan over them,
        # rather than an approximate HNSW scan that could drop rows matching the filters.
        filtered = (
            select(*CARD_COLUMNS, products.c.embedding).where(*conditions).cte("filtered").prefix_with("MATERIALIZED")
        )
        distance = filtered.c.embedding.cosine_distance(query_vector)
        stmt = select(*[filtered.c[col.name] for col in CARD_COLUMNS], (1 - distance).label("similarity")).order_by(
            distance.asc().nulls_last()
        )
    else:
        order = sort_columns.get(filters.sort or "", products.c.rating.desc().nulls_last())
        stmt = select(*CARD_COLUMNS).where(*conditions).order_by(order, products.c.id)

    stmt = stmt.limit(limit)
    with get_engine().connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [to_plain(row) for row in rows], render_sql(stmt)


def aggregate(filters: QueryFilters) -> Tuple[List[Dict[str, Any]], str]:
    """Zero-touch analytics: COUNT / AVG / MIN / MAX, optionally grouped by platform, category or brand."""
    name = filters.aggregate or "count"
    expression = _aggregate_expression(name)
    columns = []
    group_expression = None
    if filters.group_by:
        group_expression = func.coalesce(products.c[filters.group_by], "Unknown")
        columns.append(group_expression.label(filters.group_by))
    columns.append(expression.label(AGGREGATE_LABELS[name]))
    if name != "count":
        columns.append(func.count(products.c.id).label("product_count"))

    stmt = select(*columns).where(*build_conditions(filters))
    if group_expression is not None:
        stmt = stmt.group_by(group_expression).order_by(expression.desc().nulls_last()).limit(MAX_GROUPS)

    with get_engine().connect() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [to_plain(row) for row in rows], render_sql(stmt)
