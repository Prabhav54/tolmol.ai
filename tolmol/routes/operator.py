import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from tolmol.config import settings
from tolmol.db.session import init_db
from tolmol.logger import get_logger
from tolmol.schemas import ApiKeyRequest
from tolmol.services import access, tracker
from tolmol.services.compare import refresh_product

logger = get_logger(__name__)
router = APIRouter(prefix="/api", tags=["Operator"])


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Admin endpoints are disabled (ADMIN_TOKEN is not set).")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@router.post("/admin/setup", dependencies=[Depends(require_admin)])
def setup():
    """Creates the tables and indexes (safe to run repeatedly)."""
    init_db()
    return {"schema": "ready"}


@router.get("/admin/insights", dependencies=[Depends(require_admin)])
def insights(days: int = 30):
    """Search volume, top products, failed lookups and which store is cheapest most often."""
    return access.operator_insights(days)


@router.get("/admin/api-keys", dependencies=[Depends(require_admin)])
def list_keys():
    return {"items": access.list_api_keys()}


@router.post("/admin/api-keys", dependencies=[Depends(require_admin)])
def create_key(payload: ApiKeyRequest):
    return access.create_api_key(payload.name, payload.daily_limit)


@router.delete("/admin/api-keys/{key_id}", dependencies=[Depends(require_admin)])
def revoke_key(key_id: int):
    if not access.revoke_api_key(key_id):
        raise HTTPException(status_code=404, detail="Key not found or already revoked.")
    return {"revoked": key_id}


@router.get("/cron/refresh")
def daily_refresh(authorization: Optional[str] = Header(default=None)):
    """Vercel Cron: re-checks the least recently compared products and fires price alerts."""
    if not settings.CRON_SECRET or authorization != f"Bearer {settings.CRON_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized.")
    results = []
    for product_id in tracker.stale_product_ids(settings.CRON_BATCH):
        try:
            results.append(refresh_product(product_id))
        except Exception as exc:  # one failing product must not stop the batch
            logger.error(f"Refresh failed for product #{product_id}: {exc}")
            results.append({"product_id": product_id, "error": str(exc)[:200]})
    return {"refreshed": results}
