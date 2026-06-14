import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from db.session import db
from engines.vector_engine import vector_db
from engines.sql_engine import SQLEngine
from core.logger import get_logger
import google.generativeai as genai
import random

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["Query"])

class QueryPayload(BaseModel):
    question: str
    product_id: int

# ---------------------------------------------------------
# ENDPOINT: Hybrid RAG Intent Router (Chat Interface)
# ---------------------------------------------------------
@router.post("")
def handle_user_query(payload: QueryPayload):
    logger.info(f"Incoming query routing evaluation for Product ID: {payload.product_id}")
    question_lower = payload.question.lower()
    sql_engine = SQLEngine()
    
    try:
        # 1. INTENT ROUTING
        # Check if the user is asking quantitative (SQL) or qualitative (Vector) questions
        sql_keywords = ["cheap", "price", "lowest", "cost", "trend", "chart", "history", "compare", "platform"]
        is_sql_intent = any(keyword in question_lower for keyword in sql_keywords)
        
        if is_sql_intent:
            logger.info("Routing query to Structured SQL Analytics Engine...")
            analytics_result = sql_engine.generate_and_execute(payload.question, payload.product_id)
            
            # Use Gemini to synthesize the raw SQL output into a human-friendly answer
            model = genai.GenerativeModel("gemini-1.5-flash")
            summary_prompt = f"""
            Summarize these retail pricing results nicely for a consumer. 
            User question: {payload.question}
            Data Rows from Database: {analytics_result['data']}
            """
            ai_response = model.generate_content(summary_prompt).text
            
            return {
                "engine_selected": "SQL Analytics Engine",
                "response": ai_response
            }
            
        else:
            logger.info("Routing query to Unstructured Semantic Vector Engine...")
            # Retrieve vectors strictly mapped to this specific product ID
            retrieved_chunks = vector_db.vector_store.similarity_search(
                query=payload.question,
                k=4,
                filter={"product_id": payload.product_id}
            )
            
            context_text = "\n".join([doc.page_content for doc in retrieved_chunks])
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            rag_prompt = f"""
            Answer the consumer's question using ONLY the verified product review excerpts provided.
            If the answer isn't in the context, explicitly state that you don't have enough data.
            
            Question: {payload.question}
            Context:
            {context_text}
            """
            ai_response = model.generate_content(rag_prompt).text
            
            return {
                "engine_selected": "Semantic Vector Engine",
                "response": ai_response
            }
            
    except Exception as e:
        logger.error(f"Query routing failure: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# ENDPOINT: Database-Driven Price Comparison
# ---------------------------------------------------------
@router.get("/compare/{product_id}")
def compare_platform_prices(product_id: int):
    try:
        query = """
            SELECT platform as "Platform", current_price as "Price", delivery_timeline as "Delivery"
            FROM product_links 
            WHERE product_id = :pid 
            ORDER BY current_price ASC;
        """
        with db.engine.connect() as conn:
            rows = conn.execute(text(query), {"pid": product_id}).fetchall()
            data = [dict(row._mapping) for row in rows]
            
        return {
            "product_id": product_id,
            "category": "Cross-Platform Intelligence",
            "comparisons": data
        }
    except Exception as e:
        logger.error(f"Failed to query price comparisons: {e}")
        raise HTTPException(status_code=500, detail="Database failure.")

# ---------------------------------------------------------
# ENDPOINT: Database-Driven Price Trend
# ---------------------------------------------------------
@router.get("/trend/{product_id}")
def get_product_trend(product_id: int):
    try:
        query = """
            SELECT pl.platform, ph.price, ph.fetched_at::date as date
            FROM price_history ph
            JOIN product_links pl ON ph.link_id = pl.id
            WHERE pl.product_id = :pid
            ORDER BY ph.fetched_at ASC;
        """
        with db.engine.connect() as conn:
            rows = conn.execute(text(query), {"pid": product_id}).fetchall()
            data = [dict(row._mapping) for row in rows]
            
        return {"product_id": product_id, "trend": data}
    except Exception as e:
        logger.error(f"Failed to query price trends: {e}")
        raise HTTPException(status_code=500, detail="Database failure.")

# ---------------------------------------------------------
# ENDPOINT: Simulated Metrics (Holdovers for UI Integrity)
# ---------------------------------------------------------
@router.get("/sentiment/{product_id}")
def get_product_sentiment(product_id: int):
    pos = random.randint(60, 85)
    neu = random.randint(10, 20)
    return {
        "metrics": {"Positive": pos, "Neutral": neu, "Negative": 100 - (pos + neu)},
        "top_praises": ["Premium build quality", "Excellent value ratio"],
        "top_complaints": ["Slightly high baseline pricing"]
    }

@router.get("/benchmark/{product_id}")
def get_feature_benchmark(product_id: int):
    return {
        "benchmarks": [
            {"Feature": "Value for Money", "Product Score": random.randint(78, 95), "Market Average": 75},
            {"Feature": "Material Quality", "Product Score": random.randint(80, 92), "Market Average": 72}
        ]
    }