"""Reads a product page's own structured data (schema.org JSON-LD, then OpenGraph/meta tags)."""

import html
import json
import re
from typing import Any, Dict, Iterator, Optional

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from tolmol.config import settings
from tolmol.errors import ScrapingError

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

_PRICE_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BLOCK_MARKERS = ("captcha", "robot check", "access denied", "are you a human", "request blocked")


class PageProduct(BaseModel):
    title: str
    price: Optional[float] = None
    mrp: Optional[float] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    rating: Optional[float] = None
    rating_count: Optional[int] = None
    in_stock: Optional[bool] = None
    model_number: Optional[str] = None


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", html.unescape(str(value))).strip()
    return cleaned or None


def parse_price(value: Any) -> Optional[float]:
    """'₹1,299.00', 'Rs. 999' or 1299 -> float."""
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


def _from_json_ld(soup: BeautifulSoup) -> Dict[str, Any]:
    product = next((node for node in _iter_json_ld(soup) if _is_product(node)), None)
    if not product:
        return {}
    offers = _first(product.get("offers")) or {}
    offers = offers if isinstance(offers, dict) else {}
    rating = product.get("aggregateRating") or {}
    rating = rating if isinstance(rating, dict) else {}
    availability = str(offers.get("availability", ""))
    rating_count = _as_float(rating.get("reviewCount") or rating.get("ratingCount"))
    return {
        "title": product.get("name"),
        "brand": _name(product.get("brand")),
        "category": _name(product.get("category")),
        "description": product.get("description"),
        "image_url": _image(product.get("image")),
        "model_number": product.get("mpn") or (product.get("model") if isinstance(product.get("model"), str) else None),
        "price": parse_price(offers.get("price") or offers.get("lowPrice")),
        "mrp": parse_price(offers.get("highPrice")) if offers.get("lowPrice") else None,
        "in_stock": ("InStock" in availability) if availability else None,
        "rating": _as_float(rating.get("ratingValue")),
        "rating_count": int(rating_count) if rating_count is not None else None,
    }


def _from_meta(soup: BeautifulSoup) -> Dict[str, Any]:
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
    }


def extract_product(page_html: str) -> Optional[PageProduct]:
    """Returns the product described by the page's markup, or None if the page has none."""
    soup = BeautifulSoup(page_html, "html.parser")
    fields: Dict[str, Any] = {}
    for source in (_from_json_ld(soup), _from_meta(soup)):
        for key, value in source.items():
            if fields.get(key) in (None, "") and value not in (None, ""):
                fields[key] = value
    for key in ("title", "brand", "category", "description", "model_number"):
        fields[key] = clean_text(fields.get(key))
    if fields.get("rating") is not None and not 0 <= fields["rating"] <= 5:
        fields["rating"] = None
    if not fields.get("title") or any(marker in fields["title"].lower() for marker in _BLOCK_MARKERS):
        return None
    return PageProduct(**fields)


def fetch_html(url: str, timeout: Optional[float] = None) -> str:
    try:
        response = httpx.get(
            url, headers=HEADERS, follow_redirects=True, timeout=timeout or settings.SCRAPE_TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise ScrapingError(f"Could not reach the store: {exc}") from exc
    if response.status_code != 200:
        raise ScrapingError(f"The store returned HTTP {response.status_code}.")
    return response.text
