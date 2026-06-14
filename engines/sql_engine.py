from sqlalchemy import text
from db.session import db
from core.logger import get_logger

logger = get_logger(__name__)

class SQLEngine:
    def __init__(self):
        self.engine = db.engine

    def generate_and_execute(self, user_question: str, product_id: int) -> dict:
        """
        Interprets natural language queries related to structured comparisons,
        aggregating raw data matrices safely across competing platforms.
        """
        logger.info(f"Compiling relational analytics dataset metrics for Product ID: {product_id}")
        
        # Simple text parsing rules to decide analytics response formatting
        question_lower = user_question.lower()
        
        try:
            with self.engine.connect() as conn:
                if "cheap" in question_lower or "lowest" in question_lower or "compare" in question_lower:
                    query = """
                        SELECT platform, current_price, delivery_timeline 
                        FROM product_links 
                        WHERE product_id = :product_id 
                        ORDER BY current_price ASC;
                    """
                    rows = conn.execute(text(query), {"product_id": product_id}).fetchall()
                    data_payload = [dict(row._mapping) for row in rows]
                    
                    return {
                        "sql_executed": "SELECT platform, current_price FROM product_links WHERE product_id = ...",
                        "data": data_payload
                    }
                    
                elif "trend" in question_lower or "history" in question_lower or "price chart" in question_lower:
                    query = """
                        SELECT pl.platform, ph.price, ph.fetched_at::text 
                        FROM price_history ph
                        JOIN product_links pl ON ph.link_id = pl.id
                        WHERE pl.product_id = :product_id
                        ORDER BY ph.fetched_at ASC;
                    """
                    rows = conn.execute(text(query), {"product_id": product_id}).fetchall()
                    data_payload = [dict(row._mapping) for row in rows]
                    
                    return {
                        "sql_executed": "SELECT price, fetched_at FROM price_history JOIN product_links ...",
                        "data": data_payload
                    }
                
                # Default safety fallback query context map
                query = "SELECT platform, current_price FROM product_links WHERE product_id = :product_id"
                rows = conn.execute(text(query), {"product_id": product_id}).fetchall()
                return {"sql_executed": query, "data": [dict(row._mapping) for row in rows]}
                
        except Exception as e:
            logger.error(f"SQL engine telemetry processing exception: {e}")
            return {"sql_executed": "None", "data": []}