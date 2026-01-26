"""Unified search API endpoint."""
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
import logging

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.library import LibraryService
from app.services.download import DownloadService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


# Response Schemas
class LocalResults(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    count: int
    albums: List[Any] = []
    artists: List[Any] = []
    tracks: List[Any] = []


class ExternalResults(BaseModel):
    source: str
    count: int
    items: List[Any] = []
    error: Optional[str] = None


class UnifiedSearchResponse(BaseModel):
    query: str
    type: str
    local: LocalResults
    external: Optional[ExternalResults] = None


@router.get("/unified", response_model=UnifiedSearchResponse)
async def unified_search(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str = Query(
        "album",
        pattern="^(artist|album|track)$",
        description="Search type - NO playlist allowed per contracts.md"
    ),
    include_external: bool = Query(
        False,
        description="Also search Qobuz if local results empty"
    ),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Unified search endpoint.

    1. Always searches local library first
    2. If include_external=True AND local results empty, searches Qobuz
    3. Returns both result sets with source indicators

    Note: Playlist type excluded per contracts.md line 94
    """
    library_service = LibraryService(db)

    # Local search
    try:
        local_results = library_service.search(q, type, limit)
    except Exception as e:
        logger.error(f"Local search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

    # Build response - convert ORM objects to dicts
    albums = [
        {
            "id": a.id,
            "title": a.title,
            "year": a.year,
            "artwork_path": a.artwork_path,
            "artist_id": a.artist_id,
            "artist_name": a.artist.name if a.artist else None,
            "source": getattr(a, 'source', None),
            "status": a.status
        }
        for a in local_results.get("albums", [])
    ]
    artists = [
        {
            "id": a.id,
            "name": a.name,
            "sort_name": a.sort_name,
            "album_count": len(a.albums) if hasattr(a, 'albums') else 0
        }
        for a in local_results.get("artists", [])
    ]
    tracks = [
        {
            "id": t.id,
            "title": t.title,
            "track_number": t.track_number,
            "duration": t.duration,
            "album_id": t.album_id,
            "album_title": t.album.title if t.album else None,
            "artist_name": t.album.artist.name if t.album and t.album.artist else None,
            "source": t.source,
            "quality": f"{t.bit_depth}/{t.sample_rate}" if t.bit_depth and t.sample_rate else None
        }
        for t in local_results.get("tracks", [])
    ]

    response = UnifiedSearchResponse(
        query=q,
        type=type,
        local=LocalResults(
            count=len(albums) + len(artists) + len(tracks),
            albums=albums,
            artists=artists,
            tracks=tracks
        ),
        external=None
    )

    # External search (on demand, only if local empty)
    if include_external and response.local.count == 0:
        download_service = DownloadService(db)
        try:
            qobuz_results = await download_service.search_qobuz(q, type, limit)
            response.external = ExternalResults(
                source="qobuz",
                count=len(qobuz_results) if qobuz_results else 0,
                items=qobuz_results or []
            )
        except Exception as e:
            logger.warning(f"Qobuz search failed: {e}")
            response.external = ExternalResults(
                source="qobuz",
                count=0,
                items=[],
                error=str(e)
            )

    return response
