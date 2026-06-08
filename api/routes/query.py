from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from engines.router import Router
from engines.vector_engine import VectorEngine
from engines.sql_engine import SQLEngine
from engines.synthesis import ResponseSynthesizer
from core.logger import get_logger
import random

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
# NEW ENDPOINT: Fetch 30-Day Simulated Price Trend
# ---------------------------------------------------------
@router.get("/compare/{product_id}")
async def compare_platform_prices(product_id: int, current_title: str = "Product"):
    try:
        clean_title = current_title.replace("Title:", "").strip().lower()
        
        # 1. Base Price Detection (Mocked for safety, would be pulled from vector DB in production)
        base = 2500
        if "macbook" in clean_title or "laptop" in clean_title: base = 75000
        elif "asus" in clean_title or "display" in clean_title: base = 22000
        elif "nike" in clean_title or "shoe" in clean_title: base = 4500
        elif "shirt" in clean_title or "wear" in clean_title: base = 1200
        elif "serum" in clean_title or "cream" in clean_title: base = 800

        # 2. Dynamic Category Classification & Platform Selection
        platforms = []
        if any(word in clean_title for word in ["shoe", "shirt", "wear", "sneaker", "apparel", "nike"]):
            category = "Fashion & Apparel"
            platforms = ["Myntra", "Ajio", "Tata Cliq", "Amazon.in", "Flipkart"]
        elif any(word in clean_title for word in ["serum", "cream", "beauty", "makeup", "lotion"]):
            category = "Beauty & Personal Care"
            platforms = ["Nykaa", "Purplle", "Amazon.in", "Flipkart"]
        else:
            category = "Electronics & General"
            platforms = ["Amazon.in", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales"]

        # 3. Generate Simulated Pricing Matrix based on Category
        comparison_matrix = []
        for index, platform in enumerate(platforms):
            # Simulate realistic market fluctuations (between -5% and +8% of base price)
            variance = random.uniform(-0.05, 0.08)
            price = int(base * (1 + variance))
            
            # Simulate delivery times based on typical Indian logistics
            delivery = random.choice(["Same Day", "Tomorrow", "2 Days", "3-5 Days"])
            if index == 0:  # Force the first platform to be slightly cheaper for demonstration
                price = int(base * 0.95)
                delivery = "Tomorrow"

            comparison_matrix.append({
                "Platform": platform,
                "Price": price,
                "Delivery": delivery,
                "Category": category
            })
        
        # 4. Sort by absolute lowest price
        sorted_matrix = sorted(comparison_matrix, key=lambda x: x["Price"])
        
        return {
            "product_id": product_id,
            "target_item": clean_title,
            "category": category,
            "comparisons": sorted_matrix
        }
    except Exception as e:
        logger.error(f"Cross-platform aggregation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to compile comparison matrix.")