import secrets
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.services.ingestion import ingest_products, summarize
from core.config import settings
from db.models import products
from db.session import get_engine, init_db
from scraper.dedup import url_hash
from scripts.init_db import archive_legacy_tables
from scripts.seed_catalog import BATCH_SIZE, batched, load_dummyjson

router = APIRouter(prefix="/admin", tags=["Admin"])


class SetupRequest(BaseModel):
    archive_legacy: bool = False
    seed_dummyjson: bool = False
    # The Gemini free tier embeds ~100 texts/minute, so seed in chunks; call again to continue.
    seed_max_new: int = Field(90, ge=1, le=500)


def _authorize(token: Optional[str]) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Admin endpoints are disabled (ADMIN_TOKEN is not set).")
    if not token or not secrets.compare_digest(token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token.")


@router.post("/setup")
def setup(payload: SetupRequest, x_admin_token: Optional[str] = Header(default=None)):
    """
    One-time database setup from the deployed app (useful when your own network blocks Postgres ports):
    optionally archive pre-2.0 tables into the `legacy` schema, create the schema, and seed demo products.
    """
    _authorize(x_admin_token)
    archived = archive_legacy_tables() if payload.archive_legacy else []
    init_db()

    seeded = None
    if payload.seed_dummyjson:
        catalog = load_dummyjson()
        with get_engine().connect() as conn:
            known = set(conn.execute(select(products.c.url_hash)).scalars())
        pending = [item for item in catalog if url_hash(item.url) not in known]
        chunk = pending[: payload.seed_max_new]
        seeded = {"already_in_catalog": len(catalog) - len(pending), "remaining": len(pending) - len(chunk)}
        for batch in batched(chunk, BATCH_SIZE):
            for status, count in summarize(ingest_products(batch)).items():
                seeded[status] = seeded.get(status, 0) + count
    return {"archived_to_legacy": archived, "schema": "ready", "seeded": seeded}
