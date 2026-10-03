"""Creates tolmol.ai's tables and indexes: python -m scripts.init_db"""

import sys

from tolmol.db.session import init_db
from tolmol.errors import DatabaseUnavailable

if __name__ == "__main__":
    try:
        init_db()
    except DatabaseUnavailable as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Database schema is ready.")
