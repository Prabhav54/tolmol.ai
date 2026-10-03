"""Hybrid RAG query pipeline: route -> retrieve (pgvector or SQL) -> closed-domain synthesis."""

import time
from contextlib import contextmanager
from typing import Dict, Optional

from api.schemas import QueryResponse
from core.config import settings
from core.exceptions import EmbeddingError
from core.logger import get_logger
from engines import sql_engine
from engines.embeddings import embed_query
from engines.router import SEMANTIC, route_query
from engines.synthesis import fallback_answer, summarize_aggregate, synthesize_answer
from engines.vector_engine import semantic_search

logger = get_logger(__name__)


class _Timer:
    def __init__(self):
        self.timings: Dict[str, float] = {}

    @contextmanager
    def stage(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timings[name] = round((time.perf_counter() - start) * 1000, 1)


def run_query(question: str, top_k: Optional[int] = None, synthesize: bool = True) -> QueryResponse:
    timer = _Timer()
    started = time.perf_counter()

    with timer.stage("routing"):
        decision = route_query(question)
    filters = decision.filters
    limit = top_k or filters.limit or settings.SEARCH_TOP_K

    aggregates = None
    sql = None
    if decision.route == SEMANTIC:
        with timer.stage("embedding"):
            vector = embed_query(question)
        with timer.stage("retrieval"):
            products = semantic_search(vector, limit)
    elif filters.aggregate:
        with timer.stage("retrieval"):
            aggregates, sql = sql_engine.aggregate(filters)
        products = []
    else:
        vector = None
        if filters.keywords:
            # Leftover descriptive words ("breathable running shoes") rank the filtered rows semantically.
            try:
                with timer.stage("embedding"):
                    vector = embed_query(" ".join(filters.keywords))
            except EmbeddingError as exc:
                logger.warning(f"Keyword embedding unavailable, using keyword match + rating order: {exc}")
        with timer.stage("retrieval"):
            products, sql = sql_engine.search(filters, vector, limit)

    with timer.stage("synthesis"):
        if aggregates is not None:
            answer, provider = summarize_aggregate(aggregates, filters), "sql"
        elif synthesize:
            answer, provider = synthesize_answer(question, products)
        else:
            answer, provider = (fallback_answer(products) if products else "No matching products."), "none"

    timer.timings["total"] = round((time.perf_counter() - started) * 1000, 1)
    return QueryResponse(
        question=question,
        route=decision.route,
        route_reason=decision.reason,
        filters=filters.to_dict(),
        answer=answer,
        products=products,
        aggregates=aggregates,
        sql=sql,
        synthesis_provider=provider,
        timings_ms=timer.timings,
    )
