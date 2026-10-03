"""Turns a natural-language shopping query into structured, SQL-safe filters.

Every value extracted here becomes a bound parameter in a SQLAlchemy query; the user's text is
never spliced into SQL. Matched phrases are blanked out as they are consumed, so the leftover
words become the semantic keywords ("running shoes under ₹2000" -> keywords ["running", "shoes"]).
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from scraper.dedup import PLATFORMS

# A price: optional currency prefix, digits with commas/decimals, optional "k", optional currency suffix.
# The trailing lookahead keeps specs like "500w" or "120hz" from being read as prices.
_NUM = r"(?:₹|rs\.?|inr)?\s*(?P<{name}>\d[\d,]*(?:\.\d+)?)\s*(?P<{name}_k>k)?(?:\s*(?:rupees|rs\b|inr\b|/-))?(?![a-z0-9])"


def _num(name: str) -> str:
    return _NUM.format(name=name)


_PRICE_WORD = r"(?:(?:price|priced|cost|costing|budget)\s*(?:of|is|at)?\s*)?"
_RATING_VALUE = r"(?P<rating>[0-5](?:\.\d+)?)"

PRICE_BETWEEN = re.compile(rf"\b(?:between|from)\s+{_PRICE_WORD}{_num('low')}\s*(?:and|to|-)\s*{_num('high')}")
PRICE_MAX = re.compile(
    rf"(?:\b(?:under|below|less than|cheaper than|within|upto|up to|at most|not more than|no more than"
    rf"|max(?:imum)?|budget(?: of)?)|<=?)\s*{_PRICE_WORD}{_num('value')}"
)
PRICE_MIN = re.compile(
    rf"(?:\b(?:above|over|more than|greater than|at least|min(?:imum)?|starting(?: from| at)?)|>=?)\s*"
    rf"{_PRICE_WORD}{_num('value')}"
)

RATING_MIN = [
    re.compile(
        rf"\b(?:rating|rated|stars?)\s*(?:of\s*)?(?:>=|>|=>|above|over|more than|greater than|at least|min(?:imum)?)"
        rf"\s*(?:of\s*)?{_RATING_VALUE}(?:\s*stars?)?"
    ),
    re.compile(
        rf"\b(?:at least|minimum|min)?\s*{_RATING_VALUE}\s*(?:\+|plus)?\s*(?:stars?|star rating|rating)"
        rf"(?:\s*(?:and|or|&)\s*(?:above|up|more|higher))?"
    ),
]
RATING_MAX = re.compile(
    rf"\b(?:rating|rated)\s*(?:<=|<|below|under|less than)\s*{_RATING_VALUE}(?:\s*stars?)?"
)

SORTS = [
    (re.compile(r"\b(?:cheapest|lowest[- ]priced?|lowest price|least expensive|most affordable|cheap)\b"), "price_asc"),
    (re.compile(r"\b(?:most expensive|costliest|priciest|highest[- ]priced?|highest price)\b"), "price_desc"),
    (
        re.compile(r"\b(?:top|best|highest|highly)(?:\s+(?P<n>\d{1,2}))?[- ]rated\b|\bbest reviewed\b|\bhighest rating\b"),
        "rating_desc",
    ),
]

AGGREGATES = [
    # A bare "count" is not enough ("high thread count bedsheets" is a product search).
    (
        re.compile(
            r"\b(?:how many|number of|total number of|total (?:products|items)"
            r"|count (?:of|the|all|products|items))\b|^\s*count\b"
        ),
        "count",
    ),
    (re.compile(r"\b(?:average|avg|mean)\s+(?:customer\s+)?rating\b"), "avg_rating"),
    (re.compile(r"\b(?:average|avg|mean)\s+(?:selling\s+)?(?:price|cost)\b|\b(?:average|avg|mean)\b"), "avg_price"),
    (re.compile(r"\b(?:minimum|min)\s+price\b"), "min_price"),
    (re.compile(r"\b(?:maximum|max)\s+price\b"), "max_price"),
]

GROUP_BY = re.compile(
    r"\b(?:grouped by|group by|broken down by|by|per|for each|each|across)\s+"
    r"(?P<dim>platform|category|categories|brand|retailer|store|site|website)s?\b"
)
_GROUP_ALIASES = {"retailer": "platform", "store": "platform", "site": "platform", "website": "platform",
                  "categories": "category"}

# "5 cheapest ..." (number before a sort word) and "top 5 ..." (number after a lead-in word).
LIMIT_BEFORE = re.compile(r"\b(?P<n>\d{1,2})\s+(?=(?:cheapest|best|top|most|highest|lowest|products|items|options)\b)")
LIMIT_AFTER = re.compile(r"\b(?:top|first|show(?: me)?|list|best)\s+(?P<n>\d{1,2})\b")

IN_STOCK = re.compile(r"\b(?:in stock|available now|currently available)\b")

_PLATFORM_PATTERNS = {
    name: re.compile(rf"\b(?:on |from |at )?{re.escape(key)}\b") for key, name in PLATFORMS.items()
}

STOPWORDS = set(
    """
    a an the and or of in on at to for from by with without per each is are was be been am do does did have has
    i im i'm me my we us our you your it its this that these those there which what whats who whom how can could
    please show find list get give search searching look looking want need needs buy buying recommend suggest
    some any all only also just like around about approx approximately more less than much many most least
    product products item items option options stuff thing things catalog catalogue inventory store stores
    price prices priced cost costs costing rs inr rupee rupees budget value
    rating ratings rated rate star stars review reviews reviewed
    cheap cheaper cheapest affordable expensive costly best good great top high highly low lowest highest
    under below above over between within upto up plus minimum maximum min max
    count number total average avg mean compare comparison sort sorted order ordered across grouped group
    available stock currently now platform platforms brand brands category categories retailer site website
    """.split()
)


@dataclass
class QueryFilters:
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    max_rating: Optional[float] = None
    platforms: List[str] = field(default_factory=list)
    in_stock_only: bool = False
    sort: Optional[str] = None
    limit: Optional[int] = None
    aggregate: Optional[str] = None
    group_by: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def has_structured_constraints(self) -> bool:
        return any(
            [
                self.min_price is not None,
                self.max_price is not None,
                self.min_rating is not None,
                self.max_rating is not None,
                self.platforms,
                self.in_stock_only,
                self.sort,
                self.aggregate,
                self.group_by,
            ]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in (None, [], False)}


def _price(match: "re.Match", name: str) -> float:
    value = float(match.group(name).replace(",", ""))
    return value * 1000 if match.group(f"{name}_k") else value


class _Consumer:
    """Applies regexes to the query and blanks out each consumed span."""

    def __init__(self, text: str):
        self.text = text

    def take(self, pattern: "re.Pattern", accept: Callable[["re.Match"], bool] = lambda m: True) -> Optional["re.Match"]:
        for match in pattern.finditer(self.text):
            if accept(match):
                self.text = self.text[: match.start()] + " " * (match.end() - match.start()) + self.text[match.end():]
                return match
        return None


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "xes", "sses")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def keyword_stems(keywords: List[str]) -> List[str]:
    return list(dict.fromkeys(_stem(word) for word in keywords))


def parse_query(query: str) -> QueryFilters:
    filters = QueryFilters()
    text = _Consumer(" " + query.lower().replace("’", "'") + " ")

    # Ratings first, so "rating above 4" is not mistaken for a price filter.
    for pattern in RATING_MIN:
        match = text.take(pattern, lambda m: float(m.group("rating")) <= 5)
        if match:
            filters.min_rating = float(match.group("rating"))
            break
    match = text.take(RATING_MAX, lambda m: float(m.group("rating")) <= 5)
    if match:
        filters.max_rating = float(match.group("rating"))

    match = text.take(PRICE_BETWEEN)
    if match:
        filters.min_price, filters.max_price = sorted((_price(match, "low"), _price(match, "high")))
    else:
        match = text.take(PRICE_MAX)
        if match:
            filters.max_price = _price(match, "value")
        match = text.take(PRICE_MIN)
        if match:
            filters.min_price = _price(match, "value")

    match = text.take(GROUP_BY)
    if match:
        dimension = match.group("dim")
        filters.group_by = _GROUP_ALIASES.get(dimension, dimension)

    for pattern, aggregate in AGGREGATES:
        if text.take(pattern):
            filters.aggregate = aggregate
            break
    if filters.group_by and not filters.aggregate:
        filters.aggregate = "avg_price" if re.search(r"\b(?:price|prices|cost)\b", query.lower()) else "count"

    def set_limit(match: Optional["re.Match"]) -> None:
        if match and match.groupdict().get("n"):
            filters.limit = max(1, min(int(match.group("n")), 50))

    set_limit(text.take(LIMIT_BEFORE))
    for pattern, sort in SORTS:
        match = text.take(pattern)
        if match:
            filters.sort = sort
            set_limit(match)
            break
    if filters.limit is None:
        set_limit(text.take(LIMIT_AFTER))

    for name, pattern in _PLATFORM_PATTERNS.items():
        if text.take(pattern):
            filters.platforms.append(name)

    if text.take(IN_STOCK):
        filters.in_stock_only = True

    words = [word.removesuffix("'s") for word in re.findall(r"[a-z][a-z0-9'-]*", text.text)]
    filters.keywords = [w for w in dict.fromkeys(words) if w not in STOPWORDS and len(w) > 1][:8]
    return filters
