"""Hybrid retrieval over a product's passages: pgvector similarity + Postgres full-text, fused and reranked."""

import re
from typing import Any, Dict, List, Sequence, Tuple

from pydantic import BaseModel
from sqlalchemy import func, select

from tolmol.ai.embeddings import embed_query
from tolmol.ai.llm import generate_structured
from tolmol.config import settings
from tolmol.db.models import product_chunks
from tolmol.db.session import get_engine
from tolmol.errors import ProviderError
from tolmol.logger import get_logger

logger = get_logger(__name__)

CANDIDATES_PER_METHOD = 12
RRF_K = 60  # standard reciprocal-rank-fusion constant
_STOP = {"the", "and", "for", "with", "this", "that", "what", "how", "does", "is", "are", "its", "it's", "can", "you"}


class _Rerank(BaseModel):
    order: List[int]


def keyword_query(question: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2 and w not in _STOP]
    return " or ".join(dict.fromkeys(words))


def _vector_hits(product_id: int, question: str, kinds: Sequence[str]) -> List[Dict[str, Any]]:
    vector = embed_query(question)
    distance = product_chunks.c.embedding.cosine_distance(vector)
    stmt = (
        select(product_chunks.c.id, product_chunks.c.kind, product_chunks.c.content)
        .where(product_chunks.c.product_id == product_id, product_chunks.c.kind.in_(kinds))
        .order_by(distance)
        .limit(CANDIDATES_PER_METHOD)
    )
    with get_engine().connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings()]


def _keyword_hits(product_id: int, question: str, kinds: Sequence[str]) -> List[Dict[str, Any]]:
    terms = keyword_query(question)
    if not terms:
        return []
    tsquery = func.websearch_to_tsquery("english", terms)
    stmt = (
        select(product_chunks.c.id, product_chunks.c.kind, product_chunks.c.content)
        .where(
            product_chunks.c.product_id == product_id,
            product_chunks.c.kind.in_(kinds),
            product_chunks.c.tsv.op("@@")(tsquery),
        )
        .order_by(func.ts_rank(product_chunks.c.tsv, tsquery).desc())
        .limit(CANDIDATES_PER_METHOD)
    )
    with get_engine().connect() as conn:
        return [dict(row) for row in conn.execute(stmt).mappings()]


def reciprocal_rank_fusion(*rankings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scores: Dict[int, float] = {}
    passages: Dict[int, Dict[str, Any]] = {}
    for ranking in rankings:
        for rank, passage in enumerate(ranking):
            scores[passage["id"]] = scores.get(passage["id"], 0.0) + 1.0 / (RRF_K + rank + 1)
            passages[passage["id"]] = passage
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [{**passages[pid], "score": round(scores[pid], 5)} for pid in ordered]


def _rerank(question: str, passages: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    listing = "\n".join(f"[{i}] {p['content'][:500]}" for i, p in enumerate(passages))
    result = generate_structured(
        f"Question: {question}\n\nRank the passages by how directly they help answer the question. Return the "
        f"passage numbers, most useful first, at most {k}. Leave out irrelevant passages.\n\n{listing}",
        _Rerank,
    )
    picked = [passages[i] for i in dict.fromkeys(result.order) if 0 <= i < len(passages)]
    return picked[:k] or passages[:k]


def hybrid_search(product_id: int, question: str, kinds: Sequence[str], k: int = 0) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    k = k or settings.CHAT_TOP_K
    try:
        vector_hits = _vector_hits(product_id, question, kinds)
    except ProviderError as exc:
        logger.warning(f"Vector search unavailable, using keyword search only: {exc}")
        vector_hits = []
    keyword_hits = _keyword_hits(product_id, question, kinds)
    fused = reciprocal_rank_fusion(vector_hits, keyword_hits)

    reranked = False
    if settings.RERANK and len(fused) > k:
        try:
            fused = _rerank(question, fused, k)
            reranked = True
        except ProviderError as exc:
            logger.warning(f"Rerank skipped: {exc}")
    method = {"vector_hits": len(vector_hits), "keyword_hits": len(keyword_hits), "reranked": reranked}
    return fused[:k], method
