"""Settings API endpoints."""
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.config import get_settings
from app.integrations.lidarr import LidarrClient
from app.integrations.plex import PlexClient
from app.integrations.bandcamp import BandcampClient


router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    """Settings response."""
    # Path mapping (for UI display translation)
    music_path_host: str  # Host path, e.g., /Volumes/media/library/music
    music_path_container: str = "/music"  # Container mount point

    # Paths (container paths)
    music_library: str    # /music/artists - Master library
    music_users: str      # /music/users - Per-user symlinked libraries
    music_downloads: str  # /music/downloads - Temp download staging
    music_import: str     # /music/import - Watch folder for imports
    music_export: str     # /music/export - Export destination
    music_database: str   # /music/database - Database backups

    # Qobuz
    qobuz_enabled: bool
    qobuz_email: str  # Masked email for display
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
    music_library: Optional[str] = None
    music_users: Optional[str] = None
    qobuz_email: Optional[str] = None
    qobuz_password: Optional[str] = None
    qobuz_quality: Optional[int] = None
    lidarr_url: Optional[str] = None
    lidarr_api_key: Optional[str] = None
    plex_url: Optional[str] = None
    plex_token: Optional[str] = None
    plex_auto_scan: Optional[bool] = None


@router.get("", response_model=SettingsResponse)
async def get_current_settings(
    user: User = Depends(get_current_user)
):
    """Get application settings."""
    # Get fresh settings instance (not stale module-level cache)
    settings = get_settings()

    # Test connections
    lidarr_connected = None
    plex_connected = None

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

    # Mask email for display (show first 2 chars + domain)
    qobuz_email_masked = ""
    if settings.qobuz_email:
        parts = settings.qobuz_email.split("@")
        if len(parts) == 2:
            local = parts[0]
            domain = parts[1]
            masked_local = local[:2] + "*" * max(0, len(local) - 2)
            qobuz_email_masked = f"{masked_local}@{domain}"
        else:
            qobuz_email_masked = settings.qobuz_email[:2] + "***"

    return SettingsResponse(
        music_path_host=settings.music_path_host,
        music_library=settings.music_library,
        music_users=settings.music_users,
        music_downloads=settings.music_downloads,
        music_import=settings.music_import,
        music_export=settings.music_export,
        music_database=settings.music_database,
        qobuz_enabled=bool(settings.qobuz_email and settings.qobuz_password),
        qobuz_email=qobuz_email_masked,
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


def _update_env_file(updates: dict) -> None:
    """Persist settings to .env file.

    Args:
        updates: Dict of ENV_VAR_NAME -> value to update
    """
    env_path = Path(__file__).parent.parent.parent / ".env"

    # Read existing .env content
    if env_path.exists():
        with open(env_path, 'r') as f:
            lines = f.readlines()
    else:
        lines = []

    # Update or add each setting
    for key, value in updates.items():
        pattern = f"^{key}="
        new_line = f"{key}={value}\n"
        found = False

        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = new_line
                found = True
                break

        if not found:
            # Add new line (with comment section header if needed)
            lines.append(new_line)

    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)


@router.put("")
async def update_settings(
    data: SettingsUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update application settings.

    Updates both environment variables (immediate) and .env file (persistent).
    """
    env_updates = {}

    if data.music_library is not None:
        # Validate path exists and is a directory
        lib_path = Path(data.music_library)
        if not lib_path.exists():
            raise HTTPException(status_code=400, detail="Music library path does not exist")
        if not lib_path.is_dir():
            raise HTTPException(status_code=400, detail="Music library path is not a directory")
        os.environ["MUSIC_LIBRARY"] = str(lib_path)
        env_updates["MUSIC_LIBRARY"] = str(lib_path)

    if data.music_users is not None:
        # Validate path exists and is a directory
        users_path = Path(data.music_users)
        if not users_path.exists():
            raise HTTPException(status_code=400, detail="Users library path does not exist")
        if not users_path.is_dir():
            raise HTTPException(status_code=400, detail="Users library path is not a directory")
        os.environ["MUSIC_USERS"] = str(users_path)
        env_updates["MUSIC_USERS"] = str(users_path)

    if data.qobuz_email is not None:
        os.environ["QOBUZ_EMAIL"] = data.qobuz_email
        env_updates["QOBUZ_EMAIL"] = data.qobuz_email

    if data.qobuz_password is not None:
        os.environ["QOBUZ_PASSWORD"] = data.qobuz_password
        env_updates["QOBUZ_PASSWORD"] = data.qobuz_password

    if data.qobuz_quality is not None:
        os.environ["QOBUZ_QUALITY"] = str(data.qobuz_quality)
        env_updates["QOBUZ_QUALITY"] = str(data.qobuz_quality)

    if data.lidarr_url is not None:
        os.environ["LIDARR_URL"] = data.lidarr_url
        env_updates["LIDARR_URL"] = data.lidarr_url

    if data.lidarr_api_key is not None:
        os.environ["LIDARR_API_KEY"] = data.lidarr_api_key
        env_updates["LIDARR_API_KEY"] = data.lidarr_api_key

    if data.plex_url is not None:
        os.environ["PLEX_URL"] = data.plex_url
        env_updates["PLEX_URL"] = data.plex_url

    if data.plex_token is not None:
        os.environ["PLEX_TOKEN"] = data.plex_token
        env_updates["PLEX_TOKEN"] = data.plex_token

    if data.plex_auto_scan is not None:
        os.environ["PLEX_AUTO_SCAN"] = str(data.plex_auto_scan).lower()
        env_updates["PLEX_AUTO_SCAN"] = str(data.plex_auto_scan).lower()

    # Persist to .env file
    if env_updates:
        try:
            _update_env_file(env_updates)
        except Exception as e:
            # Log but don't fail - in-memory update still worked
            import logging
            logging.warning(f"Failed to persist settings to .env: {e}")

    # Clear settings cache to reload fresh values on next request
    get_settings.cache_clear()

    return {"status": "updated"}


@router.post("/test/lidarr")
async def test_lidarr_connection(
    url: str,
    api_key: str,
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """Trigger Bandcamp collection sync."""
    from app.tasks.downloads import sync_bandcamp_task

    settings = get_settings()
    if not settings.bandcamp_cookies:
        raise HTTPException(status_code=400, detail="Bandcamp cookies not configured")

    task = sync_bandcamp_task.delay()
    return {"status": "started", "task_id": task.id}


class BrowseResponse(BaseModel):
    """Directory browser response."""
    current_path: str
    directories: List[str]


@router.get("/browse", response_model=BrowseResponse)
async def browse_directory(
    path: str = Query("/", description="Path to browse"),
    current_user: User = Depends(get_current_user)
):
    """Browse filesystem directories for path selection.

    Returns list of subdirectories at the given path.
    """
    # Normalize and validate path
    try:
        target = Path(path).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Security: prevent access outside allowed roots
    allowed_roots = ["/", "/music", "/data", "/mnt", "/Volumes", "/home"]
    if not any(str(target).startswith(root) for root in allowed_roots):
        raise HTTPException(status_code=403, detail="Access denied to this path")

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")

    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # List subdirectories only (no files)
    try:
        directories = sorted([
            entry.name for entry in target.iterdir()
            if entry.is_dir() and not entry.name.startswith('.')
        ])
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return BrowseResponse(
        current_path=str(target),
        directories=directories
    )
