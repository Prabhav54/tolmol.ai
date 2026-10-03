"""Works out which product a link, a typed query (English or Hinglish) or a photo refers to."""

from typing import List, Optional

from pydantic import BaseModel

from tolmol.ai.llm import extract_json, generate_structured, generate_structured_from_image, grounded_search
from tolmol.errors import ProductNotIdentified, ProviderError, ScrapingError
from tolmol.logger import get_logger
from tolmol.schemas import ProductCandidate, ProductIdentity
from tolmol.scraping.extract import PageProduct, extract_product, fetch_html, parse_price
from tolmol.scraping.platforms import platform_for_url
from tolmol.scraping.urls import amazon_asin, is_http_url, slug_title

logger = get_logger(__name__)


class _Canonical(BaseModel):
    title: str
    brand: Optional[str] = None
    model_number: Optional[str] = None
    variant: Optional[str] = None
    category: Optional[str] = None


class _Candidates(BaseModel):
    interpretation: str
    products: List[ProductCandidate]


CANONICAL_RULES = (
    "title: the short canonical product name a shopper would search for (brand + series + model, no marketing "
    "phrases). model_number: the manufacturer's model code if known. variant: storage/RAM, size or colour if it "
    "matters for price. category: a short generic category such as 'Smartphones', 'Headphones', 'Running Shoes'."
)


def _canonicalize(page: PageProduct) -> _Canonical:
    """Cleans a store's long listing title into brand / model / variant (no web search needed)."""
    prompt = (
        f"{CANONICAL_RULES}\n\nStore listing title: {page.title}\nBrand: {page.brand or 'unknown'}\n"
        f"Model: {page.model_number or 'unknown'}\nDescription: {(page.description or '')[:600]}"
    )
    try:
        return generate_structured(prompt, _Canonical)
    except ProviderError as exc:
        logger.warning(f"Canonicalization failed, using the raw title: {exc}")
        return _Canonical(title=page.title[:120], brand=page.brand, model_number=page.model_number, category=page.category)


def _identify_with_search(url: str) -> ProductIdentity:
    """For pages that block scrapers: let Gemini look the link up through Google Search."""
    hints = []
    if slug_title(url):
        hints.append(f"The URL path suggests: {slug_title(url)}")
    if amazon_asin(url):
        hints.append(f"Amazon ASIN: {amazon_asin(url)}")
    result = grounded_search(
        "Identify the exact product sold at this Indian e-commerce link and its current selling price there.\n"
        f"Link: {url}\n{chr(10).join(hints)}\n\n{CANONICAL_RULES}\n"
        'Reply with ONLY a JSON object: {"title": str, "brand": str|null, "model_number": str|null, '
        '"variant": str|null, "category": str|null, "price_inr": number|null, "mrp_inr": number|null, '
        '"image_url": str|null}. Use null for anything you could not confirm.'
    )
    try:
        data = extract_json(result.text)
    except ProviderError:
        data = None
    if not isinstance(data, dict) or not data.get("title"):
        raise ProductNotIdentified("We couldn't recognise the product at that link. Try pasting the product name instead.")

    platform = platform_for_url(url)
    image = data.get("image_url")
    return ProductIdentity(
        title=data["title"],
        brand=data.get("brand"),
        model_number=data.get("model_number"),
        variant=data.get("variant"),
        category=data.get("category"),
        image_url=image if isinstance(image, str) and is_http_url(image) else None,
        source_url=url,
        source_platform=platform.name if platform else None,
        source_price=parse_price(data.get("price_inr")),
        source_mrp=parse_price(data.get("mrp_inr")),
        source_is_live=False,
    )


def identify_from_url(url: str) -> ProductIdentity:
    url = url.strip()
    if not is_http_url(url):
        raise ProductNotIdentified("That doesn't look like a web link. Paste the full product URL (https://…).")
    platform = platform_for_url(url)

    page = None
    try:
        page = extract_product(fetch_html(url))
    except ScrapingError as exc:
        logger.info(f"Direct scrape failed for {url} ({exc}); falling back to web search.")

    if page is None:
        return _identify_with_search(url)

    canonical = _canonicalize(page)
    return ProductIdentity(
        title=canonical.title,
        brand=canonical.brand or page.brand,
        model_number=canonical.model_number or page.model_number,
        variant=canonical.variant,
        category=canonical.category or page.category,
        image_url=page.image_url,
        source_url=url,
        source_platform=platform.name if platform else None,
        source_price=page.price,
        source_mrp=page.mrp,
        source_in_stock=page.in_stock,
        source_rating=page.rating,
        source_is_live=page.price is not None,
    )


def search_products(query: str) -> _Candidates:
    """Free-text product search. Understands Hinglish and messy phrasing ("joote 2000 ke andar")."""
    result = grounded_search(
        "A shopper in India typed this into a price-comparison site. It may be Hinglish (Hindi in Roman script), "
        f'misspelled or vague: "{query}"\n\n'
        "1. Interpret what they want in one short English sentence (e.g. 'Shoes under ₹2,000').\n"
        "2. Find up to 6 specific, currently sold products in India that best match, using current listings.\n"
        f"{CANONICAL_RULES}\n"
        'Reply with ONLY a JSON object: {"interpretation": str, "products": [{"title": str, "brand": str|null, '
        '"model_number": str|null, "variant": str|null, "category": str|null, "approx_price": number|null}]}'
    )
    try:
        data = extract_json(result.text)
        candidates = _Candidates.model_validate(data)
    except Exception:
        # Fall back to turning the prose answer into the schema.
        candidates = generate_structured(
            f"Convert this answer into the requested structure.\nShopper query: {query}\n\n{result.text}", _Candidates
        )
    if not candidates.products:
        raise ProductNotIdentified(f'No products found for "{query}". Try a brand or model name.')
    return candidates


def identify_from_photo(image: bytes, mime_type: str) -> _Candidates:
    """Search by photo: Gemini vision names the product so it can be compared like any other."""
    candidates = generate_structured_from_image(
        "Identify the retail product in this photo so a shopper in India can compare its price. "
        "Give your best guess first and up to 2 close alternatives (other models it could be). "
        f"interpretation: one sentence describing what you see.\n{CANONICAL_RULES}",
        image,
        mime_type,
        _Candidates,
    )
    if not candidates.products:
        raise ProductNotIdentified("We couldn't recognise a product in that photo. Try a clearer, closer shot.")
    candidates.products = candidates.products[:3]
    return candidates


def identity_from_candidate(candidate: ProductCandidate) -> ProductIdentity:
    return ProductIdentity(**candidate.model_dump())
