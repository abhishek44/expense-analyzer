"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db
from app.routers import csv_upload, accounts, categories, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CSV Upload API with expense tracking",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(csv_upload.router)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(analytics.router)

# Mount static files
app_static_path = Path(__file__).parent / "static"
static_path = Path(__file__).parent.parent / "static"
if app_static_path.exists():
    app.mount("/app-static", StaticFiles(directory=str(app_static_path)), name="app-static")
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the frontend SPA."""
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend not found. Access API docs at /docs"}


@app.get("/analytics", include_in_schema=False)
async def serve_analytics():
    """Serve the analytics page."""
    analytics_path = app_static_path / "analytics.html"
    if analytics_path.exists():
        return FileResponse(str(analytics_path))
    return {"message": "Analytics page not found."}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
