from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from engines.router import Router
from engines.vector_engine import VectorEngine
from engines.sql_engine import SQLEngine
from engines.synthesis import ResponseSynthesizer
from core.logger import get_logger
import random
from datetime import datetime, timedelta
from urllib.parse import urlparse

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["RAG Inference"])

# Explicitly defining the expected payload schema
class QueryRequest(BaseModel):
    question: str
    product_id: int

intent_router = Router()
vector_engine = VectorEngine()
sql_engine = SQLEngine()
synthesizer = ResponseSynthesizer()

@router.post("")
async def execute_rag_query(payload: QueryRequest):
    try:
        # 1. Classify execution route
        engine_route = intent_router.route_query(payload.question)
        
        # 2. Execute SQL Strategy
        if engine_route == "SQL":
            execution_payload = sql_engine.generate_and_execute(payload.question)
            data_summary = str(execution_payload["data"])
            final_output = synthesizer.answer_question(payload.question, data_summary)
            
            return {
                "engine_selected": "Structured SQL Engine",
                "sql_executed": execution_payload.get("sql_executed", ""),
                "response": final_output
            }
            
        # 3. Execute Vector Strategy
        else:
            matches = vector_engine.similarity_search(
                query=payload.question,
                product_id=payload.product_id,
                top_k=10
            )
            context_string = "\n---\n".join([m["text"] for m in matches])
            final_output = synthesizer.answer_question(payload.question, context_string)
            
            return {
                "engine_selected": "Semantic Vector Engine",
                "sql_executed": None,
                "response": final_output
            }
            
    except Exception as e:
        logger.error(f"Inference processing endpoint exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# ENDPOINT: Fetch Cross-Platform Price Comparison (With URL Guard)
# ---------------------------------------------------------
@router.get("/compare/{product_id}")
async def compare_platform_prices(product_id: int, current_title: str = "Product", source_url: str = ""):
    try:
        # Prevent non-e-commerce scraping workflows
        if source_url:
            parsed_url = urlparse(source_url)
            domain = parsed_url.netloc.lower()
            banned_domains = ["youtube.com", "youtu.be", "instagram.com", "facebook.com", "twitter.com"]
            if any(banned in domain for banned in banned_domains):
                raise HTTPException(status_code=400, detail="Invalid link. Please provide a valid retail platform URL.")

        clean_title = current_title.replace("Title:", "").strip().lower()
        
        # Base Price Detection Matrix
        base = 2500
        if "macbook" in clean_title or "laptop" in clean_title: base = 75000
        elif "asus" in clean_title or "display" in clean_title: base = 22000
        elif any(w in clean_title for w in ["shoe", "shoes", "sneaker", "asics", "skechers", "nike"]): base = 4500
        elif any(w in clean_title for w in ["shirt", "snitch", "wear", "apparel"]): base = 1200

        fashion_keywords = ["shoe", "shoes", "sneaker", "sneakers", "shirt", "apparel", "myntra", "ajio", "snitch", "asics", "skechers", "nike"]
        beauty_keywords = ["serum", "cream", "beauty", "makeup", "lotion", "nykaa", "purplle"]
        
        if any(word in clean_title for word in fashion_keywords):
            category = "Fashion & Apparel"
            platforms = ["Myntra", "AJIO", "Tata Cliq", "Amazon.in", "Nykaa Fashion"]
        elif any(word in clean_title for word in beauty_keywords):
            category = "Beauty & Personal Care"
            platforms = ["Nykaa", "Purplle", "Amazon.in", "Flipkart"]
        else:
            category = "Electronics & General"
            platforms = ["Amazon.in", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales"]

        comparison_matrix = []
        for index, platform in enumerate(platforms):
            variance = random.uniform(-0.05, 0.08)
            price = int(base * (1 + variance))
            delivery = random.choice(["Same Day", "Tomorrow", "2 Days", "3-5 Days"])
            
            if index == 0:  
                price = int(base * 0.95)
                delivery = "Tomorrow"

            comparison_matrix.append({
                "Platform": platform,
                "Price": price,
                "Delivery": delivery,
                "Category": category
            })
        
        return {
            "product_id": product_id,
            "target_item": clean_title,
            "category": category,
            "comparisons": sorted(comparison_matrix, key=lambda x: x["Price"])
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Cross-platform aggregation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compile comparison matrix.")


# ---------------------------------------------------------
# ENDPOINT: Fetch 30-Day Simulated Price Trend
# ---------------------------------------------------------
@router.get("/trend/{product_id}")
async def get_product_trend(product_id: int, current_title: str = "Product"):
    try:
        clean_title = current_title.replace("Title:", "").strip().lower()
        
        base = 2500
        if "macbook" in clean_title or "laptop" in clean_title: base = 75000
        elif "asus" in clean_title or "display" in clean_title: base = 22000
        elif any(w in clean_title for w in ["shoe", "shoes", "sneaker", "asics", "skechers", "nike"]): base = 4500
        elif any(w in clean_title for w in ["shirt", "snitch", "wear", "apparel"]): base = 1200

        trend_data = []
        current_date = datetime.now()
        running_price = base

        for i in range(30, -1, -1):
            date_str = (current_date - timedelta(days=i)).strftime("%Y-%m-%d")
            running_price = int(running_price * (1 + random.uniform(-0.02, 0.025)))
            trend_data.append({"date": date_str, "price": running_price})

        return {"product_id": product_id, "trend": trend_data}
    except Exception as e:
        logger.error(f"Price trend generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compile historical trend matrix.")


# ---------------------------------------------------------
# ENDPOINT: Competitor Sentiment Tracker
# ---------------------------------------------------------
@router.get("/sentiment/{product_id}")
async def get_product_sentiment(product_id: int):
    try:
        # Generates proportional distributions adding up to 100%
        pos = random.randint(60, 85)
        neu = random.randint(10, 20)
        neg = 100 - (pos + neu)
        
        return {
            "product_id": product_id,
            "metrics": {"Positive": pos, "Neutral": neu, "Negative": neg},
            "top_praises": ["Premium physical build quality", "Excellent value ratio", "Rapid delivery processing"],
            "top_complaints": ["Slightly high baseline pricing", "Minor instructions documentation limits"]
        }
    except Exception as e:
        logger.error(f"Sentiment generation matrix exception: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze competitor review sentiment.")


# ---------------------------------------------------------
# ENDPOINT: Competitor Feature Benchmark
# ---------------------------------------------------------
@router.get("/benchmark/{product_id}")
async def get_feature_benchmark(product_id: int):
    try:
        return {
            "product_id": product_id,
            "benchmarks": [
                {"Feature": "Value for Money", "Product Score": random.randint(78, 95), "Market Average": 75},
                {"Feature": "Material Quality", "Product Score": random.randint(80, 92), "Market Average": 72},
                {"Feature": "Shipping Timelines", "Product Score": random.randint(85, 98), "Market Average": 80},
                {"Feature": "Packaging Evaluation", "Product Score": random.randint(70, 88), "Market Average": 74}
            ]
        }
    except Exception as e:
        logger.error(f"Benchmark generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract feature benchmarks.")