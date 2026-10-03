from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from scraper.models import ProductData


class IngestURLRequest(BaseModel):
    url: str = Field(..., min_length=8, examples=["https://www.amazon.in/dp/B0CHX1W1XY"])
    refresh: bool = Field(False, description="Re-scrape a known URL to update its price and details.")


class IngestBatchRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=25)
    refresh: bool = False


class IngestProductsRequest(BaseModel):
    """Bulk catalog import for feeds/exports that are already structured (no scraping needed)."""

    products: List[ProductData] = Field(..., min_length=1, max_length=500)
    refresh: bool = False


class IngestResult(BaseModel):
    url: str
    status: str  # created | updated | unchanged | duplicate | failed
    product_id: Optional[int] = None
    title: Optional[str] = None
    platform: Optional[str] = None
    price: Optional[float] = None
    url_hash: Optional[str] = None
    detail: Optional[str] = None


class IngestBatchResponse(BaseModel):
    results: List[IngestResult]
    summary: Dict[str, int]


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, examples=["running shoes under ₹2000 with rating > 4.2"])
    top_k: Optional[int] = Field(None, ge=1, le=50)
    synthesize: bool = True


class ProductHit(BaseModel):
    id: int
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    platform: str
    price: Optional[float] = None
    currency: str = "INR"
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    in_stock: Optional[bool] = None
    url: str
    image_url: Optional[str] = None
    similarity: Optional[float] = None


class QueryResponse(BaseModel):
    question: str
    route: str
    route_reason: str
    filters: Dict[str, Any]
    answer: str
    products: List[ProductHit] = []
    aggregates: Optional[List[Dict[str, Any]]] = None
    sql: Optional[str] = None
    synthesis_provider: str
    timings_ms: Dict[str, float]


class BenchmarkRequest(BaseModel):
    samples: int = Field(50, ge=5, le=500)
    top_k: int = Field(6, ge=1, le=50)
    end_to_end: bool = Field(False, description="Also time query embedding + retrieval (uses embedding API calls).")
