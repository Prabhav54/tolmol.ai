from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from api.routes import admin, benchmark, catalog, ingest, query
from core.config import settings
from core.exceptions import DatabaseConnectionError, EmbeddingError, LLMGenerationError, ScrapingError
from core.logger import get_logger
from db.session import get_engine, init_db

logger = get_logger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_INIT_DB:
        try:
            init_db()
        except DatabaseConnectionError as exc:
            # Keep serving so /health and the UI can report the problem instead of a dead process.
            logger.error(str(exc))
    yield


app = FastAPI(
    title="tolmol.ai — E-Commerce Intelligence API",
    description="Hybrid RAG search over a product catalog: pgvector semantic retrieval + SQL constraint filtering.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": message})


@app.exception_handler(ScrapingError)
async def scraping_error(_: Request, exc: ScrapingError):
    return _error(422, str(exc))


@app.exception_handler(EmbeddingError)
@app.exception_handler(LLMGenerationError)
async def provider_error(_: Request, exc: Exception):
    return _error(502, f"AI provider error: {exc}")


@app.exception_handler(DatabaseConnectionError)
@app.exception_handler(OperationalError)
async def database_error(_: Request, exc: Exception):
    logger.error(f"Database error: {exc}")
    return _error(503, "The catalog database is unreachable. Check DATABASE_URL and that Supabase is running.")


app.include_router(ingest.router)
app.include_router(query.router)
app.include_router(catalog.router)
app.include_router(benchmark.router)
app.include_router(admin.router)


@app.get("/health", tags=["System"])
def health():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        logger.error(f"Health check failed: {exc}")
        database = "unreachable"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL
        if settings.EMBEDDING_PROVIDER == "gemini"
        else settings.HF_EMBEDDING_MODEL,
    }


# The web UI is mounted last so every API route above takes precedence.
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
