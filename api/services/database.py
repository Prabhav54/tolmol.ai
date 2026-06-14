import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from core.config import settings

class DatabaseService:
    def __init__(self):
        self.connection_string = settings.DATABASE_URL

    @contextmanager
    def get_cursor(self):
        """Context manager to ensure connections and cursors are safely closed."""
        conn = None
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            yield cursor
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def fetch_product_context(self, product_id: int):
        """Example method to query vector chunks for a product."""
        query = """
            SELECT content, metadata 
            FROM product_embeddings 
            WHERE product_id = %s;
        """
        with self.get_cursor() as cur:
            cur.execute(query, (product_id,))
            return cur.fetchall()

# Initialize a single global instance
db_service = DatabaseService()