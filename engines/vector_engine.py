from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from db.session import db
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

class VectorEngine:
    def __init__(self):
        logger.info("Loading Local Sentence-Transformers Embedding Layer...")
        self.embedder = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
        self.engine = db.engine

    def similarity_search(self, query: str, product_id: int = None, top_k: int = 3) -> list:
        """
        Generates vector embeddings locally and matches them with stored chunks using Cosine Distance (<=>).
        """
        # Convert text into numerical vector array
        raw_embeddings = self.embedder.encode(query).tolist()
        embedding_vector_str = f"[{','.join(map(str, raw_embeddings))}]"
        
        # Base SQL setup utilizing pgvector operator
        query_text = """
            SELECT product_id, chunk_text, 1 - (embedding <=> :query_embed) AS similarity
            FROM product_reviews
            WHERE 1=1
        """
        
        params = {"query_embed": embedding_vector_str, "top_k": top_k}
        
        # Scrape-specific scope constraint optimization if product_id is passed
        if product_id is not None:
            query_text += " AND product_id = :product_id"
            params["product_id"] = product_id
            
        query_text += " ORDER BY embedding <=> :query_embed LIMIT :top_k;"
        
        results = []
        with self.engine.connect() as conn:
            rows = conn.execute(text(query_text), params).fetchall()
            for row in rows:
                results.append({
                    "product_id": row.product_id,
                    "text": row.chunk_text,
                    "score": round(row.similarity, 4)
                })
                
        logger.info(f"Vector similarity search completed. Retrieved {len(results)} chunks.")
        return results