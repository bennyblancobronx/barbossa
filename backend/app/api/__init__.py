"""API routes."""
from fastapi import APIRouter
from app.api import (
    auth, library, streaming, downloads, websocket,
    admin, review, torrentleech, exports, lidarr,
    artwork, metadata, settings, search
)

api_router = APIRouter()

# Auth
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Library
api_router.include_router(library.router, tags=["library"])
api_router.include_router(streaming.router, tags=["streaming"])
api_router.include_router(artwork.router, tags=["artwork"])
api_router.include_router(metadata.router, tags=["metadata"])

# Downloads
api_router.include_router(downloads.router, tags=["downloads"])

# Admin
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(review.router, tags=["review"])
api_router.include_router(settings.router, tags=["settings"])

# Integrations
api_router.include_router(torrentleech.router, tags=["torrentleech"])
api_router.include_router(lidarr.router, tags=["lidarr"])

# Exports
api_router.include_router(exports.router, tags=["exports"])

# Search
api_router.include_router(search.router, tags=["search"])

# WebSocket routes (not under /api prefix)
ws_router = websocket.router
