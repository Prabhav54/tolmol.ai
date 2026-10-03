"""Finds the same product on other Indian stores via Gemini + Google Search, then validates every result."""

from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx
from pydantic import BaseModel

from tolmol.ai.llm import extract_json, grounded_search
from tolmol.config import settings
from tolmol.errors import ProviderError
from tolmol.logger import get_logger
from tolmol.schemas import ProductIdentity
from tolmol.scraping.extract import HEADERS, parse_price
from tolmol.scraping.platforms import Platform, platform_by_name, search_link, stores_for_category, url_matches_platform
from tolmol.scraping.urls import is_http_url
from tolmol.services.matching import match_score, price_outliers

logger = get_logger(__name__)

MIN_MATCH_SCORE = 0.45


class Listing(BaseModel):
    platform: str
    title: Optional[str] = None
    url: str
    link_type: str  # source | verified | search
    price: Optional[float] = None
    mrp: Optional[float] = None
    in_stock: Optional[bool] = None
    rating: Optional[float] = None
    match_score: Optional[float] = None
    variant_note: Optional[str] = None
    price_source: str = "search"  # live | search


def source_listing(identity: ProductIdentity) -> Optional[Listing]:
    """The store the shopper pasted, with the price read directly from its page when possible."""
    if not identity.source_url or not identity.source_platform:
        return None
    return Listing(
        platform=identity.source_platform,
        title=identity.title,
        url=identity.source_url,
        link_type="source",
        price=identity.source_price,
        mrp=identity.source_mrp,
        in_stock=identity.source_in_stock,
        rating=identity.source_rating,
        match_score=1.0,
        price_source="live" if identity.source_is_live else "search",
    )


def _search_prompt(identity: ProductIdentity, stores: List[Platform]) -> str:
    names = ", ".join(store.name for store in stores)
    model = f" (model {identity.model_number})" if identity.model_number else ""
    return (
        f"Find the current selling price in India of this exact product{model} on each of these stores: {names}.\n"
        f"Product: {identity.search_name()}\n\n"
        "Rules: only the same model and variant (not accessories, cases or other storage sizes); price is what a "
        "buyer pays today in INR, mrp is the struck-through list price; url is the product page on that store if "
        "you found it, otherwise null. Never guess a price: omit a store you could not find.\n"
        'Reply with ONLY a JSON array: [{"platform": str, "title": str, "price_inr": number, "mrp_inr": number|null, '
        '"url": str|null, "in_stock": bool|null, "rating": number|null}]'
    )


def _verify_link(listing: Listing, platform: Platform, query: str) -> Listing:
    """Keeps a product-page link only if it really opens on that store; otherwise links to the store's search."""
    if listing.link_type == "verified":
        try:
            response = httpx.get(
                listing.url, headers=HEADERS, follow_redirects=True, timeout=settings.LINK_CHECK_TIMEOUT
            )
            final_url = str(response.url)
            if response.status_code == 200 and url_matches_platform(final_url, platform) and len(response.url.path) > 3:
                return listing.model_copy(update={"url": final_url})
        except httpx.HTTPError:
            pass
    return listing.model_copy(update={"url": search_link(platform, query), "link_type": "search"})


def find_listings(identity: ProductIdentity) -> List[Listing]:
    source = source_listing(identity)
    # Search the pasted store too when its own page didn't give us a price (e.g. it blocked the scraper).
    skip_source = source is not None and source.price is not None
    stores = [s for s in stores_for_category(identity.category) if not skip_source or s.name != source.platform]
    if source and not skip_source and all(s.name != source.platform for s in stores):
        stores.append(platform_by_name(source.platform))

    try:
        raw = extract_json(grounded_search(_search_prompt(identity, stores)).text)
    except ProviderError as exc:
        logger.warning(f"Listing search failed for '{identity.title}': {exc}")
        raw = []
    raw = raw if isinstance(raw, list) else []

    found: dict = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        platform = platform_by_name(str(item.get("platform", "")))
        price = parse_price(item.get("price_inr"))
        if platform is None or price is None:
            continue
        if source and platform.name == source.platform:
            if source.price is None:  # fill in the pasted store's price, keeping the shopper's own link
                source.price = price
                source.mrp = source.mrp or parse_price(item.get("mrp_inr"))
                if isinstance(item.get("in_stock"), bool):
                    source.in_stock = item["in_stock"]
            continue
        title = str(item.get("title") or identity.title)
        score, note = match_score(identity.search_name(), identity.model_number, title)
        if score < MIN_MATCH_SCORE:
            logger.info(f"Dropped {platform.name} listing '{title}' (match {score}).")
            continue
        url = item.get("url")
        listing = Listing(
            platform=platform.name,
            title=title,
            url=url if isinstance(url, str) and is_http_url(url) and url_matches_platform(url, platform) else "",
            link_type="verified",
            price=price,
            mrp=parse_price(item.get("mrp_inr")),
            in_stock=item.get("in_stock") if isinstance(item.get("in_stock"), bool) else None,
            rating=parse_price(item.get("rating")),
            match_score=score,
            variant_note=note,
        )
        if not listing.url:
            listing.link_type = "search"
        current = found.get(platform.name)
        if current is None or score > (current.match_score or 0):
            found[platform.name] = listing

    low, high = price_outliers([l.price for l in found.values()], source.price if source else None)
    candidates = [l for l in found.values() if low <= (l.price or 0) <= high]
    dropped = set(found) - {l.platform for l in candidates}
    if dropped:
        logger.info(f"Dropped price outliers: {sorted(dropped)}")

    query = identity.search_name()
    with ThreadPoolExecutor(max_workers=8) as pool:
        verified = list(pool.map(lambda l: _verify_link(l, platform_by_name(l.platform), query), candidates))

    listings = ([source] if source else []) + verified
    return sorted(listings, key=lambda l: (l.price is None, l.price or 0))
