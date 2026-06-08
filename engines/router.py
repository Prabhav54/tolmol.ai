import re
from core.logger import get_logger

logger = get_logger(__name__)

class Router:
    def __init__(self):
        # 1. Semantic Override Keywords: If these are present, always use Vector
        self.vector_triggers = [
            r"\boffer", r"\bdiscount", r"\bcoupon", r"\bfeature", r"\breview", 
            r"\bspec", r"\bdetail", r"\bpolicy", r"\bwarranty", r"\bquality",
            r"\bcolor", r"\bmaterial", r"\bsize", r"\bcompare"
        ]
        
        # 2. Quantitative SQL Keywords: Uses \b to ensure exact word matches
        # This prevents "discount" from accidentally triggering "count"
        self.sql_triggers = [
            r"\bcount\b", r"\bhow many\b", r"\btotal\b", r"\bsum\b", 
            r"\baverage\b", r"\bmean\b", r"\bnumber of\b"
        ]

    def route_query(self, query: str) -> str:
        """
        Intelligently routes the user query to the Vector Engine (Semantic) 
        or SQL Engine (Quantitative) based on intent.
        """
        cleaned_query = query.lower()
        
        # Step 1: Check for explicit semantic features/offers first
        if any(re.search(pattern, cleaned_query) for pattern in self.vector_triggers):
            logger.info("Query routed to: [Vector Engine] (Semantic override keyword matched)")
            return "VECTOR"
            
        # Step 2: Check for mathematical/aggregation triggers safely
        if any(re.search(pattern, cleaned_query) for pattern in self.sql_triggers):
            logger.info("Query routed to: [SQL Engine] (Quantitative aggregation matched)")
            return "SQL"
            
        # Step 3: Prevent false positives on product specs (like "500w", "120Hz")
        # Only trigger SQL if they explicitly ask for an ID number
        if re.search(r'\bid\s*\d{3,}\b', cleaned_query):
            logger.info("Query routed to: [SQL Engine] (Explicit ID lookup)")
            return "SQL"
            
        # Default Fallback: Natural language questions about products are usually semantic
        logger.info("Query routed to: [Vector Engine] (Default fallback)")
        return "VECTOR"