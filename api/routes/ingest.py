import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from scraper.parser import LinkParser
from engines.vector_engine import VectorEngine
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

class IngestionPayload(BaseModel):
    url: str
    product_id: int

# Note: Removed 'async' to let FastAPI handle it securely in a standard thread
@router.post("/ingest")
def ingest_product(payload: IngestionPayload):
    logger.info(f"Starting cloud ingestion for Product ID: {payload.product_id}")
    
    try:
        parser = LinkParser()
        parsed_data = parser.parse(payload.url)
        
        if not parsed_data or not parsed_data.get("chunks"):
            raise HTTPException(status_code=400, detail="No readable text could be extracted.")
            
        vector_engine = VectorEngine()
        chunks_inserted = vector_engine.ingest_product(
            product_id=payload.product_id,
            source_url=payload.url,
            chunks=parsed_data["chunks"]
        )
        
        return {
            "status": "Success",
            "message": "Product context fully analyzed and stored.",
            "chunks_inserted": chunks_inserted,
            "product_title": parsed_data.get("title", "Unknown Product")
        }
        
    except Exception as e:
        error_stack = traceback.format_exc()
        logger.error(f"Ingestion pipeline crashed!\n{error_stack}")
        raise HTTPException(
            status_code=500, 
            detail=f"Pipeline Crash Details:\n{str(e)}"
        )