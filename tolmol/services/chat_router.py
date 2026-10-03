"""
Routes a product question to the right data source:
  PRICE   -> SQL over listings and price snapshots (exact numbers)
  SPECS   -> SQL over the structured spec table + hybrid search over spec passages
  REVIEWS -> hybrid (keyword + vector) search over review passages
  GENERAL -> hybrid search over everything
Fast keyword rules (English + Hinglish) decide most questions; the LLM classifies the rest.
"""

import re
from dataclasses import dataclass
from typing import Dict, List

from pydantic import BaseModel, Field

from tolmol.ai.llm import generate_structured
from tolmol.errors import ProviderError
from tolmol.logger import get_logger
from tolmol.scraping.platforms import PLATFORMS

logger = get_logger(__name__)

PRICE, SPECS, REVIEWS, GENERAL = "PRICE", "SPECS", "REVIEWS", "GENERAL"

_platform_words = "|".join(re.escape(p.name.lower()) for p in PLATFORMS)

RULES: Dict[str, List[str]] = {
    PRICE: [
        r"\bprices?\b", r"\bcost\b", r"\bcheap\w*", r"\blowest\b", r"\bhighest\b", r"\bexpensive\b", r"\bdiscount",
        r"\bdeals?\b", r"\bmrp\b", r"\bsav(e|ing)", r"\bwhere (to|should i|can i) buy\b", r"\bwhich (store|site|platform)",
        r"\bbuy (it )?from\b", r"\bhistory\b", r"\btrend\b", r"\bdrop", r"\bwait\b", r"₹", r"\brs\.?\s?\d",
        r"\bkit(na|ne|ni) (ka|ki|ke|me|mein|main)\b", r"\bdaam\b", r"\bsast[ai]\b", r"\bmeh?nga\b", r"\bkab (le|kharid)",
        rf"\b({_platform_words})\b",
    ],
    SPECS: [
        r"\bspec", r"\bbattery\b", r"\bmah\b", r"\bcamera\b", r"\bmp\b", r"\bdisplay\b", r"\bscreen\b", r"\binch",
        r"\bresolution\b", r"\brefresh\b", r"\bhz\b", r"\bprocessor\b", r"\bchip(set)?\b", r"\bcpu\b", r"\bgpu\b",
        r"\bram\b", r"\bstorage\b", r"\bweigh", r"\bdimension", r"\bsize\b", r"\bmaterial\b", r"\bwarranty\b",
        r"\bwater(proof| resistant)\b", r"\bip\d\d\b", r"\bbluetooth\b", r"\bwi-?fi\b", r"\bcharg", r"\bwatt",
        r"\bport\b", r"\busb\b", r"\bandroid\b", r"\bios\b", r"\bfeatures?\b", r"\bcolou?rs?\b", r"\bcompatib",
        r"\bsensor\b", r"\bdriver\b", r"\banc\b", r"\bnoise cancel", r"\bcodec\b", r"\bcapacity\b", r"\bpower\b",
        r"\bsupport", r"\bkitni (battery|ram|storage)\b", r"\bkya (features|specs)\b",
    ],
    REVIEWS: [
        r"\breview", r"\bratings?\b", r"\bworth\b", r"\bgood\b", r"\bbad\b", r"\bquality\b", r"\bdurab", r"\bproblems?\b",
        r"\bissues?\b", r"\bcomplain", r"\bheat", r"\blag", r"\bpros\b", r"\bcons\b", r"\brecommend", r"\bshould i buy\b",
        r"\b(people|users|buyers|customers) say\b", r"\bexperience\b", r"\breliab", r"\bcomfort", r"\bvs\b",
        r"\bkaisa\b", r"\bkaisi\b", r"\bkaise\b", r"\ba(c)?cha\b", r"\bachha\b", r"\bbekar\b", r"\bbakwas\b",
        r"\btheek\b", r"\bsahi\b", r"\blena chahiye\b",
    ],
}
_COMPILED = {route: [re.compile(p) for p in patterns] for route, patterns in RULES.items()}
_HINGLISH = re.compile(
    r"\b(kya|hai|hain|kitna|kitne|kitni|kaisa|kaisi|kaise|kab|lena|chahiye|mein|ka|ki|ke|nahi|acha|accha|"
    r"achha|bekar|sasta|mehnga|daam|bhai|yaar|iska|iski|isme)\b"
)


@dataclass
class ChatRoute:
    route: str
    source: str  # rules | llm
    question: str  # English version used for retrieval
    language: str  # english | hinglish


class _LLMRoute(BaseModel):
    route: str = Field(description="PRICE, SPECS, REVIEWS or GENERAL")
    english_question: str = Field(description="The question rewritten as clear English")


def detect_language(question: str) -> str:
    return "hinglish" if len(_HINGLISH.findall(question.lower())) >= 1 else "english"


def rule_route(question: str) -> Dict[str, int]:
    text = question.lower()
    return {route: sum(1 for p in patterns if p.search(text)) for route, patterns in _COMPILED.items()}


def route_question(question: str, use_llm: bool = True) -> ChatRoute:
    language = detect_language(question)
    scores = rule_route(question)
    top = max(scores.values())
    if top > 0:
        winners = [route for route in (PRICE, SPECS, REVIEWS) if scores[route] == top]
        decision = ChatRoute(winners[0], "rules", question, language)
        # Hinglish questions are still retrieved better in English.
        if language == "hinglish" and use_llm:
            decision.question = _translate(question) or question
    elif use_llm:
        decision = _llm_route(question, language)
    else:
        decision = ChatRoute(GENERAL, "rules", question, language)
    logger.info(f"Chat routed to {decision.route} via {decision.source} ({language}): {question!r}")
    return decision


def _llm_route(question: str, language: str) -> ChatRoute:
    try:
        result = generate_structured(
            "Classify a shopper's question about one product. PRICE = price, deals, which store, price history, "
            "when to buy. SPECS = technical specifications or features. REVIEWS = opinions, quality, problems, "
            "whether it's worth it. GENERAL = anything else. The question may be Hinglish.\n\n"
            f"Question: {question}",
            _LLMRoute,
        )
        route = result.route.upper() if result.route.upper() in (PRICE, SPECS, REVIEWS, GENERAL) else GENERAL
        return ChatRoute(route, "llm", result.english_question or question, language)
    except ProviderError as exc:
        logger.warning(f"LLM routing unavailable: {exc}")
        return ChatRoute(GENERAL, "rules", question, language)


def _translate(question: str) -> str:
    try:
        return _llm_route(question, "hinglish").question
    except Exception:
        return question
