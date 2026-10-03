import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PLATFORMS = {
    "amazon": "Amazon",
    "flipkart": "Flipkart",
    "myntra": "Myntra",
    "ajio": "AJIO",
    "snitch": "Snitch",
    "nykaa": "Nykaa",
    "meesho": "Meesho",
    "tatacliq": "Tata CLiQ",
    "croma": "Croma",
}

# Query parameters that only track the visit and never change which product a URL points to.
_TRACKING_PARAMS = re.compile(
    r"^(utm_.*|ref|ref_|tag|gclid|fbclid|msclkid|pf_rd_.*|pd_rd_.*|psc|th|sr|qid|keywords|crid|sprefix"
    r"|_encoding|content-id|linkcode|smid|spm|srsltid|lid|marketplace|store|srno|otracker.*|ssid|iid"
    r"|affid|affextparam\d*|cmpid|source|src)$",
    re.IGNORECASE,
)
_AMAZON_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", re.IGNORECASE)


def detect_platform(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    for key, name in PLATFORMS.items():
        if key in host:
            return name
    return "Generic Retailer"


def normalize_url(url: str) -> str:
    """Reduces a product URL to a canonical form so that the same product always hashes the same."""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url

    parts = urlsplit(url)
    host = parts.netloc.lower()
    for prefix in ("www.", "m.", "dl."):
        if host.startswith(prefix):
            host = host[len(prefix):]
            break

    # Amazon URLs carry the product title and a tracking slug; the ASIN alone identifies the item.
    if "amazon." in host:
        asin = _AMAZON_ASIN.search(parts.path)
        if asin:
            return urlunsplit(("https", host, f"/dp/{asin.group(1).upper()}", "", ""))

    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if not _TRACKING_PARAMS.match(key)
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def url_hash(url: str) -> str:
    """SHA-256 of the normalized URL; the unique key for deduplicating catalog writes."""
    return sha256_hex(normalize_url(url))
