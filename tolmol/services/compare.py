"""The compare flow: identify -> search every store -> record snapshots -> analysis (+ alerts)."""

from typing import Any, Dict

from sqlalchemy.exc import SQLAlchemyError

from tolmol.config import settings
from tolmol.errors import DatabaseUnavailable
from tolmol.logger import get_logger
from tolmol.schemas import ProductIdentity
from tolmol.services import alerts, tracker
from tolmol.services.market import find_listings

logger = get_logger(__name__)


def compare(identity: ProductIdentity, refresh: bool = False) -> Dict[str, Any]:
    key = identity.identity_key()
    if not refresh:
        try:
            cached_id = tracker.fresh_product_id(key, settings.COMPARE_CACHE_HOURS)
            if cached_id:
                return tracker.product_view(cached_id, cached=True)
        except SQLAlchemyError:
            pass  # database down: fall through to a live comparison

    found = find_listings(identity)
    try:
        product_id = tracker.save_comparison(identity, found)
    except (SQLAlchemyError, DatabaseUnavailable) as exc:
        logger.warning(f"Comparison not saved (database unavailable): {exc.__class__.__name__}")
        return tracker.ephemeral_view(identity, found)

    view = tracker.product_view(product_id)
    best = view["analysis"]["best"]
    if best:
        alerts.check_alerts(product_id, identity.title, best["price"], best["platform"])
    return view


def refresh_product(product_id: int) -> Dict[str, Any]:
    """Used by the daily cron: re-search every store for an already tracked product."""
    identity = tracker.product_identity(product_id)
    view = compare(identity, refresh=True)
    best = view["analysis"]["best"]
    return {"product_id": product_id, "title": identity.title, "stores": view["analysis"]["stores_with_price"],
            "best": best}
