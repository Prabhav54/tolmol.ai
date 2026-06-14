import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from db.session import db
from scraper.parser import LinkParser
from engines.vector_engine import vector_db
from langchain_core.documents import Document
from core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingest"])

class IngestionPayload(BaseModel):
    url: str

@router.post("")
def ingest_product(payload: IngestionPayload):
    logger.info(f"Initializing relational ingestion routing sequence for: {payload.url}")
    
    try:
        # 1. Scrape and structure data from any platform automatically
        parser = LinkParser()
        parsed_data = parser.parse(payload.url)
        
        if not parsed_data or not parsed_data.get("title"):
            raise HTTPException(status_code=400, detail="Unable to safely parse or verify e-commerce metadata.")
            
        title = parsed_data["title"]
        price = parsed_data["price"]
        platform = parsed_data["platform"]
        chunks = parsed_data["chunks"]
        
        engine = db.engine
        product_id = None
        
        with engine.begin() as conn:
            # 2. Check if this product title already exists in the system
            existing_product = conn.execute(
                text("SELECT id FROM products WHERE LOWER(title) = LOWER(:title) LIMIT 1;"),
                {"title": title}
            ).fetchone()
            
            if existing_product:
                product_id = existing_product.id
                logger.info(f"Matching master product found. ID: {product_id}")
            else:
                # Create a new canonical tracking group if unique
                new_prod = conn.execute(
                    text("INSERT INTO products (title) VALUES (:title) RETURNING id;"),
                    {"title": title}
                ).fetchone()
                product_id = new_prod.id
                logger.info(f"Provisioned new canonical record entry. Generated ID: {product_id}")
            
            # 3. Add or update platform-specific link entries
            conn.execute(
                text("""
                    INSERT INTO product_links (product_id, platform, url, current_price)
                    VALUES (:product_id, :platform, :url, :price)
                    ON CONFLICT (url) DO UPDATE 
                    SET current_price = EXCLUDED.current_price, updated_at = CURRENT_TIMESTAMP;
                """),
                {"product_id": product_id, "platform": platform, "url": payload.url, "price": price}
            )
            
            # 4. Snapshot logging to history for your trend charts
            link_record = conn.execute(
                text("SELECT id FROM product_links WHERE url = :url;"), {"url": payload.url}
            ).fetchone()
            
            conn.execute(
                text("INSERT INTO price_history (link_id, price) VALUES (:link_id, :price);"),
                {"link_id": link_record.id, "price": price}
            )

        # 5. Vectorize raw chunks using LangChain and link back to master identity
        if chunks:
            documents = [
                Document(
                    page_content=chunk,
                    metadata={"product_id": product_id, "source_platform": platform}
                )
                for chunk in chunks
            ]
            vector_db.vector_store.add_documents(documents)
            
        return {
            "status": "Success",
            "product_id": product_id,
            "detected_platform": platform,
            "product_title": title,
            "current_price": price,
            "message": "Unified multi-platform data sync finalized successfully."
        }
        
    except Exception as e:
        logger.error(f"Ingestion pipeline crash encountered: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))