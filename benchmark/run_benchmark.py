"""CLI: python -m benchmark.run_benchmark [--samples 100] [--end-to-end] [--routing-only] [--out report.json]"""

import argparse
import json
import sys
from pathlib import Path

from benchmark.evaluator import evaluate_routing, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="tolmol.ai routing accuracy and retrieval latency benchmark")
    parser.add_argument("--samples", type=int, default=50, help="Number of timed vector queries")
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument("--end-to-end", action="store_true", help="Also time embedding API calls")
    parser.add_argument("--routing-only", action="store_true", help="Skip the database; only test the router")
    parser.add_argument("--out", type=Path, help="Write the JSON report to this file")
    args = parser.parse_args()

    if args.routing_only:
        report = {"routing": evaluate_routing()}
    else:
        report = run_benchmark(args.samples, args.top_k, args.end_to_end)

    output = json.dumps(report, indent=2)
    print(output)
    if args.out:
        args.out.write_text(output, encoding="utf-8")

    routing = report["routing"]
    print(f"\nRouting accuracy: {routing['correct']}/{routing['total']} ({routing['accuracy']:.0%})", file=sys.stderr)
    latency = report.get("retrieval_latency_ms", {})
    if "p95" in latency:
        verdict = "PASS" if latency["meets_target"] else "FAIL"
        print(
            f"Retrieval p50={latency['p50']}ms p95={latency['p95']}ms over "
            f"{report['catalog']['embedded']} embeddings -> {verdict} (<{latency['target_ms']:.0f}ms)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
