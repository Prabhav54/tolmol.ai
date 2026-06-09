from sqlalchemy import text
from db.session import db
from core.config import settings
from core.logger import get_logger
import random
from datetime import datetime, timedelta
import pandas as pd
import google.generativeai as genai
import os

logger = get_logger(__name__)

class VectorEngine:
    def __init__(self):
        logger.info("Initializing Lightweight Gemini Embedding Engine...")
        
        # Configure Gemini API using environment variable
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY environment variable is missing!")
        genai.configure(api_key=api_key)
        
        self.engine = db.engine

    def similarity_search(self, query: str, product_id: int = None, top_k: int = 3) -> list:
        """
        Generates vector embeddings via Gemini API and matches them with stored chunks using Cosine Distance (<=>).
        """
        # 1. Generate embedding via Gemini API
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=query,
            task_type="retrieval_query",
            output_dimensionality=384  # Magic parameter to match your existing PostgreSQL schema!
        )
        raw_embeddings = response['embedding']
        
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

    def ingest_product(self, product_id: int, source_url: str, chunks: list[str]) -> int:
        """
        Encodes list of raw text chunks via Gemini API and inserts them into PostgreSQL via pgvector.
        """
        if not chunks:
            logger.warning(f"No chunks provided for product ingestion (ID: {product_id}).")
            return 0

        logger.info(f"Encoding {len(chunks)} text chunks for Product ID: {product_id} via Gemini...")
        
        # 1. Batch encode all text chunks simultaneously via API
        response = genai.embed_content(
            model="models/text-embedding-004",
            content=chunks,
            task_type="retrieval_document",
            output_dimensionality=384  # Keeps compatibility with your existing database
        )
        embeddings = response['embedding']
        
        # 2. Build bulk insertion parameters
        insert_query = """
            INSERT INTO product_reviews (product_id, chunk_text, embedding)
            VALUES (:product_id, :chunk_text, CAST(:embedding AS vector));
        """
        
        inserted_count = 0
        
        # 3. Secure connection to execute bulk transaction blocks safely
        with self.engine.begin() as conn:
            for text_chunk, vector in zip(chunks, embeddings):
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

    def get_simulated_price_trend(self, product_id: int, base_price: int = 2500) -> list:
        """
        Generates a simulated 30-day price trend for the UI dashboard.
        """
        trend_data = []
        current_date = datetime.now()
        
        current_price = base_price
        for i in range(30):
            date_string = (current_date - timedelta(days=30-i)).strftime("%Y-%m-%d")
            
            change_percent = random.uniform(-0.05, 0.05)
            current_price = int(current_price * (1 + change_percent))
            
            trend_data.append({
                "date": date_string,
                "price": current_price
            })
            
        return trend_data