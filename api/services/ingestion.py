"""ETL: scrape -> SHA-256 URL dedup -> embed -> store in Supabase (pgvector)."""

from typing import Dict, List

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from api.schemas import IngestResult
from core.exceptions import ScrapingError
from core.logger import get_logger
from db.models import price_history, products
from db.session import get_engine
from engines.embeddings import embed_documents
from scraper.dedup import detect_platform, sha256_hex, url_hash
from scraper.models import ProductData
from scraper.parser import scrape_product

logger = get_logger(__name__)


def _row_values(product: ProductData) -> Dict:
    return {
        "url": product.url,
        "platform": product.platform or detect_platform(product.url),
        "title": product.title,
        "brand": product.brand,
        "category": product.category,
        "description": product.description,
        "price": product.price,
        "currency": product.currency,
        "rating": product.rating,
        "rating_count": product.rating_count,
        "image_url": product.image_url,
        "in_stock": product.in_stock,
        "content_hash": sha256_hex(product.embedding_text()),
    }


def _result(product: ProductData, status: str, product_id: int, digest: str) -> IngestResult:
    return IngestResult(
        url=product.url,
        status=status,
        product_id=product_id,
        title=product.title,
        platform=product.platform or detect_platform(product.url),
        price=product.price,
        url_hash=digest,
    )


def find_by_url(url: str):
    with get_engine().connect() as conn:
        return conn.execute(
            select(products.c.id, products.c.title, products.c.platform, products.c.price).where(
                products.c.url_hash == url_hash(url)
            )
        ).first()


def ingest_url(url: str, refresh: bool = False) -> IngestResult:
    """Scrapes one product URL. Known URLs are skipped before any network or database write."""
    digest = url_hash(url)
    if not refresh:
        existing = find_by_url(url)
        if existing:
            logger.info(f"Duplicate URL skipped (sha256={digest[:12]}…), product #{existing.id}.")
            return IngestResult(
                url=url,
                status="duplicate",
                product_id=existing.id,
                title=existing.title,
                platform=existing.platform,
                price=float(existing.price) if existing.price is not None else None,
                url_hash=digest,
                detail="Already in the catalog. Pass refresh=true to re-scrape.",
            )
    return ingest_products([scrape_product(url)], refresh=True)[0]


def ingest_urls(urls: List[str], refresh: bool = False) -> List[IngestResult]:
    results = []
    for url in urls:
        try:
            results.append(ingest_url(url, refresh=refresh))
        except ScrapingError as exc:
            results.append(IngestResult(url=url, status="failed", url_hash=url_hash(url), detail=str(exc)))
    return results


def ingest_products(items: List[ProductData], refresh: bool = False) -> List[IngestResult]:
    """
    Writes structured products. The SHA-256 hash of the normalized URL is the unique key, so a
    product already in the catalog produces no write at all (unless refresh=True), and concurrent
    inserts of the same URL are absorbed by ON CONFLICT DO NOTHING.
    """
    # Collapse duplicates inside the batch itself.
    batch: Dict[str, ProductData] = {}
    for item in items:
        batch.setdefault(url_hash(item.url), item)

    with get_engine().connect() as conn:
        existing = {
            row.url_hash: row
            for row in conn.execute(
                select(products.c.url_hash, products.c.id, products.c.content_hash, products.c.price).where(
                    products.c.url_hash.in_(list(batch))
                )
            )
        }

    results: Dict[str, IngestResult] = {}
    to_embed: Dict[str, Dict] = {}
    for digest, item in batch.items():
        values = _row_values(item)
        row = existing.get(digest)
        if row is None:
            to_embed[digest] = values
        elif not refresh:
            results[digest] = _result(item, "duplicate", row.id, digest)
        elif row.content_hash != values["content_hash"]:
            to_embed[digest] = values
        else:
            values["skip_embedding"] = True
            to_embed[digest] = values

    needs_vectors = [d for d, v in to_embed.items() if not v.get("skip_embedding")]
    vectors = embed_documents([batch[d].embedding_text() for d in needs_vectors])
    for digest, vector in zip(needs_vectors, vectors):
        to_embed[digest]["embedding"] = vector

    with get_engine().begin() as conn:
        for digest, values in to_embed.items():
            item = batch[digest]
            values.pop("skip_embedding", None)
            row = existing.get(digest)

            if row is None:
                inserted = conn.execute(
                    insert(products)
                    .values(url_hash=digest, **values)
                    .on_conflict_do_nothing(index_elements=["url_hash"])
                    .returning(products.c.id)
                ).scalar()
                if inserted is None:  # another request inserted it first
                    product_id = conn.execute(select(products.c.id).where(products.c.url_hash == digest)).scalar()
                    results[digest] = _result(item, "duplicate", product_id, digest)
                    continue
                if item.price is not None:
                    conn.execute(insert(price_history).values(product_id=inserted, price=item.price))
                results[digest] = _result(item, "created", inserted, digest)
                continue

            changed_price = item.price is not None and (row.price is None or float(row.price) != item.price)
            changed_content = row.content_hash != values["content_hash"]
            if not changed_price and not changed_content:
                results[digest] = _result(item, "unchanged", row.id, digest)
                continue
            conn.execute(
                update(products).where(products.c.id == row.id).values(updated_at=func.now(), **values)
            )
            if changed_price:
                conn.execute(insert(price_history).values(product_id=row.id, price=item.price))
            results[digest] = _result(item, "updated", row.id, digest)

    ordered = [results[url_hash(item.url)] for item in items]
    logger.info(f"Ingested {len(items)} products: {summarize(ordered)}")
    return ordered


def summarize(results: List[IngestResult]) -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    return summary
