from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import quote_plus, urlsplit


@dataclass(frozen=True)
class Platform:
    name: str
    domains: Tuple[str, ...]
    search_url: str  # "{q}" is replaced by the URL-encoded product name
    kind: str  # electronics | fashion | beauty | general


PLATFORMS: List[Platform] = [
    Platform("Amazon", ("amazon.in", "amzn.in", "amzn.to"), "https://www.amazon.in/s?k={q}", "general"),
    Platform("Flipkart", ("flipkart.com", "fkrt.it"), "https://www.flipkart.com/search?q={q}", "general"),
    Platform("Croma", ("croma.com",), "https://www.croma.com/searchB?q={q}%3Arelevance", "electronics"),
    Platform("Reliance Digital", ("reliancedigital.in",), "https://www.reliancedigital.in/products?q={q}", "electronics"),
    Platform("Vijay Sales", ("vijaysales.com",), "https://www.vijaysales.com/search-listing?q={q}", "electronics"),
    Platform("Tata CLiQ", ("tatacliq.com",), "https://www.tatacliq.com/search/?searchCategory=all&text={q}", "general"),
    Platform("JioMart", ("jiomart.com",), "https://www.jiomart.com/search/{q}", "general"),
    Platform("Myntra", ("myntra.com",), "https://www.myntra.com/{q}", "fashion"),
    Platform("AJIO", ("ajio.com",), "https://www.ajio.com/search/?text={q}", "fashion"),
    Platform("Nykaa", ("nykaa.com",), "https://www.nykaa.com/search/result/?q={q}", "beauty"),
    Platform("Meesho", ("meesho.com",), "https://www.meesho.com/search?q={q}", "general"),
    Platform("Snapdeal", ("snapdeal.com",), "https://www.snapdeal.com/search?keyword={q}", "general"),
]

_BY_NAME = {platform.name.lower(): platform for platform in PLATFORMS}
_ALIASES = {
    "amazon.in": "amazon",
    "amazon india": "amazon",
    "reliance": "reliance digital",
    "reliancedigital": "reliance digital",
    "vijaysales": "vijay sales",
    "tata cliq": "tata cliq",
    "tatacliq": "tata cliq",
    "jio mart": "jiomart",
}


def _host(url: str) -> str:
    host = urlsplit(url if "://" in url else "https://" + url).netloc.lower()
    return host.split("@")[-1].split(":")[0]


def platform_for_url(url: str) -> Optional[Platform]:
    host = _host(url)
    for platform in PLATFORMS:
        if any(host == domain or host.endswith("." + domain) for domain in platform.domains):
            return platform
    return None


def platform_by_name(name: str) -> Optional[Platform]:
    key = (name or "").strip().lower()
    key = _ALIASES.get(key, key)
    if key in _BY_NAME:
        return _BY_NAME[key]
    for platform in PLATFORMS:  # "Amazon.in Store", "Flipkart (SuperCoin)" ...
        if platform.name.lower() in key:
            return platform
    return None


def url_matches_platform(url: str, platform: Platform) -> bool:
    found = platform_for_url(url)
    return found is not None and found.name == platform.name


def search_link(platform: Platform, query: str) -> str:
    if platform.name == "Myntra":
        return platform.search_url.format(q=quote_plus(query).replace("+", "-"))
    return platform.search_url.format(q=quote_plus(query))


def stores_for_category(category: Optional[str]) -> List[Platform]:
    """Which stores are worth searching for a product category."""
    text = (category or "").lower()
    if any(word in text for word in ("cloth", "fashion", "shoe", "apparel", "wear", "shirt", "jean", "dress", "kurta")):
        wanted = {"fashion", "general"}
    elif any(word in text for word in ("beauty", "skin", "makeup", "cosmetic", "hair", "fragrance", "perfume")):
        wanted = {"beauty", "general"}
    else:
        wanted = {"electronics", "general"}
    return [platform for platform in PLATFORMS if platform.kind in wanted and platform.name not in ("Meesho", "Snapdeal")]
