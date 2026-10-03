"""Decides whether a store listing is the same product, using model numbers plus title similarity."""

import re
from difflib import SequenceMatcher
from statistics import median
from typing import Iterable, List, Optional, Set, Tuple

# Words that make two otherwise similar titles different models ("S24" vs "S24 Ultra").
EDITION_WORDS = {"ultra", "plus", "pro", "max", "mini", "lite", "fe", "neo", "prime", "air", "se", "edge"}
GENERIC_WORDS = {
    "with", "and", "for", "the", "new", "latest", "buy", "online", "india", "price", "best", "pack", "of",
    "wireless", "bluetooth", "smartphone", "mobile", "phone", "headphones", "headphone", "earbuds", "black",
    "white", "blue", "green", "red", "grey", "gray", "silver", "gold", "5g", "4g", "in", "on", "a",
}
_STORAGE = re.compile(r"\b(\d+)\s?(gb|tb)\b")


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def model_keys(text: str) -> Set[str]:
    """Alphanumeric codes such as 'WH-1000XM5', 'SM-S721B', 'MTP43HN/A' (punctuation removed)."""
    keys = set()
    for raw in re.findall(r"[A-Za-z0-9]+(?:[-/][A-Za-z0-9]+)*", text or ""):
        key = re.sub(r"[-/]", "", raw).lower()
        if len(key) >= 4 and re.search(r"\d", key) and re.search(r"[a-z]", key) and not _STORAGE.fullmatch(key):
            if not re.fullmatch(r"\d+(gb|tb|mah|mp|hz|w|mm|cm|inch|in)", key):
                keys.add(key)
    return keys


def keys_overlap(a: Set[str], b: Set[str]) -> bool:
    """Equal codes, or one extends the other with a suffix (WH1000XM5 vs WH1000XM5B, the colour code)."""
    return any(x == y or x.startswith(y) or y.startswith(x) for x in a for y in b)


def storage_values(text: str) -> Set[str]:
    return {f"{number}{unit}" for number, unit in _STORAGE.findall((text or "").lower())}


def title_similarity(a: str, b: str) -> float:
    words_a = {w for w in _tokens(a) if w not in GENERIC_WORDS}
    words_b = {w for w in _tokens(b) if w not in GENERIC_WORDS}
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    sequence = SequenceMatcher(None, " ".join(sorted(words_a)), " ".join(sorted(words_b))).ratio()
    return max(overlap * 0.9, sequence)


def match_score(reference: str, reference_model: Optional[str], candidate: str) -> Tuple[float, Optional[str]]:
    """Returns (score 0..1, note about a variant difference)."""
    score = title_similarity(reference, candidate)
    ref_keys = model_keys(f"{reference} {reference_model or ''}")
    cand_keys = model_keys(candidate)
    if ref_keys and cand_keys:
        if keys_overlap(ref_keys, cand_keys):
            score = min(1.0, max(score, 0.75) + 0.15)
        else:
            # Both titles name a model code and they differ (e.g. WH-1000XM5 vs WH-1000XM4): another product.
            score = min(score, 0.3)

    ref_editions = EDITION_WORDS & set(_tokens(reference))
    cand_editions = EDITION_WORDS & set(_tokens(candidate))
    if ref_editions != cand_editions:
        score *= 0.4

    note = None
    ref_storage, cand_storage = storage_values(reference), storage_values(candidate)
    if ref_storage and cand_storage and ref_storage != cand_storage:
        score *= 0.7
        note = "Different variant: " + ", ".join(sorted(cand_storage))
    return round(score, 3), note


def price_outliers(prices: Iterable[Optional[float]], anchor: Optional[float] = None) -> Tuple[float, float]:
    """Bounds outside which a price is probably a different variant, an accessory or stale data."""
    values = [p for p in prices if p]
    if anchor:
        values.append(anchor)
    if not values:
        return 0.0, float("inf")
    middle = anchor or median(values)
    return middle * 0.5, middle * 1.8
