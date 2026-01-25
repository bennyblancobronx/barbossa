"""Settings API endpoints."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.config import settings
from app.integrations.lidarr import LidarrClient
from app.integrations.plex import PlexClient
from app.integrations.bandcamp import BandcampClient


router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    """Settings response."""
    # Paths
    music_library: str
    music_users: str
    music_downloads: str
    music_import: str
    music_export: str

    # Qobuz
    qobuz_enabled: bool
    qobuz_quality: int

    # Lidarr
    lidarr_enabled: bool
    lidarr_url: str
    lidarr_connected: Optional[bool] = None

    # Plex
    plex_enabled: bool
    plex_url: str
    plex_auto_scan: bool
    plex_connected: Optional[bool] = None

    # TorrentLeech
    torrentleech_enabled: bool

    # Bandcamp
    bandcamp_enabled: bool


class SettingsUpdate(BaseModel):
    """Settings update request."""
    qobuz_quality: Optional[int] = None
    lidarr_url: Optional[str] = None
    lidarr_api_key: Optional[str] = None
    plex_url: Optional[str] = None
    plex_token: Optional[str] = None
    plex_auto_scan: Optional[bool] = None


@router.get("", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user)
):
    """Get application settings."""
    # Test connections for admin
    lidarr_connected = None
    plex_connected = None

    if user.is_admin:
        if settings.lidarr_url and settings.lidarr_api_key:
            try:
                lidarr = LidarrClient()
                lidarr_connected = await lidarr.test_connection()
            except Exception:
                lidarr_connected = False

        if settings.plex_url and settings.plex_token:
            try:
                plex = PlexClient()
                plex_connected = await plex.test_connection()
            except Exception:
                plex_connected = False

    return SettingsResponse(
        music_library=settings.music_library,
        music_users=settings.music_users,
        music_downloads=settings.music_downloads,
        music_import=settings.music_import,
        music_export=settings.music_export,
        qobuz_enabled=bool(settings.qobuz_email and settings.qobuz_password),
        qobuz_quality=settings.qobuz_quality,
        lidarr_enabled=bool(settings.lidarr_url and settings.lidarr_api_key),
        lidarr_url=settings.lidarr_url or "",
        lidarr_connected=lidarr_connected,
        plex_enabled=settings.plex_enabled,
        plex_url=settings.plex_url or "",
        plex_auto_scan=settings.plex_auto_scan,
        plex_connected=plex_connected,
        torrentleech_enabled=bool(settings.torrentleech_key),
        bandcamp_enabled=bool(settings.bandcamp_cookies)
    )


@router.put("")
async def update_settings(
    data: SettingsUpdate,
    admin: User = Depends(require_admin)
):
    """Update application settings.

    Note: This updates environment variables for the current process.
    For persistent changes, update .env file.
    """
    import os

    if data.qobuz_quality is not None:
        os.environ["QOBUZ_QUALITY"] = str(data.qobuz_quality)

    if data.lidarr_url is not None:
        os.environ["LIDARR_URL"] = data.lidarr_url

    if data.lidarr_api_key is not None:
        os.environ["LIDARR_API_KEY"] = data.lidarr_api_key

    if data.plex_url is not None:
        os.environ["PLEX_URL"] = data.plex_url

    if data.plex_token is not None:
        os.environ["PLEX_TOKEN"] = data.plex_token

    if data.plex_auto_scan is not None:
        os.environ["PLEX_AUTO_SCAN"] = str(data.plex_auto_scan).lower()

    # Clear settings cache to reload
    from app.config import get_settings
    get_settings.cache_clear()

    return {"status": "updated"}


@router.post("/test/lidarr")
async def test_lidarr_connection(
    url: str,
    api_key: str,
    admin: User = Depends(require_admin)
):
    """Test Lidarr connection with provided credentials."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{url.rstrip('/')}/api/v1/system/status",
                headers={"X-Api-Key": api_key},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "connected": True,
                    "version": data.get("version")
                }
            else:
                return {"connected": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/test/plex")
async def test_plex_connection(
    url: str,
    token: str,
    admin: User = Depends(require_admin)
):
    """Test Plex connection with provided credentials."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{url.rstrip('/')}/",
                params={"X-Plex-Token": token},
                timeout=10
            )
            if response.status_code == 200:
                return {"connected": True}
            else:
                return {"connected": False, "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


@router.post("/bandcamp/sync")
async def trigger_bandcamp_sync(
    admin: User = Depends(require_admin)
):
    """Trigger Bandcamp collection sync."""
    from app.tasks.downloads import sync_bandcamp_task

    if not settings.bandcamp_cookies:
        raise HTTPException(status_code=400, detail="Bandcamp cookies not configured")

    task = sync_bandcamp_task.delay()
    return {"status": "started", "task_id": task.id}
