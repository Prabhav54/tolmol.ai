"""Researches specs and reviews from real web sources and indexes them for chat (pgvector + full-text)."""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, update

from tolmol.ai.embeddings import embed_documents
from tolmol.ai.llm import generate_structured, grounded_search
from tolmol.db.models import product_chunks, tracked_products
from tolmol.db.session import get_engine
from tolmol.errors import ProviderError
from tolmol.logger import get_logger
from tolmol.services.tracker import product_identity

logger = get_logger(__name__)


class SpecItem(BaseModel):
    group: str = Field(description="e.g. Display, Battery, Camera, Audio, Build, Connectivity, General")
    name: str
    value: str


class Aspect(BaseModel):
    aspect: str = Field(description="What buyers talk about, e.g. Battery life, Comfort, Sound, Build quality")
    sentiment: str = Field(description="positive, mixed or negative")
    summary: str = Field(description="One sentence on what reviewers say about it")


class ReviewAnalysis(BaseModel):
    positive_pct: int = Field(ge=0, le=100)
    neutral_pct: int = Field(ge=0, le=100)
    negative_pct: int = Field(ge=0, le=100)
    average_rating: Optional[float] = Field(None, description="Typical star rating out of 5 across stores, if stated")
    overall: str = Field(description="Two-sentence summary of buyer and expert opinion")
    aspects: List[Aspect]
    pros: List[str]
    cons: List[str]
    best_for: Optional[str] = Field(None, description="Who this product suits best, one short phrase")


class Insights(BaseModel):
    overview: str
    specs: List[SpecItem]
    reviews: ReviewAnalysis


def _research(name: str) -> tuple:
    result = grounded_search(
        f"Research this product sold in India: {name}\n\n"
        "Write a factual report with two sections.\n"
        "SPECIFICATIONS: the complete key specifications (dimensions, weight, display, battery, performance, "
        "materials, connectivity, warranty, whatever applies to this kind of product), with exact values.\n"
        "REVIEWS: what customers on Amazon.in / Flipkart and professional reviewers say. Overall sentiment and "
        "typical star rating, the main aspects people discuss and whether they are praised or criticised, "
        "frequent complaints, and who it suits. Be specific and only state what sources support."
    )
    if len(result.text) < 200:
        raise ProviderError("Not enough information was found about this product.")
    return result.text, result.sources


def _structure(name: str, report: str) -> Insights:
    insights = generate_structured(
        f"Product: {name}\n\nTurn this research report into the requested structure. Use only facts from the "
        "report. Percentages are your estimate of the share of positive, neutral and negative buyer opinion and "
        "must add up to 100. List 3-8 aspects, 3-6 pros and 2-6 cons.\n\nREPORT:\n" + report,
        Insights,
    )
    total = insights.reviews.positive_pct + insights.reviews.neutral_pct + insights.reviews.negative_pct
    if total and total != 100:
        reviews = insights.reviews
        reviews.positive_pct = round(reviews.positive_pct * 100 / total)
        reviews.negative_pct = round(reviews.negative_pct * 100 / total)
        reviews.neutral_pct = 100 - reviews.positive_pct - reviews.negative_pct
    return insights


def _split_report(report: str) -> List[Dict[str, str]]:
    """Paragraph chunks of the raw report, labelled by the section they came from."""
    chunks, kind = [], "overview"
    for block in re.split(r"\n\s*\n", report):
        text = re.sub(r"[*#]+", "", block).strip()
        if not text:
            continue
        upper = text[:40].upper()
        if "SPECIFICATION" in upper:
            kind = "spec"
        elif "REVIEW" in upper:
            kind = "review"
        for start in range(0, len(text), 900):
            piece = text[start:start + 900].strip()
            if len(piece) > 40:
                chunks.append({"kind": kind, "content": piece})
    return chunks


def _chunks(name: str, insights: Insights, report: str) -> List[Dict[str, str]]:
    chunks = [{"kind": "overview", "content": f"{name}. {insights.overview}"}]
    groups: Dict[str, List[str]] = {}
    for spec in insights.specs:
        groups.setdefault(spec.group, []).append(f"{spec.name}: {spec.value}")
    chunks += [{"kind": "spec", "content": f"{group} specifications — " + "; ".join(items)} for group, items in groups.items()]

    reviews = insights.reviews
    chunks.append({"kind": "review", "content": f"Overall opinion: {reviews.overall} "
                   f"({reviews.positive_pct}% positive, {reviews.neutral_pct}% neutral, {reviews.negative_pct}% negative)."})
    chunks += [{"kind": "review", "content": f"{a.aspect} ({a.sentiment}): {a.summary}"} for a in reviews.aspects]
    chunks.append({"kind": "review", "content": "Pros: " + "; ".join(reviews.pros)})
    chunks.append({"kind": "review", "content": "Cons and common complaints: " + "; ".join(reviews.cons)})
    if reviews.best_for:
        chunks.append({"kind": "review", "content": f"Best for: {reviews.best_for}"})
    return chunks + _split_report(report)


def build_insights(product_id: int) -> Dict[str, Any]:
    identity = product_identity(product_id)
    name = identity.search_name()
    report, sources = _research(name)
    insights = _structure(name, report)

    chunks = _chunks(name, insights, report)
    vectors = embed_documents([chunk["content"] for chunk in chunks])
    specs = [spec.model_dump() for spec in insights.specs]
    review_summary = {"overview": insights.overview, **insights.reviews.model_dump()}
    unique_sources = list({source["title"] or source["url"]: source for source in sources}.values())[:12]

    with get_engine().begin() as conn:
        conn.execute(delete(product_chunks).where(product_chunks.c.product_id == product_id))
        conn.execute(
            insert(product_chunks),
            [{"product_id": product_id, **chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)],
        )
        conn.execute(
            update(tracked_products)
            .where(tracked_products.c.id == product_id)
            .values(specs=specs, review_summary=review_summary, insight_sources=unique_sources,
                    insights_ready_at=func.now())
        )
    logger.info(f"Indexed {len(chunks)} insight chunks for product #{product_id}.")
    return {"ready": True, "specs": specs, "reviews": review_summary, "sources": unique_sources}
