from fastapi import APIRouter

from api.schemas import (
    IngestBatchRequest,
    IngestBatchResponse,
    IngestProductsRequest,
    IngestResult,
    IngestURLRequest,
)
from api.services import ingestion

router = APIRouter(prefix="/ingest", tags=["Ingest"])


@router.post("", response_model=IngestResult)
def ingest_url(payload: IngestURLRequest):
    """Scrape one product page, deduplicate by SHA-256 URL hash, embed and store it."""
    return ingestion.ingest_url(payload.url, refresh=payload.refresh)


@router.post("/batch", response_model=IngestBatchResponse)
def ingest_batch(payload: IngestBatchRequest):
    """Scrape up to 25 URLs; failures are reported per URL instead of failing the batch."""
    results = ingestion.ingest_urls(payload.urls, refresh=payload.refresh)
    return IngestBatchResponse(results=results, summary=ingestion.summarize(results))


@router.post("/products", response_model=IngestBatchResponse)
def ingest_products(payload: IngestProductsRequest):
    """Bulk-load already structured products (catalog feeds / exports) through the same dedup + embed path."""
    results = ingestion.ingest_products(payload.products, refresh=payload.refresh)
    return IngestBatchResponse(results=results, summary=ingestion.summarize(results))
