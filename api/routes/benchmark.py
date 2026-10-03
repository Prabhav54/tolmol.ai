from fastapi import APIRouter

from api.schemas import BenchmarkRequest
from benchmark.evaluator import evaluate_routing, run_benchmark

router = APIRouter(prefix="/benchmark", tags=["Benchmark"])


@router.post("")
def benchmark(payload: BenchmarkRequest):
    """Routing accuracy on the golden set plus pgvector retrieval latency (p50/p95/p99) on the live catalog."""
    return run_benchmark(samples=payload.samples, top_k=payload.top_k, end_to_end=payload.end_to_end)


@router.get("/routing")
def routing_accuracy():
    """Routing accuracy only; needs no database or API keys."""
    return evaluate_routing()
