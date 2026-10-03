"""Chat with a product: route the question, fetch facts from SQL and/or hybrid search, answer only from them."""

import re
import time
from typing import Any, Dict, List

from sqlalchemy import select, text

from tolmol.ai.llm import generate_text
from tolmol.db.models import tracked_products
from tolmol.db.session import get_engine
from tolmol.errors import NotFound, ProviderError
from tolmol.schemas import ChatTurn
from tolmol.services.chat_router import GENERAL, PRICE, REVIEWS, SPECS, route_question
from tolmol.services.insights import build_insights
from tolmol.services.retrieval import hybrid_search

PRICE_SQL = """
SELECT l.platform, l.price, l.mrp, l.in_stock, l.link_type, l.price_source, l.last_seen_at,
       MIN(s.price) AS lowest_recorded, MAX(s.price) AS highest_recorded,
       COUNT(s.id) AS checks, MIN(s.captured_at) AS tracked_since
FROM listings l
LEFT JOIN price_snapshots s ON s.listing_id = l.id
WHERE l.product_id = :product_id
GROUP BY l.id
ORDER BY l.price ASC NULLS LAST
""".strip()

SPECS_SQL = """
SELECT spec->>'group' AS "group", spec->>'name' AS name, spec->>'value' AS value
FROM tracked_products p, jsonb_array_elements(p.specs) AS spec
WHERE p.id = :product_id
  AND (spec->>'name' ILIKE ANY(:patterns) OR spec->>'group' ILIKE ANY(:patterns) OR spec->>'value' ILIKE ANY(:patterns))
""".strip()

_SPEC_STOP = {"what", "which", "does", "have", "this", "that", "the", "how", "much", "many", "kitni", "kitna", "kya", "hai", "iska", "iski"}

SYSTEM_PROMPT = (
    "You are tolmol.ai's product assistant. Answer the shopper's question about ONE product using only the FACTS "
    "provided. Quote prices exactly in ₹ with the store name. If the facts don't contain the answer, say you don't "
    "have that information instead of guessing. Be concise: 2-5 sentences or a short list. No markdown headings."
)


def _money(value) -> str:
    return f"₹{float(value):,.0f}" if value is not None else "price unknown"


def _price_facts(product_id: int) -> str:
    with get_engine().connect() as conn:
        rows = conn.execute(text(PRICE_SQL), {"product_id": product_id}).mappings().all()
    if not rows:
        return "No store prices recorded."
    lines = []
    for r in rows:
        parts = [f"{r['platform']}: current {_money(r['price'])}"]
        if r["mrp"]:
            parts.append(f"MRP {_money(r['mrp'])}")
        if r["in_stock"] is False:
            parts.append("out of stock")
        if r["checks"]:
            parts.append(
                f"lowest recorded {_money(r['lowest_recorded'])}, highest {_money(r['highest_recorded'])} over "
                f"{r['checks']} checks since {r['tracked_since']:%d %b %Y}"
            )
        parts.append(f"last checked {r['last_seen_at']:%d %b %Y}")
        lines.append(", ".join(parts))
    return "\n".join(lines)


def _spec_facts(product_id: int, question: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in _SPEC_STOP]
    if not words:
        return ""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(SPECS_SQL), {"product_id": product_id, "patterns": [f"%{w}%" for w in words]}
        ).mappings().all()
    return "\n".join(f"{r['group']} / {r['name']}: {r['value']}" for r in rows)


def _review_facts(product_id: int) -> str:
    with get_engine().connect() as conn:
        summary = conn.execute(
            select(tracked_products.c.review_summary).where(tracked_products.c.id == product_id)
        ).scalar()
    if not summary:
        return ""
    return (
        f"Review sentiment: {summary.get('positive_pct')}% positive, {summary.get('neutral_pct')}% neutral, "
        f"{summary.get('negative_pct')}% negative. Overall: {summary.get('overall')}"
    )


def answer(product_id: int, question: str, history: List[ChatTurn]) -> Dict[str, Any]:
    timings: Dict[str, float] = {}
    started = time.perf_counter()

    with get_engine().connect() as conn:
        product = conn.execute(
            select(tracked_products.c.title, tracked_products.c.variant, tracked_products.c.insights_ready_at).where(
                tracked_products.c.id == product_id
            )
        ).mappings().first()
    if product is None:
        raise NotFound("Product not found.")

    t = time.perf_counter()
    decision = route_question(question)
    timings["routing"] = round((time.perf_counter() - t) * 1000, 1)

    if decision.route != PRICE and product["insights_ready_at"] is None:
        t = time.perf_counter()
        build_insights(product_id)
        timings["research"] = round((time.perf_counter() - t) * 1000, 1)

    t = time.perf_counter()
    facts: List[str] = []
    sql_used: List[str] = []
    passages: List[Dict[str, Any]] = []
    method: Dict[str, Any] = {}
    if decision.route == PRICE:
        facts.append("STORE PRICES (from our price tracker):\n" + _price_facts(product_id))
        sql_used.append(PRICE_SQL)
    if decision.route == SPECS:
        spec_rows = _spec_facts(product_id, decision.question)
        sql_used.append(SPECS_SQL)
        if spec_rows:
            facts.append("MATCHING SPECIFICATIONS:\n" + spec_rows)
    if decision.route in (SPECS, REVIEWS, GENERAL):
        kinds = {SPECS: ["spec", "overview"], REVIEWS: ["review"], GENERAL: ["overview", "spec", "review"]}[decision.route]
        passages, method = hybrid_search(product_id, decision.question, kinds)
        if decision.route == REVIEWS:
            review_line = _review_facts(product_id)
            if review_line:
                facts.append(review_line)
        if passages:
            facts.append("RELEVANT PASSAGES:\n" + "\n".join(f"- {p['content']}" for p in passages))
    timings["retrieval"] = round((time.perf_counter() - t) * 1000, 1)

    name = product["title"] + (f" ({product['variant']})" if product["variant"] else "")
    convo = "\n".join(f"{turn.role}: {turn.content[:400]}" for turn in history[-4:])
    language = (
        "Reply in Hinglish (Hindi written in Roman script, mixed with English), matching the shopper."
        if decision.language == "hinglish" else "Reply in English."
    )
    prompt = (
        f"PRODUCT: {name}\n\nFACTS:\n" + ("\n\n".join(facts) or "(no facts found)") +
        (f"\n\nEARLIER CONVERSATION:\n{convo}" if convo else "") +
        f"\n\nSHOPPER QUESTION: {question}\n{language}"
    )

    t = time.perf_counter()
    try:
        reply = generate_text(prompt, system=SYSTEM_PROMPT, max_tokens=500)
    except ProviderError:
        reply = "I can't reach the AI model right now. Here is what I found:\n" + ("\n\n".join(facts) or "Nothing relevant.")
    timings["answer"] = round((time.perf_counter() - t) * 1000, 1)
    timings["total"] = round((time.perf_counter() - started) * 1000, 1)

    return {
        "answer": reply,
        "route": decision.route,
        "route_source": decision.source,
        "language": decision.language,
        "sql": sql_used,
        "passages": [{"kind": p["kind"], "content": p["content"]} for p in passages],
        "retrieval": method,
        "timings_ms": timings,
    }
