from fastapi import APIRouter, HTTPException
from api.schemas import IngestRequest, IngestResponse
from scraper.parser import LinkParser
from scraper.text_processor import TextProcessor
from engines.vector_engine import VectorEngine
from db.session import db
from sqlalchemy import text
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingestion"])

# Initialize required components
parser = LinkParser()
processor = TextProcessor()
vector_layer = VectorEngine()

@router.post("", response_model=IngestResponse)
async def ingest_product_link(payload: IngestRequest):
    try:
        # 1. Scrape the live link
        scraped_data = parser.fetch_product_data(payload.url)
        
        # 2. Segment text into overlapping chunks
        chunks = processor.chunk_text(scraped_data["raw_content"])
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No extractable text content found at the provided URL.")
            
        # 3. Clean out old entries for this specific product ID to avoid duplications
        with db.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM product_reviews WHERE product_id = :prod_id;"),
                {"prod_id": payload.product_id}
            )
            
            # 4. Generate embeddings locally and save directly to Postgres
            for chunk in chunks:
                raw_embeds = vector_layer.embedder.encode(chunk).tolist()
                embedding_str = f"[{','.join(map(str, raw_embeds))}]"
                
                conn.execute(
                    text("""
                        INSERT INTO product_reviews (product_id, source_url, chunk_text, embedding)
                        VALUES (:prod_id, :url, :txt, :embed);
                    """),
                    {
                        "prod_id": payload.product_id,
                        "url": str(payload.url),
                        "txt": chunk,
                        "embed": embedding_str
                    }
                )
                
        logger.info(f"Successfully processed and stored product context for ID {payload.product_id}")
        return IngestResponse(
            status="Success",
            message="Product context fully analyzed and stored.",
            chunks_inserted=len(chunks),
            product_title=scraped_data["title"]
        )
        
    except Exception as e:
        logger.error(f"Ingestion route failed processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))