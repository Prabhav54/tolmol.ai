from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional

class IngestRequest(BaseModel):
    url: str
    product_id: int

class IngestResponse(BaseModel):
    status: str
    message: str
    chunks_inserted: int
    product_title: str

class QueryRequest(BaseModel):
    prompt: str
    product_id: Optional[int] = None

class QueryResponse(BaseModel):
    engine: str
    intent: str
    query_executed: str
    response: str
    metadata: Optional[List[Dict[str, Any]]] = None