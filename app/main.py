import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import init_db, engine
from app.routers import csv_upload, accounts, categories, analytics, ml_predict, budgets

# Configure structured logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("expense_analyzer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Initializing database schema...")
    init_db()
    yield
    logger.info("Shutting down application...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CSV Upload API with expense tracking",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Global exception handler to avoid leaking tracebacks in non-debug mode."""
    logger.error(f"Unhandled error handling request to {request.url.path}: {exc}", exc_info=True)
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "type": type(exc).__name__},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# Include API routers
app.include_router(csv_upload.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(analytics.router)
app.include_router(ml_predict.router)
app.include_router(budgets.router)

# Mount static files — both index.html and analytics.html live in app/static/
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend SPA."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found. Access API docs at /docs"}


@app.get("/analytics", include_in_schema=False)
async def serve_analytics():
    """Serve the analytics page."""
    analytics_path = static_dir / "analytics.html"
    if analytics_path.exists():
        return FileResponse(str(analytics_path))
    return {"message": "Analytics page not found."}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint with database probe."""
    db_status = "healthy"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    status_code = status.HTTP_200_OK if db_status == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if db_status == "healthy" else "degraded",
            "database": db_status,
            "version": settings.APP_VERSION,
        },
    )

