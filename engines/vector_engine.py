from typing import Any, Dict, List, Optional

from sqlalchemy import select, text

from core.config import settings
from db.models import CARD_COLUMNS, products, to_plain
from db.session import get_engine


def semantic_search(
    query_vector: List[float], top_k: int, min_similarity: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Cosine-similarity ranking over the whole catalog, served by the HNSW index."""
    threshold = settings.SEMANTIC_MIN_SIMILARITY if min_similarity is None else min_similarity
    distance = products.c.embedding.cosine_distance(query_vector)
    stmt = (
        select(*CARD_COLUMNS, (1 - distance).label("similarity"))
        .where(products.c.embedding.isnot(None))
        .order_by(distance)
        .limit(top_k)
    )

    with get_engine().begin() as conn:
        conn.execute(text(f"SET LOCAL hnsw.ef_search = {int(settings.HNSW_EF_SEARCH)}"))
        rows = conn.execute(stmt).mappings().all()

    hits = [to_plain(row) for row in rows]
    return [hit for hit in hits if hit["similarity"] >= threshold]
