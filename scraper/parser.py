import json
import re
from typing import Any, Dict, Iterator, Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from core.config import settings
from core.exceptions import LLMGenerationError, ScrapingError
from core.logger import get_logger
from engines.llm import gemini_available, generate_structured
from scraper.dedup import detect_platform
from scraper.models import ProductData, clean_text

logger = get_logger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

_PRICE_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_price(value: Any) -> Optional[float]:
    """Turns '₹1,299.00', 'Rs. 999' or 1299 into a float."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _PRICE_NUMBER.search(str(value))
    return float(match.group().replace(",", "")) if match else None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(str(value).replace(",", "")) if value not in (None, "") else None
    except ValueError:
        return None


def _as_int(value: Any) -> Optional[int]:
    number = _as_float(value)
    return int(number) if number is not None else None


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _name(value: Any) -> Optional[str]:
    value = _first(value)
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _image(value: Any) -> Optional[str]:
    value = _first(value)
    if isinstance(value, dict):
        return value.get("url") or value.get("contentUrl")
    return value if isinstance(value, str) else None


def _iter_json_ld(soup: BeautifulSoup) -> Iterator[Dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or script.get_text() or "", strict=False)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                yield node
                stack.extend(node.get("@graph", []))


def _is_product(node: Dict[str, Any]) -> bool:
    node_type = node.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    return any(t in ("Product", "ProductGroup", "IndividualProduct") for t in types)


def extract_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    """Reads schema.org Product markup, which most large retailers embed for search engines."""
    product = next((node for node in _iter_json_ld(soup) if _is_product(node)), None)
    if not product:
        return {}

    offers = _first(product.get("offers")) or {}
    if not isinstance(offers, dict):
        offers = {}
    rating = product.get("aggregateRating") or {}
    if not isinstance(rating, dict):
        rating = {}
    availability = str(offers.get("availability", ""))

    return {
        "title": product.get("name"),
        "brand": _name(product.get("brand")),
        "category": _name(product.get("category")),
        "description": product.get("description"),
        "image_url": _image(product.get("image")),
        "price": parse_price(offers.get("price") or offers.get("lowPrice")),
        "currency": offers.get("priceCurrency"),
        "in_stock": ("InStock" in availability) if availability else None,
        "rating": _as_float(rating.get("ratingValue")),
        "rating_count": _as_int(rating.get("reviewCount") or rating.get("ratingCount")),
    }


def extract_meta(soup: BeautifulSoup) -> Dict[str, Any]:
    """Falls back to OpenGraph / product meta tags and microdata."""

    def meta(*names: str) -> Optional[str]:
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"]
        return None

    price_tag = soup.find(attrs={"itemprop": "price"})
    microdata_price = (price_tag.get("content") or price_tag.get_text()) if price_tag else None
    title_tag = soup.find("title")

    return {
        "title": meta("og:title", "twitter:title") or (title_tag.get_text() if title_tag else None),
        "description": meta("og:description", "description", "twitter:description"),
        "image_url": meta("og:image", "twitter:image"),
        "price": parse_price(meta("product:price:amount", "og:price:amount") or microdata_price),
        "currency": meta("product:price:currency", "og:price:currency"),
    }


class _LLMExtraction(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None


def extract_with_llm(page_text: str, url: str) -> Dict[str, Any]:
    prompt = (
        "Extract the product being sold on this e-commerce page. Use only facts present in the text; "
        "leave a field null if it is not stated. Price is the current selling price as a number in the "
        "page's currency. Rating is out of 5. Description is 2-4 sentences covering material, features "
        f"and use.\n\nURL: {url}\n\nPage text:\n{page_text}"
    )
    return generate_structured(prompt, _LLMExtraction).model_dump()


def _merge(*sources: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for source in sources:
        for key, value in source.items():
            if merged.get(key) in (None, "") and value not in (None, ""):
                merged[key] = value
    return merged


def extract_product(page_html: str, url: str, use_llm: bool = True) -> ProductData:
    soup = BeautifulSoup(page_html, "html.parser")
    fields = _merge(extract_json_ld(soup), extract_meta(soup))

    if use_llm and gemini_available() and (not fields.get("title") or fields.get("price") is None):
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "svg"]):
            tag.decompose()
        page_text = clean_text(soup.get_text(" ")) or ""
        try:
            fields = _merge(fields, extract_with_llm(page_text[: settings.MAX_SCRAPE_CHARS], url))
        except LLMGenerationError as exc:
            logger.warning(f"LLM extraction fallback failed for {url}: {exc}")

    if not fields.get("title"):
        raise ScrapingError("No product title found on the page (it may be blocked or not a product page).")

    rating = fields.get("rating")
    if rating is not None and not 0 <= rating <= 5:
        fields["rating"] = None

    return ProductData(url=url, platform=detect_platform(url), **fields)


def fetch_html(url: str) -> str:
    try:
        response = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=settings.SCRAPE_TIMEOUT)
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Could not reach {url}: {exc}") from exc
    if response.status_code != 200:
        raise ScrapingError(f"{url} returned HTTP {response.status_code} (the retailer may be blocking bots).")
    return response.text


def scrape_product(url: str) -> ProductData:
    page_html = fetch_html(url)
    product = extract_product(page_html, url)
    logger.info(f"Scraped '{product.title}' from {product.platform} (price={product.price}).")
    return product
