"""Lidarr integration for artist requests."""
import httpx
from typing import Optional, List
from app.config import settings


class LidarrError(Exception):
    """Lidarr operation failed."""
    pass


class LidarrClient:
    """Lidarr API client."""

    def __init__(self):
        self.base_url = settings.lidarr_url.rstrip("/") if settings.lidarr_url else ""
        self.api_key = settings.lidarr_api_key

    @property
    def headers(self) -> dict:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def test_connection(self) -> bool:
        """Test connection to Lidarr."""
        if not self.base_url or not self.api_key:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/system/status",
                    headers=self.headers,
                    timeout=10
                )
                return response.status_code == 200
            except Exception:
                return False

    async def search_artist(self, query: str) -> List[dict]:
        """Search for artist in Lidarr/MusicBrainz."""
        if not self.base_url:
            raise LidarrError("Lidarr URL not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/artist/lookup",
                headers=self.headers,
                params={"term": query},
                timeout=30
            )
            response.raise_for_status()
            return response.json()

    async def add_artist(
        self,
        mbid: str,
        name: str,
        quality_profile_id: int = 1,
        metadata_profile_id: int = 1,
        monitored: bool = True,
        search_for_missing: bool = True
    ) -> dict:
        """Add artist to Lidarr for monitoring/downloading."""
        root_folder = await self._get_root_folder()

        payload = {
            "foreignArtistId": mbid,
            "artistName": name,
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder,
            "monitored": monitored,
            "addOptions": {
                "searchForMissingAlbums": search_for_missing
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/artist",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

    async def get_queue(self) -> List[dict]:
        """Get current download queue."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/queue",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])

    async def get_artists(self) -> List[dict]:
        """Get all monitored artists."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/artist",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

    async def get_history(self, limit: int = 50) -> List[dict]:
        """Get download history."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/history",
                headers=self.headers,
                params={
                    "pageSize": limit,
                    "sortKey": "date",
                    "sortDirection": "descending"
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("records", [])

    async def trigger_search(self, artist_id: int):
        """Trigger search for artist's music."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/api/v1/command",
                headers=self.headers,
                json={"name": "ArtistSearch", "artistId": artist_id},
                timeout=30
            )

    async def _get_root_folder(self) -> str:
        """Get first root folder path."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/rootfolder",
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            folders = response.json()
            if not folders:
                raise LidarrError("No root folders configured in Lidarr")
            return folders[0]["path"]
