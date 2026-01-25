"""TorrentLeech integration for checking/uploading releases."""
import httpx
from typing import Optional
from pathlib import Path
from app.config import settings


class TorrentLeechError(Exception):
    """TorrentLeech operation failed."""
    pass


class TorrentLeechClient:
    """TorrentLeech API client."""

    def __init__(self):
        self.api_key = settings.torrentleech_key
        self.base_url = "https://www.torrentleech.org/api"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def search(self, query: str, category: str = "music") -> list[dict]:
        """Search TorrentLeech for existing releases.

        Args:
            query: Search query (release name)
            category: Category to search (music)

        Returns:
            List of matching torrents
        """
        if not self.api_key:
            raise TorrentLeechError("TorrentLeech API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/torrents/search/{query}",
                headers=self.headers,
                params={"category": category},
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("torrents", [])

    async def check_exists(self, release_name: str) -> bool:
        """Check if release already exists on TorrentLeech.

        Normalizes the release name for comparison.
        """
        # Normalize: lowercase, replace spaces with dots
        normalized = release_name.lower().replace(" ", ".")

        try:
            results = await self.search(normalized)
        except Exception:
            # If search fails, assume doesn't exist
            return False

        for result in results:
            result_normalized = result.get("name", "").lower()
            if normalized in result_normalized:
                return True

        return False

    async def upload(
        self,
        torrent_path: Path,
        nfo_path: Optional[Path] = None,
        category: str = "music"
    ) -> dict:
        """Upload torrent to TorrentLeech.

        Args:
            torrent_path: Path to .torrent file
            nfo_path: Optional NFO file path
            category: Upload category

        Returns:
            Upload response with torrent ID
        """
        if not self.api_key:
            raise TorrentLeechError("TorrentLeech API key not configured")

        files = {
            "torrent": ("torrent.torrent", open(torrent_path, "rb"), "application/x-bittorrent")
        }

        if nfo_path and nfo_path.exists():
            files["nfo"] = ("release.nfo", open(nfo_path, "rb"), "text/plain")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/torrents/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data={"category": category},
                timeout=60
            )
            response.raise_for_status()
            return response.json()
