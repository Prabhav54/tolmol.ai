from fastapi import APIRouter

from api.schemas import QueryRequest, QueryResponse
from api.services.search import run_query
from engines.router import route_query

router = APIRouter(prefix="/query", tags=["Query"])


@router.post("", response_model=QueryResponse)
def query(payload: QueryRequest):
    """Hybrid RAG: route by intent to pgvector or SQL, then answer strictly from catalog results."""
    return run_query(payload.question, top_k=payload.top_k, synthesize=payload.synthesize)


@router.get("/route")
def explain_route(q: str):
    """Shows how a query would be routed and which filters were extracted, without running it."""
    decision = route_query(q)
    return {"query": q, "route": decision.route, "reason": decision.reason, "filters": decision.filters.to_dict()}
