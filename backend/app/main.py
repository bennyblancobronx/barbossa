"""Barbossa API - Main application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router, ws_router
from app.api.health import router as health_router
from app import __version__
from app.logging_config import setup_logging

# Initialize logging
setup_logging()

app = FastAPI(
    title="Barbossa",
    description="Family music library manager - Download, organize, curate",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
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
