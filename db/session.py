from sqlalchemy import create_engine, text
from core.config import settings
from core.logger import get_logger
from core.exceptions import DatabaseConnectionError

logger = get_logger(__name__)

class DatabaseSession:
    def __init__(self):
        try:
            self.engine = create_engine(settings.DATABASE_URL)
            self._init_db()
            logger.info("Successfully connected to PostgreSQL database.")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise DatabaseConnectionError("Ensure Docker is running and port 5433 is available.")

    def _init_db(self):
        """Ensures the vector extension and schema exist upon startup."""
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            
        
            # Using 384 dimensions to match our local Hugging Face embedder
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS product_reviews (
                    id SERIAL PRIMARY KEY,
                    product_id INT,
                    source_url TEXT,
                    chunk_text TEXT,
                    embedding vector(384) 
                );
            """))

    def get_connection(self):
        return self.engine.connect()

# Global instance to be imported by the engines
db = DatabaseSession()