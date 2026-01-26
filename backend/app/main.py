"""Barbossa API - Main application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import shutil
from app.api import api_router, ws_router
from app.api.health import router as health_router
from app import __version__
from app.logging_config import setup_logging

# Initialize logging
setup_logging()


def ensure_beets_config():
    """Ensure beets config is present in /config."""
    config_dir = Path("/config")
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "beets.yaml"
    source = Path(__file__).resolve().parents[1] / "config" / "beets.yaml"
    if not target.exists() and source.exists():
        shutil.copy2(source, target)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    ensure_beets_config()
    yield
    # Shutdown (nothing needed)


app = FastAPI(
    title="Barbossa",
    description="Family music library manager - Download, organize, curate",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
# In production, set CORS_ORIGINS env var to your domain(s)
import os
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")

# Include health routes (not under /api prefix)
app.include_router(health_router)

# Include WebSocket routes (not under /api prefix)
app.include_router(ws_router)


@app.get("/")
def root():
    """Root endpoint - API info."""
    return {
        "name": "Barbossa",
        "version": __version__,
        "docs": "/docs",
    }
