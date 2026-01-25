"""Direct Qobuz API client for catalog browsing.

Used for browsing catalog (search, artist discography, album details).
Downloads still use streamrip via StreamripClient.
"""
import asyncio
import hashlib
import platform
import time
from collections import deque
from pathlib import Path
from typing import Optional
import httpx

from app.config import get_settings


class QobuzAPIError(Exception):
    """Qobuz API request failed."""
    pass


def _get_streamrip_app_credentials() -> tuple[str, str]:
    """Try to extract app_id and app_secret from streamrip config.

    Returns:
        Tuple of (app_id, app_secret) or empty strings if not found.
    """
    # Find streamrip config location
    if platform.system() == "Darwin":
        config_path = Path.home() / "Library" / "Application Support" / "streamrip" / "config.toml"
    else:
        config_path = Path.home() / ".config" / "streamrip" / "config.toml"

    if not config_path.exists():
        return "", ""

    try:
        content = config_path.read_text()
        app_id = ""
        app_secret = ""

        # Parse TOML manually (avoid adding toml dependency)
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("app_id"):
                # app_id = "123456"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    app_id = parts[1].strip().strip('"').strip("'")
            elif line.startswith("secrets"):
                # secrets = ["secret1", "secret2"] - take first one
                parts = line.split("=", 1)
                if len(parts) == 2:
                    val = parts[1].strip()
                    if val.startswith("["):
                        # Extract first secret from array
                        import re
                        match = re.search(r'"([^"]+)"', val)
                        if match:
                            app_secret = match.group(1)

        return app_id, app_secret
    except Exception:
        return "", ""


class QobuzAPI:
    """Direct Qobuz API client.

    Used for browsing catalog with artwork URLs.
    Downloads still use streamrip.
    """

    BASE_URL = "https://www.qobuz.com/api.json/0.2"

    # Default app credentials - may need updating if Qobuz rotates them
    # Can be overridden via QOBUZ_APP_ID and QOBUZ_APP_SECRET env vars
    # Or extracted from streamrip config if available
    DEFAULT_APP_ID = "285473059"
    DEFAULT_APP_SECRET = ""

    # Region for web URLs (not API)
    REGIONS = {
        "us": "us-en",
        "uk": "gb-en",
        "de": "de-de",
        "fr": "fr-fr",
        "nl": "nl-nl",
        "es": "es-es",
        "it": "it-it",
    }

    def __init__(self, region: str = "us"):
        self._user_auth_token: Optional[str] = None
        self._token_expiry: float = 0
        self._client = httpx.AsyncClient(timeout=30.0)
        self._region = self.REGIONS.get(region, "us-en")
        # Rate limiting: 50 requests per minute
        self._request_times: deque = deque(maxlen=50)
        self._rate_limit = 50
        # Response caching
        self._cache: dict = {}
        self._cache_ttl = 300  # 5 minutes

        # Get app credentials (priority: env vars > streamrip config > defaults)
        settings = get_settings()
        self._app_id = settings.qobuz_app_id or ""
        self._app_secret = settings.qobuz_app_secret or ""

        if not self._app_id:
            # Try to extract from streamrip config
            streamrip_id, streamrip_secret = _get_streamrip_app_credentials()
            if streamrip_id:
                self._app_id = streamrip_id
                self._app_secret = streamrip_secret or self._app_secret

        # Fall back to defaults
        if not self._app_id:
            self._app_id = self.DEFAULT_APP_ID
        if not self._app_secret:
            self._app_secret = self.DEFAULT_APP_SECRET

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _ensure_auth(self) -> None:
        """Ensure we have a valid user auth token."""
        if self._user_auth_token and time.time() < self._token_expiry:
            return

        settings = get_settings()
        if not settings.qobuz_email or not settings.qobuz_password:
            raise QobuzAPIError(
                "Qobuz credentials not configured. "
                "Go to Settings > Sources > Qobuz."
            )

        if not self._app_id:
            raise QobuzAPIError(
                "Qobuz app_id not configured. Set QOBUZ_APP_ID env var "
                "or install streamrip and run 'rip config --qobuz' first."
            )

        # Login to get user token
        # Password must be MD5 hashed
        password_hash = hashlib.md5(
            settings.qobuz_password.encode()
        ).hexdigest()

        response = await self._client.post(
            f"{self.BASE_URL}/user/login",
            params={
                "app_id": self._app_id,
                "username": settings.qobuz_email,
                "password": password_hash,
            }
        )

        if response.status_code != 200:
            raise QobuzAPIError(f"Login failed: {response.text}")

        data = response.json()
        self._user_auth_token = data.get("user_auth_token")

        if not self._user_auth_token:
            raise QobuzAPIError("No auth token in response")

        # Token typically lasts 24 hours, refresh after 23
        self._token_expiry = time.time() + (23 * 60 * 60)

    async def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = time.time()
        # Remove requests older than 1 minute
        while self._request_times and now - self._request_times[0] > 60:
            self._request_times.popleft()

        if len(self._request_times) >= self._rate_limit:
            # Wait until oldest request is > 1 minute old
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    def _get_cached(self, key: str) -> Optional[dict]:
        """Get cached response if still valid."""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _set_cached(self, key: str, data: dict) -> None:
        """Cache response."""
        self._cache[key] = (data, time.time())

    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request."""
        await self._check_rate_limit()
        await self._ensure_auth()

        params = params or {}
        params["app_id"] = self._app_id
        params["user_auth_token"] = self._user_auth_token

        response = await self._client.get(
            f"{self.BASE_URL}/{endpoint}",
            params=params
        )

        if response.status_code != 200:
            raise QobuzAPIError(f"Request failed: {response.text}")

        return response.json()

    async def search_albums(self, query: str, limit: int = 20) -> list[dict]:
        """Search for albums.

        Returns list of albums with artwork URLs.
        """
        data = await self._request("album/search", {
            "query": query,
            "limit": limit,
        })

        albums = []
        for item in data.get("albums", {}).get("items", []):
            albums.append(self._parse_album(item))

        return albums

    async def search_artists(self, query: str, limit: int = 20) -> list[dict]:
        """Search for artists."""
        data = await self._request("artist/search", {
            "query": query,
            "limit": limit,
        })

        artists = []
        for item in data.get("artists", {}).get("items", []):
            artists.append(self._parse_artist(item))

        return artists

    async def search_tracks(self, query: str, limit: int = 20) -> list[dict]:
        """Search for tracks."""
        data = await self._request("track/search", {
            "query": query,
            "limit": limit,
        })

        tracks = []
        for item in data.get("tracks", {}).get("items", []):
            tracks.append(self._parse_track(item))

        return tracks

    async def get_artist(self, artist_id: str) -> dict:
        """Get artist details with discography (cached)."""
        cache_key = f"artist:{artist_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        data = await self._request("artist/get", {
            "artist_id": artist_id,
            "extra": "albums",
            "limit": 100,
        })

        artist = self._parse_artist(data)
        artist["albums"] = [
            self._parse_album(a)
            for a in data.get("albums", {}).get("items", [])
        ]

        self._set_cached(cache_key, artist)
        return artist

    async def get_album(self, album_id: str) -> dict:
        """Get album details with track listing (cached)."""
        cache_key = f"album:{album_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        data = await self._request("album/get", {
            "album_id": album_id,
        })

        album = self._parse_album(data)
        album["tracks"] = [
            self._parse_track(t)
            for t in data.get("tracks", {}).get("items", [])
        ]

        self._set_cached(cache_key, album)
        return album

    def _parse_album(self, data: dict) -> dict:
        """Parse album data into consistent format."""
        image = data.get("image", {}) or {}
        artist = data.get("artist", {}) or {}

        return {
            "id": str(data.get("id", "")),
            "title": data.get("title", ""),
            "artist_id": str(artist.get("id", "")),
            "artist_name": artist.get("name", "Unknown"),
            "year": str(data.get("release_date_original", ""))[:4],
            "track_count": data.get("tracks_count", 0),
            "duration": data.get("duration", 0),
            "label": data.get("label", {}).get("name", "") if isinstance(data.get("label"), dict) else "",
            "genre": data.get("genre", {}).get("name", "") if isinstance(data.get("genre"), dict) else "",
            # Quality info
            "hires": data.get("hires", False),
            "hires_streamable": data.get("hires_streamable", False),
            "maximum_bit_depth": data.get("maximum_bit_depth", 16),
            "maximum_sampling_rate": data.get("maximum_sampling_rate", 44.1),
            # Artwork URLs (multiple sizes)
            "artwork_small": image.get("small", ""),
            "artwork_thumbnail": image.get("thumbnail", ""),
            "artwork_large": image.get("large", ""),
            "artwork_url": image.get("large", ""),  # Default for compatibility
            # Qobuz URL for streamrip download
            "url": f"https://www.qobuz.com/{self._region}/album/{data.get('id', '')}",
        }

    def _parse_artist(self, data: dict) -> dict:
        """Parse artist data into consistent format."""
        image = data.get("image", {}) or {}

        return {
            "id": str(data.get("id", "")),
            "name": data.get("name", "Unknown"),
            "biography": data.get("biography", {}).get("content", "") if isinstance(data.get("biography"), dict) else "",
            "album_count": data.get("albums_count", 0),
            # Artist images
            "image_small": image.get("small", ""),
            "image_medium": image.get("medium", ""),
            "image_large": image.get("large", ""),
            "image_url": image.get("medium", ""),  # Default
        }

    def _parse_track(self, data: dict) -> dict:
        """Parse track data into consistent format."""
        album = data.get("album", {}) or {}
        album_image = album.get("image", {}) or {}
        performer = data.get("performer", {}) or {}

        return {
            "id": str(data.get("id", "")),
            "title": data.get("title", ""),
            "track_number": data.get("track_number", 0),
            "disc_number": data.get("media_number", 1),  # For multi-disc albums
            "duration": data.get("duration", 0),
            "album_id": str(album.get("id", "")),
            "album_title": album.get("title", ""),
            "album_artwork": album_image.get("thumbnail", ""),  # For track search results
            "artist_name": performer.get("name", "Unknown"),
            # Quality
            "hires": data.get("hires", False),
            "maximum_bit_depth": data.get("maximum_bit_depth", 16),
            "maximum_sampling_rate": data.get("maximum_sampling_rate", 44.1),
            # Preview URL (30-second clip) - only if previewable
            "preview_url": f"https://streaming-qobuz-std.akamaized.net/file?uid={data.get('id')}&fmt=mp3" if data.get("previewable") else ""
        }


# Singleton instances by region
_qobuz_api_instances: dict[str, QobuzAPI] = {}


def get_qobuz_api(region: str = "us") -> QobuzAPI:
    """Get or create QobuzAPI instance for region.

    Args:
        region: Region code (us, uk, de, fr, nl, es, it). Default: us

    Returns:
        QobuzAPI instance for the specified region
    """
    global _qobuz_api_instances
    if region not in _qobuz_api_instances:
        _qobuz_api_instances[region] = QobuzAPI(region=region)
    return _qobuz_api_instances[region]


def reset_qobuz_api() -> None:
    """Reset all QobuzAPI instances. Useful for testing."""
    global _qobuz_api_instances
    _qobuz_api_instances = {}
