from fastapi import APIRouter, HTTPException
from api.schemas import QueryRequest, QueryResponse
from engines.router import Router
from engines.vector_engine import VectorEngine
from engines.sql_engine import SQLEngine
from engines.synthesis import ResponseSynthesizer
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/query", tags=["RAG Inference"])

# Core execution engines
intent_router = Router()
vector_engine = VectorEngine()
sql_engine = SQLEngine()
synthesizer = ResponseSynthesizer()

@router.post("", response_model=QueryResponse)
async def execute_rag_query(payload: QueryRequest):
    try:
        # 1. Classify execution route
        engine_route = intent_router.route_query(payload.prompt)
        
        # 2. Execute SQL Strategy
        if engine_route == "SQL":
            execution_payload = sql_engine.generate_and_execute(payload.prompt)
            data_summary = str(execution_payload["data"])
            
            # Synthesize numbers/records cleanly
            final_output = synthesizer.answer_question(payload.prompt, data_summary)
            
            return QueryResponse(
                engine="Structured SQL Engine",
                intent="Analytical Search",
                query_executed=execution_payload["sql_executed"],
                response=final_output,
                metadata=execution_payload["data"]
            )
            
        # 3. Execute Vector Strategy
        else:
            matches = vector_engine.similarity_search(
                query=payload.prompt,
                product_id=payload.product_id
            )
            
            context_string = "\n---\n".join([m["text"] for m in matches])
            final_output = synthesizer.answer_question(payload.prompt, context_string)
            
            return QueryResponse(
                engine="Semantic Vector Engine",
                intent="Contextual Matching",
                query_executed="Cosine Distance Operator (<=>)",
                response=final_output,
                metadata=matches
            )
            
    except Exception as e:
        logger.error(f"Inference processing endpoint exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))