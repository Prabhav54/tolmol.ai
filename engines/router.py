from dataclasses import dataclass

from core.logger import get_logger
from engines.query_parser import QueryFilters, parse_query

logger = get_logger(__name__)

SEMANTIC = "SEMANTIC"
SQL = "SQL"


@dataclass
class RouteDecision:
    route: str
    reason: str
    filters: QueryFilters


def route_query(query: str) -> RouteDecision:
    """
    Dispatches a query by intent:
      - SQL: hard constraints (price / rating bounds, platform, stock, sorting) or analytics
        (count / average / group-by). Leftover descriptive words still rank results semantically.
      - SEMANTIC: purely descriptive queries ("breathable summer running wear") go to pgvector.
    """
    filters = parse_query(query)

    if filters.aggregate:
        decision = RouteDecision(SQL, f"Analytics query ({filters.aggregate})", filters)
    elif filters.has_structured_constraints():
        constraints = ", ".join(k for k in filters.to_dict() if k not in ("keywords", "limit"))
        decision = RouteDecision(SQL, f"Structured constraints detected ({constraints})", filters)
    else:
        decision = RouteDecision(SEMANTIC, "Descriptive query with no hard constraints", filters)

    logger.info(f"Routed to {decision.route}: {decision.reason} | filters={filters.to_dict()}")
    return decision
