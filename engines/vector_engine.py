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
        raw_embeddings = self.embedder.encode(query).tolist()
        embedding_vector_str = f"[{','.join(map(str, raw_embeddings))}]"
        
        query_text = """
            SELECT product_id, chunk_text, 1 - (embedding <=> :query_embed) AS similarity
            FROM product_reviews
            WHERE 1=1
        """
        
        params = {"query_embed": embedding_vector_str, "top_k": top_k}
        
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

    # 🚀 --- ADD THIS NEW METHOD ---
    def ingest_product(self, product_id: int, source_url: str, chunks: list[str]) -> int:
        """
        Encodes list of raw text chunks into dense vectors and inserts them into PostgreSQL via pgvector.
        """
        if not chunks:
            logger.warning(f"No chunks provided for product ingestion (ID: {product_id}).")
            return 0

        logger.info(f"Encoding {len(chunks)} text chunks for Product ID: {product_id}...")
        
        # 1. Batch encode all text chunks simultaneously to optimize performance
        embeddings = self.embedder.encode(chunks).tolist()
        
        # 2. Build bulk insertion parameters with an explicit type cast to vector
        insert_query = """
            INSERT INTO product_reviews (product_id, chunk_text, embedding)
            VALUES (:product_id, :chunk_text, CAST(:embedding AS vector));
        """
        
        inserted_count = 0
        
        # 3. Secure connection to execute bulk transaction blocks safely
        with self.engine.begin() as conn:
            for text_chunk, vector in zip(chunks, embeddings):
                # Format python list into a string literal array string '[x, y, z...]'
                vector_str = f"[{','.join(map(str, vector))}]"
                
                conn.execute(
                    text(insert_query),
                    {
                        "product_id": product_id,
                        "chunk_text": text_chunk,
                        "embedding": vector_str
                    }
                )
                inserted_count += 1
                
        logger.info(f"Successfully vectorized and stored {inserted_count} chunks in database.")
        return inserted_count