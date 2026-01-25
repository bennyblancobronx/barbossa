"""Plex integration for library scanning."""
import httpx
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class PlexError(Exception):
    """Plex operation failed."""
    pass


class PlexClient:
    """Plex Media Server API client."""

    def __init__(self):
        self.base_url = settings.plex_url.rstrip("/") if settings.plex_url else ""
        self.token = settings.plex_token
        self.music_section = settings.plex_music_section

    @property
    def enabled(self) -> bool:
        """Check if Plex integration is enabled."""
        return bool(self.base_url and self.token)

    @property
    def headers(self) -> dict:
        return {
            "X-Plex-Token": self.token,
            "Accept": "application/json"
        }

    async def test_connection(self) -> bool:
        """Test connection to Plex server."""
        if not self.enabled:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/",
                    headers=self.headers,
                    timeout=10
                )
                return response.status_code == 200
            except Exception as e:
                logger.warning(f"Plex connection test failed: {e}")
                return False

    async def get_sections(self) -> list:
        """Get library sections."""
        if not self.enabled:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/library/sections",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            return [
                {
                    "key": section["key"],
                    "title": section["title"],
                    "type": section["type"]
                }
                for section in data.get("MediaContainer", {}).get("Directory", [])
            ]

    async def get_music_section_key(self) -> Optional[str]:
        """Get the music library section key."""
        if self.music_section:
            return self.music_section

        sections = await self.get_sections()
        for section in sections:
            if section["type"] == "artist":
                return section["key"]

        return None

    async def scan_library(
        self,
        section_key: Optional[str] = None,
        path: Optional[str] = None
    ):
        """Trigger library scan.

        Args:
            section_key: Library section key (defaults to music section)
            path: Optional specific path to scan
        """
        if not self.enabled:
            logger.debug("Plex not enabled, skipping scan")
            return

        key = section_key or await self.get_music_section_key()

        if not key:
            raise PlexError("No music section configured or found")

        url = f"{self.base_url}/library/sections/{key}/refresh"

        params = {}
        if path:
            params["path"] = path

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()

        logger.info(f"Plex scan triggered for section {key}" +
                    (f" path={path}" if path else ""))

    async def get_scan_status(self, section_key: Optional[str] = None) -> dict:
        """Get current scan status."""
        if not self.enabled:
            return {"scanning": False, "refreshing": False}

        key = section_key or await self.get_music_section_key()

        if not key:
            return {"scanning": False, "refreshing": False}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/library/sections/{key}",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            container = data.get("MediaContainer", {})

            return {
                "scanning": container.get("scanning", False),
                "refreshing": container.get("refreshing", False)
            }


async def trigger_plex_scan(path: Optional[str] = None):
    """Trigger Plex scan if enabled.

    This is a convenience function that handles errors gracefully.
    Plex scanning is optional and should not fail the import.

    Args:
        path: Optional specific path to scan (e.g., artist folder)
    """
    if not settings.plex_url or not settings.plex_token:
        return

    if not settings.plex_auto_scan:
        return

    client = PlexClient()

    try:
        await client.scan_library(path=path)
    except Exception as e:
        # Log but don't fail - Plex scan is optional
        logger.warning(f"Plex scan failed: {e}")
