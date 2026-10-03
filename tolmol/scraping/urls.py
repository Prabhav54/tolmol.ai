import hashlib
import re
from typing import Optional
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

# Query parameters that only track the visit and never change which product a URL points to.
_TRACKING_PARAMS = re.compile(
    r"^(utm_.*|ref|ref_|tag|gclid|fbclid|msclkid|pf_rd_.*|pd_rd_.*|psc|th|sr|qid|keywords|crid|sprefix"
    r"|_encoding|content-id|linkcode|smid|spm|srsltid|lid|marketplace|store|srno|otracker.*|ssid|iid"
    r"|affid|affextparam\d*|cmpid|source|src)$",
    re.IGNORECASE,
)
_AMAZON_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", re.IGNORECASE)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_http_url(value: str) -> bool:
    parts = urlsplit(value.strip())
    return parts.scheme in ("http", "https") and "." in parts.netloc


def normalize_url(url: str) -> str:
    """Canonical form of a product URL: no tracking params, no fragment, Amazon reduced to its ASIN."""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    host = parts.netloc.lower()
    for prefix in ("www.", "m.", "dl."):
        if host.startswith(prefix):
            host = host[len(prefix):]
            break

    if "amazon." in host:
        asin = _AMAZON_ASIN.search(parts.path)
        if asin:
            return urlunsplit(("https", host, f"/dp/{asin.group(1).upper()}", "", ""))

    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    query = sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=False) if not _TRACKING_PARAMS.match(key)
    )
    return urlunsplit(("https", host, path, urlencode(query), ""))


def url_hash(url: str) -> str:
    return sha256_hex(normalize_url(url))


def amazon_asin(url: str) -> Optional[str]:
    match = _AMAZON_ASIN.search(urlsplit(url).path)
    return match.group(1).upper() if match else None


def slug_title(url: str) -> Optional[str]:
    """Most store URLs carry the product name in the path ("/Sony-WH-1000XM5-Cancelling/dp/..."); recover it."""
    path = unquote(urlsplit(url).path)
    best = ""
    for segment in path.split("/"):
        words = re.split(r"[-_+]+", segment)
        if len(words) >= 3 and sum(word.isalpha() for word in words) >= 2 and len(segment) > len(best):
            best = segment
    if not best:
        return None
    return re.sub(r"\s+", " ", re.sub(r"[-_+]+", " ", best)).strip()
