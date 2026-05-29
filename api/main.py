from fastapi import FastAPI
from api.routes import ingest, query
from db.session import db

app = FastAPI(
    title="Hybrid E-Commerce Intelligence Platform",
    description="Real-Time URL Scraping, Layered pgvector Storage, and Routing RAG Server",
    version="1.0.0"
)

# Attach routes
app.include_router(ingest.router)
app.include_router(query.router)

@app.get("/")
def systems_check():
    return {
        "status": "Green",
        "database_connected": db.engine is not None,
        "message": "Hybrid RAG Backbone Engine Fully Operational"
    }