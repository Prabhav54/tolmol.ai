"""
Prepares the database: python -m scripts.init_db [--archive-legacy]

--archive-legacy moves tables from the pre-2.0 layout (products / product_links / price_history /
product_reviews) into a `legacy` schema. Their data, indexes and sequences move with them; nothing is
deleted. Recover with:  ALTER TABLE legacy.<name> SET SCHEMA public;
"""

import argparse
import sys

from sqlalchemy import text

from core.exceptions import DatabaseConnectionError
from db.session import get_engine, init_db

LEGACY_TABLES = ["product_links", "price_history", "product_reviews", "products"]


def _is_current_layout(conn) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'products' AND column_name = 'url_hash'"
            )
        ).first()
    )


def archive_legacy_tables() -> list:
    moved = []
    with get_engine().begin() as conn:
        if _is_current_layout(conn):
            return moved
        existing = {
            row[0]
            for row in conn.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")
            )
        }
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS legacy"))
        for table in LEGACY_TABLES:
            if table in existing:
                conn.execute(text(f'ALTER TABLE "{table}" SET SCHEMA legacy'))
                moved.append(table)
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive-legacy", action="store_true", help="Move old-layout tables into schema 'legacy'")
    args = parser.parse_args()

    if args.archive_legacy:
        moved = archive_legacy_tables()
        print(f"Archived to schema 'legacy': {', '.join(moved)}" if moved else "No legacy tables to archive.")

    try:
        init_db()
    except DatabaseConnectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print("Database schema is ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
