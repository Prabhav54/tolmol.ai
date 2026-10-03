"""Closed-domain answer synthesis: the LLM only sees, and may only cite, products retrieved from the catalog."""

from typing import Any, Dict, List, Tuple

from core.config import settings
from core.exceptions import LLMGenerationError
from core.logger import get_logger
from engines.llm import generate_text
from engines.query_parser import QueryFilters
from engines.sql_engine import AGGREGATE_LABELS

logger = get_logger(__name__)

NO_MATCH_ANSWER = (
    "I couldn't find any products in the catalog that match this request. "
    "Try loosening a filter (price, rating or platform) or describing the product differently."
)

SYSTEM_PROMPT = (
    "You are tolmol.ai, a shopping assistant for a closed product catalog. "
    "You may only recommend products from the CATALOG RESULTS you are given. Never invent products, "
    "prices, ratings, discounts or availability, and never use outside knowledge about products. "
    "Quote prices and ratings exactly as listed. If none of the results fit the request, say so plainly."
)


def _format_price(product: Dict[str, Any]) -> str:
    if product.get("price") is None:
        return "price not listed"
    symbol = "₹" if product.get("currency", "INR") == "INR" else f"{product.get('currency')} "
    return f"{symbol}{product['price']:,.0f}"


def _product_line(product: Dict[str, Any]) -> str:
    rating = f"{product['rating']:.1f}★" if product.get("rating") is not None else "no rating"
    details = [_format_price(product), rating, product.get("platform") or "unknown platform"]
    if product.get("brand"):
        details.insert(0, product["brand"])
    if product.get("in_stock") is False:
        details.append("out of stock")
    return f"[#{product['id']}] {product['title']} — {', '.join(details)}"


def fallback_answer(products: List[Dict[str, Any]]) -> str:
    lines = [f"Here are the {len(products)} best matches from the catalog:"]
    lines += [f"• {_product_line(product)}" for product in products]
    return "\n".join(lines)


def synthesize_answer(question: str, products: List[Dict[str, Any]]) -> Tuple[str, str]:
    """Returns (answer, provider). Falls back to a deterministic list when the LLM is unavailable."""
    if not products:
        return NO_MATCH_ANSWER, "none"

    catalog = "\n".join(_product_line(product) for product in products)
    prompt = (
        f"CATALOG RESULTS (already filtered and ranked for the shopper):\n{catalog}\n\n"
        f"SHOPPER QUESTION: {question}\n\n"
        "Write a short recommendation (3-5 sentences). Name the best 1-3 options with their #id, exact price "
        "and rating, and explain in one clause each why they fit. If several are close, say how they differ. "
        "Do not use markdown headings or tables."
    )
    try:
        return generate_text(prompt, system=SYSTEM_PROMPT, max_tokens=400), settings.LLM_PROVIDER.lower()
    except LLMGenerationError as exc:
        logger.warning(f"Synthesis unavailable, returning catalog list instead: {exc}")
        return fallback_answer(products), "fallback"


def _format_value(key: str, value: Any) -> str:
    if value is None:
        return "n/a"
    if key.endswith("price"):
        return f"₹{value:,.2f}"
    if key == "average_rating":
        return f"{value:.2f}★"
    return f"{value:,}" if isinstance(value, (int, float)) else str(value)


def summarize_aggregate(rows: List[Dict[str, Any]], filters: QueryFilters) -> str:
    """Deterministic, number-exact summary for analytics questions (no LLM involved)."""
    metric = AGGREGATE_LABELS[filters.aggregate or "count"]
    label = metric.replace("_", " ")
    if not rows or (not filters.group_by and rows[0].get("product_count") == 0):
        return "No products in the catalog match these filters."

    if not filters.group_by:
        row = rows[0]
        summary = f"The {label} is {_format_value(metric, row[metric])}"
        if metric != "product_count":
            summary += f" across {row['product_count']:,} matching products"
        return summary + "."

    lines = [f"{label.capitalize()} by {filters.group_by}:"]
    lines += [f"• {row[filters.group_by]}: {_format_value(metric, row[metric])}" for row in rows]
    return "\n".join(lines)
