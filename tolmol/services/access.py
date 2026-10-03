"""API keys, rate limits, search logging and the operator insights they enable."""

import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from fastapi import Request
from sqlalchemy import Date, case, cast, func, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from tolmol.config import settings
from tolmol.db.models import api_keys, listings, search_logs, to_plain, tracked_products
from tolmol.db.session import get_engine
from tolmol.errors import RateLimited, TolmolError
from tolmol.logger import get_logger
from tolmol.scraping.urls import sha256_hex

logger = get_logger(__name__)


class InvalidApiKey(TolmolError):
    pass


@dataclass
class Client:
    api_key_id: Optional[int]
    client_hash: str
    name: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def identify_client(request: Request) -> Client:
    """Checks the X-API-Key header (if any) and enforces the caller's allowance."""
    client_hash = sha256_hex(f"{_client_ip(request)}|{settings.ADMIN_TOKEN or 'tolmol'}")
    raw_key = request.headers.get("x-api-key")
    try:
        with get_engine().connect() as conn:
            if raw_key:
                key = conn.execute(
                    select(api_keys.c.id, api_keys.c.name, api_keys.c.daily_limit).where(
                        api_keys.c.key_hash == sha256_hex(raw_key), api_keys.c.revoked_at.is_(None)
                    )
                ).mappings().first()
                if key is None:
                    raise InvalidApiKey("Invalid or revoked API key.")
                used = conn.execute(
                    select(func.count(search_logs.c.id)).where(
                        search_logs.c.api_key_id == key["id"],
                        search_logs.c.created_at >= datetime.now(timezone.utc) - timedelta(days=1),
                    )
                ).scalar()
                if used >= key["daily_limit"]:
                    raise RateLimited(f"Daily limit of {key['daily_limit']} requests reached for this API key.")
                return Client(key["id"], client_hash, key["name"])

            used = conn.execute(
                select(func.count(search_logs.c.id)).where(
                    search_logs.c.client_hash == client_hash,
                    search_logs.c.api_key_id.is_(None),
                    search_logs.c.created_at >= datetime.now(timezone.utc) - timedelta(hours=1),
                )
            ).scalar()
            if used >= settings.ANON_HOURLY_LIMIT:
                raise RateLimited("You've hit the hourly limit for free lookups. Try again later or use an API key.")
    except SQLAlchemyError as exc:
        # Without a database we can't count usage; serve the request rather than fail it.
        logger.warning(f"Rate limiting skipped (database unavailable): {exc.__class__.__name__}")
    return Client(None, client_hash, "anonymous")


@contextmanager
def logged(client: Client, kind: str, query: str) -> Iterator[Dict[str, Any]]:
    """Times a request and records it in search_logs; set entry['product_id'] inside the block."""
    entry: Dict[str, Any] = {"product_id": None}
    started = time.perf_counter()
    success, detail = False, None
    try:
        yield entry
        success = True
    except Exception as exc:
        detail = str(exc)[:500]
        raise
    finally:
        try:
            with get_engine().begin() as conn:
                conn.execute(
                    insert(search_logs).values(
                        kind=kind, query=query[:500], product_id=entry["product_id"], success=success, detail=detail,
                        latency_ms=int((time.perf_counter() - started) * 1000), api_key_id=client.api_key_id,
                        client_hash=client.client_hash,
                    )
                )
                if client.api_key_id:
                    conn.execute(update(api_keys).where(api_keys.c.id == client.api_key_id).values(last_used_at=func.now()))
        except SQLAlchemyError as exc:
            logger.warning(f"Could not write search log: {exc.__class__.__name__}")


def create_api_key(name: str, daily_limit: Optional[int]) -> Dict[str, Any]:
    raw = "tm_" + secrets.token_urlsafe(24)
    with get_engine().begin() as conn:
        key_id = conn.execute(
            insert(api_keys).values(
                name=name, key_prefix=raw[:10], key_hash=sha256_hex(raw),
                daily_limit=daily_limit or settings.DEFAULT_KEY_DAILY_LIMIT,
            ).returning(api_keys.c.id)
        ).scalar_one()
    return {"id": key_id, "name": name, "api_key": raw, "note": "Store this key now; it is not shown again."}


def list_api_keys() -> List[Dict[str, Any]]:
    usage = (
        select(func.count(search_logs.c.id))
        .where(search_logs.c.api_key_id == api_keys.c.id,
               search_logs.c.created_at >= datetime.now(timezone.utc) - timedelta(days=1))
        .scalar_subquery()
    )
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(api_keys.c.id, api_keys.c.name, api_keys.c.key_prefix, api_keys.c.daily_limit, api_keys.c.created_at,
                   api_keys.c.last_used_at, api_keys.c.revoked_at, usage.label("used_last_24h"))
            .order_by(api_keys.c.created_at.desc())
        ).mappings().all()
    return [to_plain(row) for row in rows]


def revoke_api_key(key_id: int) -> bool:
    with get_engine().begin() as conn:
        result = conn.execute(
            update(api_keys).where(api_keys.c.id == key_id, api_keys.c.revoked_at.is_(None)).values(revoked_at=func.now())
        )
    return result.rowcount > 0


def operator_insights(days: int = 30) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day = cast(search_logs.c.created_at, Date)
    with get_engine().connect() as conn:
        by_kind = conn.execute(
            select(search_logs.c.kind, func.count().label("requests"),
                   func.sum(case((search_logs.c.success, 1), else_=0)).label("succeeded"),
                   func.round(func.avg(search_logs.c.latency_ms)).label("avg_latency_ms"))
            .where(search_logs.c.created_at >= since).group_by(search_logs.c.kind)
        ).mappings().all()
        daily = conn.execute(
            select(day.label("day"), func.count().label("requests"))
            .where(search_logs.c.created_at >= since).group_by(day).order_by(day)
        ).mappings().all()
        top_products = conn.execute(
            select(tracked_products.c.id, tracked_products.c.title, func.count(search_logs.c.id).label("lookups"))
            .join(search_logs, search_logs.c.product_id == tracked_products.c.id)
            .where(search_logs.c.created_at >= since)
            .group_by(tracked_products.c.id).order_by(func.count(search_logs.c.id).desc()).limit(10)
        ).mappings().all()
        failed = conn.execute(
            select(search_logs.c.created_at, search_logs.c.kind, search_logs.c.query, search_logs.c.detail)
            .where(search_logs.c.created_at >= since, search_logs.c.success.is_(False))
            .order_by(search_logs.c.created_at.desc()).limit(25)
        ).mappings().all()

        cheapest = (
            select(listings.c.product_id, listings.c.platform,
                   func.row_number().over(partition_by=listings.c.product_id, order_by=listings.c.price).label("rank"))
            .where(listings.c.price.isnot(None)).subquery()
        )
        platform_wins = conn.execute(
            select(cheapest.c.platform, func.count().label("cheapest_for"))
            .where(cheapest.c.rank == 1).group_by(cheapest.c.platform).order_by(func.count().desc())
        ).mappings().all()
        tracked = conn.execute(select(func.count(tracked_products.c.id))).scalar()

    return {
        "days": days,
        "tracked_products": tracked,
        "by_kind": [to_plain(r) for r in by_kind],
        "daily": [{"day": str(r["day"]), "requests": r["requests"]} for r in daily],
        "top_products": [to_plain(r) for r in top_products],
        "failed_lookups": [to_plain(r) for r in failed],
        "platform_wins": [to_plain(r) for r in platform_wins],
    }
