import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import both of your route files
from api.routes import ingest, query 

# --- CRITICAL WINDOWS ASYNCIO PATCH ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# --------------------------------------

app = FastAPI(
    title="Hybrid RAG E-Commerce Intelligence API",
    version="1.0.0"
)

# Enable CORS so Streamlit can communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTER YOUR ROUTES HERE ---
app.include_router(ingest.router)
app.include_router(query.router)  # <--- This is the line that fixes the 404 error!

@app.get("/")
def read_root():
    return {"status": "Online", "engine": "Hybrid RAG E-Commerce Intelligence"}