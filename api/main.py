import sys
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import ingest, query  # Adjust imports based on your exact file names

# --- CRITICAL WINDOWS ASYNCIO PATCH ---
# This forces Windows to use ProactorEventLoop, which supports Playwright subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
# --------------------------------------

app = FastAPI(
    title="Hybrid RAG E-Commerce Intelligence API",
    version="1.0.0"
)

# Enable CORS so your Streamlit frontend can communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include your application routes
app.include_router(ingest.router)
# app.include_router(query.router) # Uncomment when your query engine route is ready

@app.get("/")
def read_root():
    return {"status": "Online", "engine": "Hybrid RAG E-Commerce Intelligence"}