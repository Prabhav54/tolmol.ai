import re
from core.logger import get_logger

logger = get_logger(__name__)

class Router:
    def __init__(self):
        # Core keywords triggering quantitative calculation paths
        self.sql_triggers = ["count", "how many", "total", "list all", "sum", "average", "mean", "number of"]

    def route_query(self, query: str) -> str:
        """
        Analyzes the context statement and picks the high-efficiency execution platform.
        """
        cleaned_query = query.lower()
        
        # Look for explicit numeric IDs (e.g. 3-digit identifiers like 101, 502)
        has_product_id = bool(re.search(r'\b\d{3,}\b', cleaned_query))
        has_sql_keyword = any(keyword in cleaned_query for keyword in self.sql_triggers)
        
        if has_sql_keyword or has_product_id:
            logger.info(f"Query routed to: [SQL Engine] (Trigger matched on input string)")
            return "SQL"
            
        logger.info(f"Query routed to: [Vector Engine] (Semantic approach inferred)")
        return "VECTOR"