"""Lidarr API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.integrations.lidarr import LidarrClient, LidarrError


router = APIRouter(prefix="/lidarr", tags=["lidarr"])


class AddArtistRequest(BaseModel):
    """Add artist request."""
    mbid: str
    name: str
    search_for_missing: bool = True


@router.get("/status")
async def check_lidarr_status(
    user: User = Depends(get_current_user)
):
    """Check Lidarr connection status."""
    client = LidarrClient()
    connected = await client.test_connection()

    return {
        "connected": connected,
        "url": client.base_url if connected else None
    }


@router.get("/artists")
async def list_monitored_artists(
    user: User = Depends(get_current_user)
):
    """List monitored artists in Lidarr."""
    client = LidarrClient()

    try:
        artists = await client.get_artists()
        return {
            "count": len(artists),
            "artists": [
                {
                    "id": a.get("id"),
                    "name": a.get("artistName"),
                    "mbid": a.get("foreignArtistId"),
                    "monitored": a.get("monitored"),
                    "album_count": a.get("statistics", {}).get("albumCount", 0)
                }
                for a in artists
            ]
        }
    except LidarrError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_lidarr(
    q: str,
    user: User = Depends(get_current_user)
):
    """Search for artists via Lidarr."""
    client = LidarrClient()

    try:
        results = await client.search_artist(q)
        return {
            "query": q,
            "results": [
                {
                    "name": r.get("artistName"),
                    "mbid": r.get("foreignArtistId"),
                    "overview": r.get("overview", "")[:200],
                    "genres": r.get("genres", [])
                }
                for r in results[:20]
            ]
        }
    except LidarrError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/artists")
async def add_artist_to_lidarr(
    data: AddArtistRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Add artist to Lidarr for monitoring."""
    client = LidarrClient()

    try:
        result = await client.add_artist(
            mbid=data.mbid,
            name=data.name,
            search_for_missing=data.search_for_missing
        )

        return {
            "status": "added",
            "artist_id": result.get("id"),
            "name": result.get("artistName")
        }
    except LidarrError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue")
async def get_lidarr_queue(
    user: User = Depends(get_current_user)
):
    """Get Lidarr download queue."""
    client = LidarrClient()

    try:
        queue = await client.get_queue()
        return {
            "count": len(queue),
            "items": [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "artist": item.get("artist", {}).get("artistName"),
                    "status": item.get("status"),
                    "progress": item.get("sizeleft", 0) / max(item.get("size", 1), 1) * 100
                }
                for item in queue
            ]
        }
    except LidarrError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_lidarr_history(
    limit: int = 50,
    user: User = Depends(get_current_user)
):
    """Get Lidarr download history."""
    client = LidarrClient()

    try:
        history = await client.get_history(limit=limit)
        return {
            "count": len(history),
            "items": [
                {
                    "id": item.get("id"),
                    "album": item.get("album", {}).get("title"),
                    "artist": item.get("artist", {}).get("artistName"),
                    "event_type": item.get("eventType"),
                    "date": item.get("date")
                }
                for item in history
            ]
        }
    except LidarrError as e:
        raise HTTPException(status_code=500, detail=str(e))
