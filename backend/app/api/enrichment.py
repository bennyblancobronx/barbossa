"""Enrichment API endpoints.

Phase 8 of audit-014: REST API for metadata enrichment.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.album import Album
from app.models.track import Track
from app.services.enrichment import EnrichmentService
from app.tasks.enrichment import (
    enrich_album_lyrics_task,
    enrich_missing_lyrics_task,
    enrich_track_lyrics_task,
)


router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# Response models
class EnrichmentStatsResponse(BaseModel):
    """Enrichment statistics response."""
    total_tracks: int
    missing_lyrics: int
    missing_isrc: int
    missing_composer: int
    lyrics_coverage_pct: float


class EnrichmentJobResponse(BaseModel):
    """Background enrichment job response."""
    task_id: str
    message: str


class TrackEnrichmentResponse(BaseModel):
    """Single track enrichment response."""
    track_id: int
    success: bool
    message: Optional[str] = None


class BatchEnrichmentResponse(BaseModel):
    """Batch enrichment response."""
    total: int
    enriched: int
    failed: int
    skipped: int


# Request models
class EnrichAlbumRequest(BaseModel):
    """Request to enrich an album."""
    album_id: int
    background: bool = True


class EnrichBatchRequest(BaseModel):
    """Request for batch enrichment."""
    limit: int = 100
    album_id: Optional[int] = None
    artist_id: Optional[int] = None
    background: bool = True


@router.get("/stats", response_model=EnrichmentStatsResponse)
async def get_enrichment_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get statistics about missing metadata that can be enriched."""
    service = EnrichmentService(db)
    return service.get_enrichment_stats()


@router.post("/album/{album_id}", response_model=EnrichmentJobResponse)
async def enrich_album(
    album_id: int,
    background: bool = Query(True, description="Run in background"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Enrich all tracks in an album with lyrics.

    If background=True (default), runs as Celery task and returns task ID.
    If background=False, runs synchronously and returns results.
    """
    # Verify album exists
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    if background:
        task = enrich_album_lyrics_task.delay(album_id)
        return EnrichmentJobResponse(
            task_id=task.id,
            message=f"Enrichment started for album '{album.title}'"
        )
    else:
        # Synchronous execution
        service = EnrichmentService(db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            service.enrich_album_lyrics(album_id)
        )
        return EnrichmentJobResponse(
            task_id="sync",
            message=f"Enriched {result.enriched}/{result.total} tracks"
        )


@router.post("/track/{track_id}", response_model=TrackEnrichmentResponse)
async def enrich_track(
    track_id: int,
    background: bool = Query(False, description="Run in background"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Enrich a single track with lyrics.

    Default is synchronous (background=False) for single tracks.
    """
    # Verify track exists
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if background:
        task = enrich_track_lyrics_task.delay(track_id)
        return TrackEnrichmentResponse(
            track_id=track_id,
            success=True,
            message=f"Enrichment task started: {task.id}"
        )
    else:
        # Synchronous execution
        service = EnrichmentService(db)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            service.enrich_track_lyrics(track)
        )
        return TrackEnrichmentResponse(
            track_id=track_id,
            success=result.success,
            message=result.message
        )


@router.post("/batch", response_model=EnrichmentJobResponse)
async def enrich_batch(
    data: EnrichBatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Enrich multiple tracks missing lyrics.

    Filters:
    - album_id: Only enrich tracks from this album
    - artist_id: Only enrich tracks from this artist
    - limit: Maximum tracks to process (default 100)

    Always runs in background due to potential long duration.
    """
    task = enrich_missing_lyrics_task.delay(
        limit=data.limit,
        album_id=data.album_id,
        artist_id=data.artist_id
    )
    return EnrichmentJobResponse(
        task_id=task.id,
        message=f"Batch enrichment started (limit={data.limit})"
    )


@router.get("/tracks/missing-lyrics")
async def get_tracks_missing_lyrics(
    limit: int = Query(50, le=200, description="Maximum tracks to return"),
    album_id: Optional[int] = Query(None, description="Filter by album"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get list of tracks that are missing lyrics."""
    service = EnrichmentService(db)
    tracks = service.get_tracks_missing_lyrics(limit=limit, album_id=album_id)

    return [
        {
            "id": track.id,
            "title": track.title,
            "album_id": track.album_id,
            "album_title": track.album.title if track.album else None,
            "artist_name": track.album.artist.name if track.album and track.album.artist else None,
        }
        for track in tracks
    ]
