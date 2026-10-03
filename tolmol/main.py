from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from tolmol.config import settings
from tolmol.db.session import get_engine, init_db
from tolmol.errors import (
    DatabaseUnavailable,
    NotFound,
    ProductNotIdentified,
    ProviderError,
    RateLimited,
    ScrapingError,
)
from tolmol.logger import get_logger
from tolmol.routes import operator, shopper
from tolmol.services.access import InvalidApiKey

logger = get_logger(__name__)

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_INIT_DB:
        try:
            init_db()
        except DatabaseUnavailable as exc:
            logger.error(str(exc))
    yield


app = FastAPI(
    title="tolmol.ai API",
    description=(
        "Paste a product link and compare its price across Indian stores, see price history, and chat with the "
        "product about its specs and reviews. Send an `X-API-Key` header for higher limits."
    ),
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])

ERROR_STATUS = {
    ProductNotIdentified: 422,
    ScrapingError: 422,
    NotFound: 404,
    RateLimited: 429,
    InvalidApiKey: 401,
    ProviderError: 502,
}


def _handler(status: int):
    async def handle(_: Request, exc: Exception):
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    return handle


for error, status in ERROR_STATUS.items():
    app.add_exception_handler(error, _handler(status))


@app.exception_handler(DatabaseUnavailable)
@app.exception_handler(SQLAlchemyError)
async def database_error(_: Request, exc: Exception):
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Price history and chat are temporarily unavailable (database unreachable)."},
    )


app.include_router(shopper.router)
app.include_router(operator.router)


@app.get("/api/health", tags=["System"])
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
        "search": "configured" if settings.GOOGLE_API_KEY else "missing GOOGLE_API_KEY",
        "alerts_email": bool(settings.RESEND_API_KEY),
    }


# Local development serves the web UI too; on Vercel the CDN serves /public directly.
if PUBLIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="web")
