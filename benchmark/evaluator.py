"""Measures routing accuracy against the golden set and retrieval latency over the live catalog."""

import json
import random
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select

from db.models import products
from db.session import get_engine
from engines.embeddings import embed_query
from engines.router import route_query
from engines.vector_engine import semantic_search

GOLDEN_SET_PATH = Path(__file__).with_name("golden_set.json")
LATENCY_TARGET_MS = 300.0


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> List[Dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_routing(golden: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    golden = golden or load_golden_set()
    failures = []
    for case in golden:
        decision = route_query(case["query"])
        if decision.route != case["expected_route"]:
            failures.append({"query": case["query"], "expected": case["expected_route"], "got": decision.route})
    correct = len(golden) - len(failures)
    return {
        "total": len(golden),
        "correct": correct,
        "accuracy": round(correct / len(golden), 4) if golden else 0.0,
        "failures": failures,
    }


def _percentiles(samples_ms: List[float]) -> Dict[str, float]:
    ordered = sorted(samples_ms)

    def pct(p: float) -> float:
        index = min(len(ordered) - 1, max(0, round(p / 100 * len(ordered)) - 1))
        return round(ordered[index], 2)

    return {
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "mean": round(statistics.fmean(ordered), 2),
        "max": round(ordered[-1], 2),
    }


def catalog_size() -> Dict[str, int]:
    with get_engine().connect() as conn:
        total, embedded = conn.execute(
            select(func.count(products.c.id), func.count(products.c.embedding))
        ).one()
    return {"products": total, "embedded": embedded}


def measure_retrieval_latency(samples: int = 50, top_k: int = 6) -> Dict[str, Any]:
    """
    Times pgvector top-k retrieval only. Query vectors are taken from stored product embeddings
    (with a little noise), so the measurement needs no embedding API calls.
    """
    with get_engine().connect() as conn:
        vectors = [
            list(row[0])
            for row in conn.execute(
                select(products.c.embedding)
                .where(products.c.embedding.isnot(None))
                .order_by(func.random())
                .limit(min(samples, 200))
            )
        ]
    if not vectors:
        return {"error": "No embedded products in the catalog yet. Ingest or seed products first."}

    rng = random.Random(42)
    queries = [[value + rng.gauss(0, 0.01) for value in rng.choice(vectors)] for _ in range(samples)]

    for vector in queries[:3]:  # warm the connection pool and index pages
        semantic_search(vector, top_k, min_similarity=-1)

    timings = []
    for vector in queries:
        start = time.perf_counter()
        semantic_search(vector, top_k, min_similarity=-1)
        timings.append((time.perf_counter() - start) * 1000)

    stats = _percentiles(timings)
    return {
        "samples": samples,
        "top_k": top_k,
        **stats,
        "target_ms": LATENCY_TARGET_MS,
        "meets_target": stats["p95"] < LATENCY_TARGET_MS,
    }


def measure_end_to_end(top_k: int = 6) -> Dict[str, Any]:
    """Embedding + retrieval latency for the semantic queries in the golden set (uses the embedding API)."""
    queries = [case["query"] for case in load_golden_set() if case["expected_route"] == "SEMANTIC"]
    embed_ms, retrieval_ms = [], []
    for query in queries:
        start = time.perf_counter()
        vector = embed_query(query, use_cache=False)
        middle = time.perf_counter()
        semantic_search(vector, top_k)
        end = time.perf_counter()
        embed_ms.append((middle - start) * 1000)
        retrieval_ms.append((end - middle) * 1000)
    return {"queries": len(queries), "embedding": _percentiles(embed_ms), "retrieval": _percentiles(retrieval_ms)}


def run_benchmark(samples: int = 50, top_k: int = 6, end_to_end: bool = False) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "catalog": catalog_size(),
        "routing": evaluate_routing(),
        "retrieval_latency_ms": measure_retrieval_latency(samples, top_k),
    }
    if end_to_end:
        report["end_to_end_ms"] = measure_end_to_end(top_k)
    return report
