"""
Loads products into the catalog through the normal dedup + embedding pipeline.

  python -m scripts.seed_catalog --dummyjson              # ~190 public demo products (dummyjson.com)
  python -m scripts.seed_catalog --file my_catalog.json   # a JSON list of ProductData objects
  python -m scripts.seed_catalog --synthetic 5000         # generated products for load / latency testing

Re-running is safe: products already in the catalog are skipped by their URL hash.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Iterable, List

import httpx

from api.services.ingestion import ingest_products, summarize
from scraper.models import ProductData

BATCH_SIZE = 100
# DummyJSON lists prices in USD; converted at a fixed demo rate so the catalog is in one currency.
USD_TO_INR = 83.0


def load_dummyjson() -> List[ProductData]:
    response = httpx.get("https://dummyjson.com/products", params={"limit": 0}, timeout=30)
    response.raise_for_status()
    items = []
    for raw in response.json()["products"]:
        items.append(
            ProductData(
                url=f"https://dummyjson.com/products/{raw['id']}",
                platform="DummyJSON (demo)",
                title=raw["title"],
                brand=raw.get("brand"),
                category=raw.get("category", "").replace("-", " ").title() or None,
                description=raw.get("description"),
                price=round(raw["price"] * USD_TO_INR),
                rating=raw.get("rating"),
                rating_count=len(raw.get("reviews") or []) or None,
                image_url=raw.get("thumbnail"),
                in_stock=(raw.get("stock") or 0) > 0,
            )
        )
    return items


def load_file(path: Path) -> List[ProductData]:
    return [ProductData(**item) for item in json.loads(path.read_text(encoding="utf-8"))]


SYNTHETIC_CATALOG = {
    "Running Shoes": (["Nike", "Adidas", "Puma", "ASICS", "Campus"], ["breathable mesh", "cushioned", "lightweight", "trail grip"], (1200, 9000)),
    "T-Shirts": (["H&M", "Roadster", "Snitch", "Bewakoof", "US Polo"], ["cotton", "oversized", "slim fit", "quick-dry"], (299, 1499)),
    "Headphones": (["boAt", "Sony", "JBL", "OnePlus", "Noise"], ["noise cancelling", "wireless", "over-ear", "40h battery"], (999, 24999)),
    "Smartwatches": (["Noise", "Fire-Boltt", "Amazfit", "Samsung", "boAt"], ["AMOLED", "GPS", "SpO2 tracking", "Bluetooth calling"], (1499, 29999)),
    "Backpacks": (["Wildcraft", "American Tourister", "Skybags", "Safari"], ["waterproof", "laptop sleeve", "35L", "anti-theft"], (799, 4999)),
    "Kurtas": (["Biba", "Manyavar", "Fabindia", "W"], ["cotton", "festive", "embroidered", "straight cut"], (499, 3999)),
}
PLATFORM_NAMES = ["Amazon", "Flipkart", "Myntra", "AJIO"]


def generate_synthetic(count: int, seed: int = 7) -> List[ProductData]:
    rng = random.Random(seed)
    items = []
    categories = list(SYNTHETIC_CATALOG)
    for index in range(count):
        category = categories[index % len(categories)]
        brands, features, (low, high) = SYNTHETIC_CATALOG[category]
        brand = rng.choice(brands)
        picked = rng.sample(features, 2)
        title = f"{brand} {picked[0].title()} {category[:-1] if category.endswith('s') else category} #{index}"
        items.append(
            ProductData(
                url=f"https://example.com/synthetic/{index}",
                platform=rng.choice(PLATFORM_NAMES) + " (synthetic)",
                title=title,
                brand=brand,
                category=category,
                description=f"{title}. Features {picked[0]} and {picked[1]} design. Synthetic product for load testing.",
                price=round(rng.uniform(low, high), -1),
                rating=round(rng.uniform(3.0, 5.0), 1),
                rating_count=rng.randint(5, 5000),
                in_stock=rng.random() > 0.1,
            )
        )
    return items


def batched(items: List[ProductData], size: int) -> Iterable[List[ProductData]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dummyjson", action="store_true")
    source.add_argument("--file", type=Path)
    source.add_argument("--synthetic", type=int, metavar="N")
    parser.add_argument("--refresh", action="store_true", help="Update products that already exist")
    args = parser.parse_args()

    if args.dummyjson:
        items = load_dummyjson()
    elif args.file:
        items = load_file(args.file)
    else:
        items = generate_synthetic(args.synthetic)

    totals: dict = {}
    for number, batch in enumerate(batched(items, BATCH_SIZE), start=1):
        summary = summarize(ingest_products(batch, refresh=args.refresh))
        for status, count in summary.items():
            totals[status] = totals.get(status, 0) + count
        print(f"batch {number}: {summary}")
    print(f"Done. {len(items)} products processed: {totals}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
