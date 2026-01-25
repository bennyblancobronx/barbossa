# Qobuz API Integration - Implementation Guide

**Purpose:** Enable browsing Qobuz catalog (artists, albums, tracks) with artwork before downloading.

**Prerequisites:**
- Barbossa backend running
- Existing Qobuz credentials configured in Settings
- Familiarity with Python/FastAPI and React

**New Dependencies:**
```bash
# Add to backend/requirements.txt
httpx>=0.25.0
```

---

## Phase 1: Backend API Client

**Goal:** Create a working Qobuz API client that can authenticate and search.

**Files to create:**
- `backend/app/integrations/qobuz_api.py`

### Step 1.1: Understand Qobuz Auth

Qobuz uses a two-part auth system:

```
1. App credentials (hardcoded)
   - app_id: identifies the application
   - app_secret: used to sign requests

2. User credentials (from Settings)
   - email + password -> user_auth_token
   - Token lasts ~24 hours
```

### Step 1.2: Create the API Client

Create `backend/app/integrations/qobuz_api.py`:

```python
"""Direct Qobuz API client for catalog browsing."""
import hashlib
import time
from typing import Optional
import httpx

from app.config import get_settings


class QobuzAPIError(Exception):
    """Qobuz API request failed."""
    pass


class QobuzAPI:
    """Direct Qobuz API client.

    Used for browsing catalog (search, artist discography, album details).
    Downloads still use streamrip.
    """

    BASE_URL = "https://www.qobuz.com/api.json/0.2"

    # App credentials (same as streamrip uses)
    # These are public knowledge, used by multiple open-source clients
    APP_ID = "285473059"
    APP_SECRET = "YOUR_APP_SECRET_HERE"  # See note below

    def __init__(self):
        self._user_auth_token: Optional[str] = None
        self._token_expiry: float = 0
        self._client = httpx.AsyncClient(timeout=30.0)

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

        # Login to get user token
        # Password must be MD5 hashed
        password_hash = hashlib.md5(
            settings.qobuz_password.encode()
        ).hexdigest()

        response = await self._client.post(
            f"{self.BASE_URL}/user/login",
            params={
                "app_id": self.APP_ID,
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

    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request."""
        await self._ensure_auth()

        params = params or {}
        params["app_id"] = self.APP_ID
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
        """Get artist details with discography."""
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

        return artist

    async def get_album(self, album_id: str) -> dict:
        """Get album details with track listing."""
        data = await self._request("album/get", {
            "album_id": album_id,
        })

        album = self._parse_album(data)
        album["tracks"] = [
            self._parse_track(t)
            for t in data.get("tracks", {}).get("items", [])
        ]

        return album

    def _parse_album(self, data: dict) -> dict:
        """Parse album data into consistent format."""
        image = data.get("image", {})
        artist = data.get("artist", {})

        return {
            "id": str(data.get("id", "")),
            "title": data.get("title", ""),
            "artist_id": str(artist.get("id", "")),
            "artist_name": artist.get("name", "Unknown"),
            "year": str(data.get("release_date_original", ""))[:4],
            "track_count": data.get("tracks_count", 0),
            "duration": data.get("duration", 0),
            "label": data.get("label", {}).get("name", ""),
            "genre": data.get("genre", {}).get("name", ""),
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
            "url": f"https://www.qobuz.com/us-en/album/{data.get('id', '')}",
        }

    def _parse_artist(self, data: dict) -> dict:
        """Parse artist data into consistent format."""
        image = data.get("image", {}) or {}

        return {
            "id": str(data.get("id", "")),
            "name": data.get("name", "Unknown"),
            "biography": data.get("biography", {}).get("content", ""),
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

        return {
            "id": str(data.get("id", "")),
            "title": data.get("title", ""),
            "track_number": data.get("track_number", 0),
            "disc_number": data.get("media_number", 1),  # For multi-disc albums
            "duration": data.get("duration", 0),
            "album_id": str(album.get("id", "")),
            "album_title": album.get("title", ""),
            "album_artwork": album_image.get("thumbnail", ""),  # For track search results
            "artist_name": data.get("performer", {}).get("name", "Unknown"),
            # Quality
            "hires": data.get("hires", False),
            "maximum_bit_depth": data.get("maximum_bit_depth", 16),
            "maximum_sampling_rate": data.get("maximum_sampling_rate", 44.1),
            # Preview URL (30-second clip)
            "preview_url": data.get("previewable", False) and
                          f"https://streaming-qobuz-std.akamaized.net/file?uid={data.get('id')}&fmt=mp3" or "",
        }


# Singleton instance
_qobuz_api: Optional[QobuzAPI] = None


def get_qobuz_api() -> QobuzAPI:
    """Get or create QobuzAPI singleton."""
    global _qobuz_api
    if _qobuz_api is None:
        _qobuz_api = QobuzAPI()
    return _qobuz_api
```

### Step 1.3: App Secret and App ID

The `APP_ID` and `APP_SECRET` are needed for Qobuz API authentication. To get them:

**Option 1: From streamrip source (recommended)**
```bash
# Check streamrip's source code
pip show streamrip
# Navigate to the installed location and find qobuz.py or config
# Look for app_id and secrets dictionary
```

**Option 2: From Qobuz web player**
1. Open Qobuz web player in browser
2. Open DevTools > Network tab
3. Filter by "api.qobuz.com"
4. Look for requests with `app_id` parameter
5. The app_secret is used for request signing (X-Request-Sign header)

**Current known working values (as of 2025):**
```python
APP_ID = "285473059"
# App secret changes periodically - check streamrip issues if auth fails
```

### Step 1.4: Rate Limiting

Qobuz API has rate limits (~50 requests/minute). Add rate limiting to avoid blocks:

```python
import asyncio
from collections import deque
from time import time

class QobuzAPI:
    # ... existing code ...

    def __init__(self):
        # ... existing init ...
        self._request_times: deque = deque(maxlen=50)
        self._rate_limit = 50  # requests per minute

    async def _check_rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = time()
        # Remove requests older than 1 minute
        while self._request_times and now - self._request_times[0] > 60:
            self._request_times.popleft()

        if len(self._request_times) >= self._rate_limit:
            # Wait until oldest request is > 1 minute old
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self._request_times.append(now)

    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request."""
        await self._check_rate_limit()  # Add this line
        await self._ensure_auth()
        # ... rest of method
```

### Step 1.5: Response Caching

Add simple caching to reduce API calls:

```python
from functools import lru_cache
from typing import Optional
import time

class QobuzAPI:
    # ... existing code ...

    def __init__(self):
        # ... existing init ...
        self._cache: dict = {}
        self._cache_ttl = 300  # 5 minutes

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

    async def get_artist(self, artist_id: str) -> dict:
        """Get artist details with discography (cached)."""
        cache_key = f"artist:{artist_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # ... existing fetch logic ...

        self._set_cached(cache_key, artist)
        return artist

    async def get_album(self, album_id: str) -> dict:
        """Get album details with track listing (cached)."""
        cache_key = f"album:{album_id}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # ... existing fetch logic ...

        self._set_cached(cache_key, album)
        return album
```

### Step 1.6: Region Handling

Qobuz URLs are region-specific. Make it configurable:

```python
class QobuzAPI:
    BASE_URL = "https://www.qobuz.com/api.json/0.2"

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
        # ... existing init ...
        self._region = self.REGIONS.get(region, "us-en")

    def _parse_album(self, data: dict) -> dict:
        # ... existing code ...
        return {
            # ... other fields ...
            # Use configured region in URL
            "url": f"https://www.qobuz.com/{self._region}/album/{data.get('id', '')}",
        }
```

### Step 1.4: Test the Client

Create a simple test script or add to existing tests:

```python
# backend/tests/test_qobuz_api.py
import pytest
from app.integrations.qobuz_api import get_qobuz_api, QobuzAPIError


@pytest.mark.asyncio
async def test_search_albums():
    """Test album search returns results with artwork."""
    api = get_qobuz_api()

    results = await api.search_albums("Pink Floyd", limit=5)

    assert len(results) > 0
    assert results[0]["title"]
    assert results[0]["artist_name"]
    assert results[0]["artwork_url"]  # This is the key test


@pytest.mark.asyncio
async def test_search_artists():
    """Test artist search returns results with images."""
    api = get_qobuz_api()

    results = await api.search_artists("Beatles", limit=5)

    assert len(results) > 0
    assert results[0]["name"]
    assert results[0]["album_count"] > 0


@pytest.mark.asyncio
async def test_get_artist_discography():
    """Test fetching artist with albums."""
    api = get_qobuz_api()

    # First search to get an artist ID
    artists = await api.search_artists("Pink Floyd", limit=1)
    artist_id = artists[0]["id"]

    # Get full artist with discography
    artist = await api.get_artist(artist_id)

    assert artist["name"] == "Pink Floyd"
    assert len(artist["albums"]) > 0
    assert artist["albums"][0]["artwork_url"]


@pytest.mark.asyncio
async def test_get_album_tracks():
    """Test fetching album with track listing."""
    api = get_qobuz_api()

    # Search for a known album
    albums = await api.search_albums("Dark Side of the Moon", limit=1)
    album_id = albums[0]["id"]

    # Get full album with tracks
    album = await api.get_album(album_id)

    assert album["title"]
    assert len(album["tracks"]) > 0
    assert album["tracks"][0]["title"]
    assert album["tracks"][0]["duration"] > 0
```

### Phase 1 Success Criteria

- [ ] `httpx` added to `requirements.txt`
- [ ] `qobuz_api.py` created and imports without errors
- [ ] Can authenticate with existing Qobuz credentials
- [ ] `search_albums()` returns results with `artwork_url`
- [ ] `search_artists()` returns results with `image_url`
- [ ] `get_artist()` returns discography with albums
- [ ] `get_album()` returns track listing with `disc_number`
- [ ] Rate limiting prevents API blocks
- [ ] Caching reduces redundant requests
- [ ] All tests pass

---

## Phase 2: Backend API Routes

**Goal:** Expose Qobuz browsing via REST endpoints.

**Files to create:**
- `backend/app/api/qobuz.py`

**Files to modify:**
- `backend/app/api/__init__.py` (add router)
- `backend/app/main.py` (register router)

### Step 2.1: Create Qobuz Router

Create `backend/app/api/qobuz.py`:

```python
"""Qobuz catalog browsing API endpoints."""
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.integrations.qobuz_api import get_qobuz_api, QobuzAPIError
from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.album import Album


router = APIRouter(prefix="/qobuz", tags=["qobuz"])


# Response schemas
class ArtworkUrls(BaseModel):
    small: str = ""
    thumbnail: str = ""
    large: str = ""


class AlbumResult(BaseModel):
    id: str
    title: str
    artist_id: str
    artist_name: str
    year: str
    track_count: int
    duration: int
    label: str
    genre: str
    hires: bool
    maximum_bit_depth: int
    maximum_sampling_rate: float
    artwork_small: str
    artwork_thumbnail: str
    artwork_large: str
    artwork_url: str
    url: str
    # Library status
    in_library: bool = False  # True if already downloaded
    local_album_id: Optional[int] = None  # ID in local database if exists


class ArtistResult(BaseModel):
    id: str
    name: str
    biography: str = ""
    album_count: int
    image_small: str
    image_medium: str
    image_large: str
    image_url: str


class TrackResult(BaseModel):
    id: str
    title: str
    track_number: int
    disc_number: int = 1  # For multi-disc albums
    duration: int
    album_id: str
    album_title: str
    album_artwork: str = ""  # Thumbnail for track search results
    artist_name: str
    hires: bool
    maximum_bit_depth: int
    maximum_sampling_rate: float
    preview_url: str


class SearchResponse(BaseModel):
    query: str
    type: str
    count: int
    albums: list[AlbumResult] = []
    artists: list[ArtistResult] = []
    tracks: list[TrackResult] = []


class ArtistDetailResponse(ArtistResult):
    albums: list[AlbumResult] = []


class AlbumDetailResponse(AlbumResult):
    tracks: list[TrackResult] = []


def check_albums_in_library(db: Session, albums: list[dict]) -> list[dict]:
    """Check which Qobuz albums exist in local library.

    Matches by normalized artist + album title.
    """
    from app.utils.normalize import normalize_text

    for album in albums:
        # Normalize for comparison
        artist_norm = normalize_text(album["artist_name"])
        title_norm = normalize_text(album["title"])

        # Check if exists locally
        local = db.query(Album).join(Album.artist).filter(
            Album.normalized_title == title_norm,
            Album.artist.has(normalized_name=artist_norm)
        ).first()

        if local:
            album["in_library"] = True
            album["local_album_id"] = local.id
        else:
            album["in_library"] = False
            album["local_album_id"] = None

    return albums


@router.get("/search", response_model=SearchResponse)
async def search_qobuz(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str = Query(
        "album",
        pattern="^(album|artist|track)$",
        description="Search type"
    ),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),  # Require auth
):
    """Search Qobuz catalog.

    Returns results with full artwork URLs.
    Albums include `in_library` flag if already downloaded.
    """
    api = get_qobuz_api()

    try:
        if type == "album":
            items = await api.search_albums(q, limit)
            # Check which albums are already in library
            items = check_albums_in_library(db, items)
            return SearchResponse(
                query=q,
                type=type,
                count=len(items),
                albums=items,
            )
        elif type == "artist":
            items = await api.search_artists(q, limit)
            return SearchResponse(
                query=q,
                type=type,
                count=len(items),
                artists=items,
            )
        elif type == "track":
            items = await api.search_tracks(q, limit)
            return SearchResponse(
                query=q,
                type=type,
                count=len(items),
                tracks=items,
            )
    except QobuzAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/artist/{artist_id}", response_model=ArtistDetailResponse)
async def get_qobuz_artist(
    artist_id: str,
    sort: str = Query("year", pattern="^(year|title)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get artist details with discography.

    Returns artist info and all their albums with artwork.
    Albums include `in_library` flag.
    """
    api = get_qobuz_api()

    try:
        artist = await api.get_artist(artist_id)

        # Check which albums are in library
        if artist.get("albums"):
            artist["albums"] = check_albums_in_library(db, artist["albums"])

            # Sort albums
            if sort == "year":
                artist["albums"].sort(key=lambda a: a.get("year", ""), reverse=True)
            elif sort == "title":
                artist["albums"].sort(key=lambda a: a.get("title", "").lower())

        return ArtistDetailResponse(**artist)
    except QobuzAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/album/{album_id}", response_model=AlbumDetailResponse)
async def get_qobuz_album(
    album_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get album details with track listing.

    Returns album info and all tracks.
    Includes `in_library` flag.
    """
    api = get_qobuz_api()

    try:
        album = await api.get_album(album_id)

        # Check if this album is in library
        albums_checked = check_albums_in_library(db, [album])
        album = albums_checked[0]

        return AlbumDetailResponse(**album)
    except QobuzAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
```

### Step 2.2: Register the Router

Add to `backend/app/api/__init__.py`:

```python
from app.api.qobuz import router as qobuz_router

# In the list of routers
routers = [
    # ... existing routers ...
    qobuz_router,
]
```

Or in `backend/app/main.py` (wherever routers are registered):

```python
from app.api.qobuz import router as qobuz_router

app.include_router(qobuz_router, prefix="/api")
```

### Step 2.3: Test the Endpoints

Use curl or the API docs (FastAPI auto-generates at `/docs`):

```bash
# Search albums
curl "http://localhost:8000/api/qobuz/search?q=Pink%20Floyd&type=album&limit=5"

# Search artists
curl "http://localhost:8000/api/qobuz/search?q=Beatles&type=artist&limit=5"

# Get artist discography
curl "http://localhost:8000/api/qobuz/artist/ARTIST_ID_HERE"

# Get album tracks
curl "http://localhost:8000/api/qobuz/album/ALBUM_ID_HERE"
```

### Phase 2 Success Criteria

- [ ] `/api/qobuz/search?q=X&type=album` returns albums with artwork URLs
- [ ] `/api/qobuz/search?q=X&type=artist` returns artists with image URLs
- [ ] `/api/qobuz/artist/{id}` returns artist + albums
- [ ] `/api/qobuz/album/{id}` returns album + tracks
- [ ] Error handling returns proper HTTP status codes
- [ ] FastAPI docs show all endpoints at `/docs`

---

## Phase 3: Frontend API Service

**Goal:** Add API calls for Qobuz browsing.

**Files to modify:**
- `frontend/src/services/api.js`

### Step 3.1: Add Qobuz API Functions

Add to `frontend/src/services/api.js`:

```javascript
// Qobuz Catalog Browsing
// ----------------------

/**
 * Search Qobuz catalog (albums, artists, or tracks)
 * Returns results with artwork URLs
 */
export const searchQobuzCatalog = (query, type = 'album', limit = 20) => {
  return api.get('/qobuz/search', {
    params: { q: query, type, limit }
  })
}

/**
 * Get artist details with full discography
 * @param {string} artistId - Qobuz artist ID
 * @param {string} sort - Sort order: 'year' (default) or 'title'
 */
export const getQobuzArtist = (artistId, sort = 'year') => {
  return api.get(`/qobuz/artist/${artistId}`, {
    params: { sort }
  })
}

/**
 * Get album details with track listing
 * @param {string} albumId - Qobuz album ID
 */
export const getQobuzAlbum = (albumId) => {
  return api.get(`/qobuz/album/${albumId}`)
}
```

### Step 3.2: Download Integration

The download flow uses the existing download API. Check the current signature:

```bash
grep -A5 "downloadQobuz" frontend/src/services/api.js
```

The existing function should look like:
```javascript
// Existing download function - use this from Qobuz pages
export const downloadQobuz = (url, quality = 4, type = 'album') => {
  return api.post('/downloads/qobuz', { url, quality, type })
}
```

Use this in your download mutations:
```javascript
const downloadMutation = useMutation(
  (album) => api.downloadQobuz(album.url, 4, 'album'),
  // ... callbacks
)
```

### Step 3.3: Update Existing Search Function (Optional)

If you want to replace the old Qobuz search entirely:

```javascript
// Replace old searchQobuz with new version that has artwork
export const searchQobuz = (query, type = 'album', limit = 20) => {
  return searchQobuzCatalog(query, type, limit)
}
```

### Phase 3 Success Criteria

- [ ] `searchQobuzCatalog()` function works
- [ ] `getQobuzArtist()` function works
- [ ] `getQobuzAlbum()` function works
- [ ] Can call from browser console: `api.searchQobuzCatalog('Pink Floyd')`

---

## Phase 4: Update Search Page

**Goal:** Display Qobuz search results with artwork.

**Files to modify:**
- `frontend/src/pages/Search.jsx`

### Step 4.1: Update Search Results Display

The key change is updating how Qobuz results are rendered. Find the section that displays `qobuzResults` and update it:

```jsx
{/* External Results (Qobuz) - Updated with artwork */}
{showExternal && externalSource === 'qobuz' && (
  <section className="search-section">
    <div className="section-header">
      <h2 className="section-title">Qobuz Results</h2>
      <button
        className="btn-ghost text-sm"
        onClick={() => setShowExternal(false)}
      >
        Back to options
      </button>
    </div>

    {qobuzLoading && (
      <div className="loading-state">
        <div className="spinner" />
        <p>Searching Qobuz...</p>
      </div>
    )}

    {!qobuzLoading && qobuzResults?.albums?.length > 0 && (
      <div className="qobuz-results-grid">
        {qobuzResults.albums.map(album => (
          <div key={album.id} className="qobuz-album-card">
            {/* Album Artwork */}
            <div className="qobuz-album-artwork">
              {album.artwork_url ? (
                <img
                  src={album.artwork_url}
                  alt={album.title}
                  loading="lazy"
                  onError={(e) => {
                    e.target.onerror = null
                    e.target.src = '/placeholder-album.svg'
                  }}
                />
              ) : (
                <div className="artwork-placeholder">No Image</div>
              )}

              {/* Quality Badge */}
              {album.hires && (
                <span className="quality-badge hires">
                  {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                </span>
              )}

              {/* In Library Badge */}
              {album.in_library && (
                <span className="in-library-badge" title="Already in your library">
                  In Library
                </span>
              )}
            </div>

            {/* Album Info */}
            <div className="qobuz-album-info">
              <h3 className="album-title">{album.title}</h3>
              <p className="album-artist">
                <a
                  href="#"
                  onClick={(e) => {
                    e.preventDefault()
                    navigate(`/qobuz/artist/${album.artist_id}`)
                  }}
                >
                  {album.artist_name}
                </a>
              </p>
              <p className="album-meta">
                {album.year} | {album.track_count} tracks
              </p>
            </div>

            {/* Actions */}
            <div className="qobuz-album-actions">
              <button
                className="btn-secondary"
                onClick={() => navigate(`/qobuz/album/${album.id}`)}
              >
                View Tracks
              </button>
              {album.in_library ? (
                <button
                  className="btn-ghost"
                  onClick={() => navigate(`/album/${album.local_album_id}`)}
                >
                  View in Library
                </button>
              ) : (
                <button
                  className="btn-primary"
                  onClick={() => downloadMutation.mutate({
                    url: album.url,
                    source: 'qobuz'
                  })}
                  disabled={downloadMutation.isLoading}
                >
                  Download
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    )}

    {/* Artist Results (if searching artists) */}
    {!qobuzLoading && qobuzResults?.artists?.length > 0 && (
      <div className="qobuz-artists-list">
        {qobuzResults.artists.map(artist => (
          <div
            key={artist.id}
            className="qobuz-artist-card"
            onClick={() => navigate(`/qobuz/artist/${artist.id}`)}
          >
            <div className="artist-image">
              {artist.image_url ? (
                <img src={artist.image_url} alt={artist.name} />
              ) : (
                <div className="image-placeholder">?</div>
              )}
            </div>
            <div className="artist-info">
              <h3>{artist.name}</h3>
              <p>{artist.album_count} albums</p>
            </div>
          </div>
        ))}
      </div>
    )}

    {!qobuzLoading && qobuzResults?.count === 0 && (
      <div className="empty-state">
        <p className="text-muted">No results found on Qobuz</p>
      </div>
    )}
  </section>
)}
```

### Step 4.2: Update the Search Query

Update the `searchQobuz` query to use the new endpoint:

```jsx
// External search (Qobuz) - updated to use new endpoint
const {
  data: qobuzResults,
  isLoading: qobuzLoading,
  refetch: searchQobuz
} = useQuery(
  ['search-qobuz', query, type],
  () => api.searchQobuzCatalog(query, type).then(r => r.data),
  { enabled: false }
)
```

### Phase 4 Success Criteria

- [ ] Qobuz search results show album artwork
- [ ] Album cards show quality badges (24/192, etc)
- [ ] Artist names are clickable (link to artist page)
- [ ] "View Tracks" button links to album detail page
- [ ] Download button still works

---

## Phase 5: Artist Discography Page

**Goal:** Create page to browse an artist's full catalog.

**Files to create:**
- `frontend/src/pages/QobuzArtist.jsx`

**Files to modify:**
- `frontend/src/App.jsx` (add route)

### Step 5.1: Create Artist Page

Create `frontend/src/pages/QobuzArtist.jsx`:

```jsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function QobuzArtist() {
  const { artistId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const [sortBy, setSortBy] = useState('year')  // 'year' or 'title'

  const { data: artist, isLoading, error } = useQuery(
    ['qobuz-artist', artistId, sortBy],
    () => api.getQobuzArtist(artistId, sortBy).then(r => r.data),
    { enabled: !!artistId }
  )

  // Download mutation for quick download from artist page
  const downloadMutation = useMutation(
    (album) => api.downloadQobuz(album.url, 4, 'album'),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (err) => {
        addNotification({
          type: 'error',
          message: err.response?.data?.detail || 'Download failed'
        })
      }
    }
  )

  if (isLoading) {
    return (
      <div className="page-qobuz-artist">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading artist...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-qobuz-artist">
        <div className="error-state">
          <p>Failed to load artist</p>
          <button onClick={() => navigate(-1)}>Go Back</button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-qobuz-artist">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs">
        <button className="btn-ghost" onClick={() => navigate(-1)}>
          Back
        </button>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">Artist</span>
      </nav>

      {/* Artist Header */}
      <header className="artist-header">
        <div className="artist-image-large">
          {artist.image_url ? (
            <img
              src={artist.image_large || artist.image_url}
              alt={artist.name}
              onError={(e) => {
                e.target.onerror = null
                e.target.src = '/placeholder-artist.svg'
              }}
            />
          ) : (
            <div className="image-placeholder" />
          )}
        </div>
        <div className="artist-details">
          <span className="label">Qobuz Artist</span>
          <h1>{artist.name}</h1>
          <p className="album-count">{artist.album_count} albums available</p>
        </div>
      </header>

      {/* Discography */}
      <section className="discography">
        <div className="section-header">
          <h2>Discography</h2>
          {/* Sort Options */}
          <div className="sort-options">
            <label>Sort by:</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="year">Year (newest first)</option>
              <option value="title">Title (A-Z)</option>
            </select>
          </div>
        </div>

        <div className="albums-grid">
          {artist.albums?.map(album => (
            <div key={album.id} className="album-card">
              <div
                className="album-artwork"
                onClick={() => navigate(`/qobuz/album/${album.id}`)}
              >
                {album.artwork_url ? (
                  <img
                    src={album.artwork_url}
                    alt={album.title}
                    onError={(e) => {
                      e.target.onerror = null
                      e.target.src = '/placeholder-album.svg'
                    }}
                  />
                ) : (
                  <div className="artwork-placeholder" />
                )}

                {album.hires && (
                  <span className="quality-badge">
                    {album.maximum_bit_depth}/{album.maximum_sampling_rate}
                  </span>
                )}

                {album.in_library && (
                  <span className="in-library-badge">In Library</span>
                )}
              </div>

              <div className="album-info">
                <h3
                  className="album-title clickable"
                  onClick={() => navigate(`/qobuz/album/${album.id}`)}
                >
                  {album.title}
                </h3>
                <p className="album-year">{album.year}</p>
                <p className="album-meta">{album.track_count} tracks</p>
              </div>

              {/* Quick Download Button */}
              <div className="album-actions">
                {album.in_library ? (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => navigate(`/album/${album.local_album_id}`)}
                  >
                    View in Library
                  </button>
                ) : (
                  <button
                    className="btn-primary btn-sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      downloadMutation.mutate(album)
                    }}
                    disabled={downloadMutation.isLoading}
                  >
                    Download
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Biography (if available) */}
      {artist.biography && (
        <section className="biography">
          <h2>About</h2>
          <div dangerouslySetInnerHTML={{ __html: artist.biography }} />
        </section>
      )}
    </div>
  )
}
```

### Step 5.2: Add Route

In `frontend/src/App.jsx`, add the route:

```jsx
import QobuzArtist from './pages/QobuzArtist'

// In routes
<Route path="/qobuz/artist/:artistId" element={<QobuzArtist />} />
```

### Phase 5 Success Criteria

- [ ] `/qobuz/artist/123` loads artist page
- [ ] Artist image displays
- [ ] All albums shown in grid with artwork
- [ ] Quality badges on hi-res albums
- [ ] Clicking album goes to album detail page
- [ ] Biography shows if available

---

## Phase 6: Album Detail Page

**Goal:** Create page to view album tracks before downloading.

**Files to create:**
- `frontend/src/pages/QobuzAlbum.jsx`

**Files to modify:**
- `frontend/src/App.jsx` (add route)

### Step 6.1: Create Album Page

Create `frontend/src/pages/QobuzAlbum.jsx`:

```jsx
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'
import { formatDuration } from '../utils/format'

export default function QobuzAlbum() {
  const { albumId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const { data: album, isLoading, error } = useQuery(
    ['qobuz-album', albumId],
    () => api.getQobuzAlbum(albumId).then(r => r.data),
    { enabled: !!albumId }
  )

  const downloadMutation = useMutation(
    () => api.downloadQobuz(album.url, 4, 'album'),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (err) => {
        addNotification({
          type: 'error',
          message: err.response?.data?.detail || 'Download failed'
        })
      }
    }
  )

  if (isLoading) {
    return (
      <div className="page-qobuz-album">
        <div className="loading-state">
          <div className="spinner" />
          <p>Loading album...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page-qobuz-album">
        <div className="error-state">
          <p>Failed to load album</p>
          <button onClick={() => navigate(-1)}>Go Back</button>
        </div>
      </div>
    )
  }

  // Calculate total duration
  const totalDuration = album.tracks?.reduce((sum, t) => sum + t.duration, 0) || 0

  // Group tracks by disc number for multi-disc albums
  const tracksByDisc = album.tracks?.reduce((acc, track) => {
    const disc = track.disc_number || 1
    if (!acc[disc]) acc[disc] = []
    acc[disc].push(track)
    return acc
  }, {}) || {}
  const discCount = Object.keys(tracksByDisc).length

  return (
    <div className="page-qobuz-album">
      {/* Breadcrumb Navigation */}
      <nav className="breadcrumbs">
        <button className="btn-ghost" onClick={() => navigate(-1)}>
          Back
        </button>
        <span className="breadcrumb-sep">/</span>
        <span
          className="breadcrumb-link"
          onClick={() => navigate(`/qobuz/artist/${album.artist_id}`)}
        >
          {album.artist_name}
        </span>
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-current">{album.title}</span>
      </nav>

      {/* Album Header */}
      <header className="album-header">
        <div className="album-artwork-large">
          {album.artwork_large ? (
            <img
              src={album.artwork_large}
              alt={album.title}
              onError={(e) => {
                e.target.onerror = null
                e.target.src = '/placeholder-album.svg'
              }}
            />
          ) : (
            <div className="artwork-placeholder" />
          )}
        </div>

        <div className="album-details">
          <span className="label">Qobuz Album</span>
          <h1>{album.title}</h1>
          <p
            className="artist-link"
            onClick={() => navigate(`/qobuz/artist/${album.artist_id}`)}
          >
            {album.artist_name}
          </p>

          <div className="album-meta">
            <span>{album.year}</span>
            <span>{album.track_count} tracks</span>
            <span>{formatDuration(totalDuration)}</span>
          </div>

          {/* Genre and Label */}
          <div className="album-extra-meta">
            {album.genre && <span className="genre-tag">{album.genre}</span>}
            {album.label && <span className="label-tag">{album.label}</span>}
          </div>

          {/* Quality Badge */}
          <div className="quality-info">
            {album.hires ? (
              <span className="quality-badge hires">
                Hi-Res {album.maximum_bit_depth}-bit / {album.maximum_sampling_rate}kHz
              </span>
            ) : (
              <span className="quality-badge cd">
                CD Quality 16-bit / 44.1kHz
              </span>
            )}
          </div>

          {/* In Library Status or Download Button */}
          {album.in_library ? (
            <div className="in-library-notice">
              <span className="in-library-badge large">Already in Library</span>
              <button
                className="btn-secondary btn-large"
                onClick={() => navigate(`/album/${album.local_album_id}`)}
              >
                View in Library
              </button>
            </div>
          ) : (
            <button
              className="btn-primary btn-large"
              onClick={() => downloadMutation.mutate()}
              disabled={downloadMutation.isLoading}
            >
              {downloadMutation.isLoading ? 'Starting...' : 'Download Album'}
            </button>
          )}
        </div>
      </header>

      {/* Track Listing */}
      <section className="track-listing">
        <h2>Tracks</h2>

        {/* Multi-disc handling */}
        {discCount > 1 ? (
          Object.entries(tracksByDisc).map(([discNum, tracks]) => (
            <div key={discNum} className="disc-section">
              <h3 className="disc-header">Disc {discNum}</h3>
              <table className="tracks-table">
                <thead>
                  <tr>
                    <th className="col-num">#</th>
                    <th className="col-title">Title</th>
                    <th className="col-duration">Duration</th>
                    <th className="col-quality">Quality</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map(track => (
                    <tr key={track.id}>
                      <td className="col-num">{track.track_number}</td>
                      <td className="col-title">{track.title}</td>
                      <td className="col-duration">{formatDuration(track.duration)}</td>
                      <td className="col-quality">
                        {track.hires ? (
                          <span className="quality-indicator hires">Hi-Res</span>
                        ) : (
                          <span className="quality-indicator cd">CD</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))
        ) : (
          <table className="tracks-table">
            <thead>
              <tr>
                <th className="col-num">#</th>
                <th className="col-title">Title</th>
                <th className="col-duration">Duration</th>
                <th className="col-quality">Quality</th>
              </tr>
            </thead>
            <tbody>
              {album.tracks?.map(track => (
                <tr key={track.id}>
                  <td className="col-num">{track.track_number}</td>
                  <td className="col-title">{track.title}</td>
                  <td className="col-duration">{formatDuration(track.duration)}</td>
                  <td className="col-quality">
                    {track.hires ? (
                      <span className="quality-indicator hires">Hi-Res</span>
                    ) : (
                      <span className="quality-indicator cd">CD</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
```

### Step 6.2: Check for Existing Utility

First, check if `formatDuration` already exists:

```bash
grep -r "formatDuration" frontend/src/
```

If it exists, import from the existing location. If not, add to `frontend/src/utils/format.js`:

```javascript
/**
 * Format duration in seconds to MM:SS or HH:MM:SS
 */
export function formatDuration(seconds) {
  if (!seconds) return '0:00'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}
```

### Step 6.3: Add Route

In `frontend/src/App.jsx`:

```jsx
import QobuzAlbum from './pages/QobuzAlbum'

// In routes
<Route path="/qobuz/album/:albumId" element={<QobuzAlbum />} />
```

### Phase 6 Success Criteria

- [ ] `/qobuz/album/123` loads album page
- [ ] Large album artwork displays
- [ ] Artist name links to artist page
- [ ] All tracks listed with duration
- [ ] Quality badge shows (Hi-Res or CD)
- [ ] Download button starts download
- [ ] Notification appears on success/failure

---

## Phase 7: Styles

**Goal:** Style all new Qobuz components.

**Files to create:**
- `frontend/src/styles/qobuz.css`

### Step 7.1: Create Styles

Create `frontend/src/styles/qobuz.css`:

```css
/* Qobuz Catalog Browsing Styles */

/* Search Results Grid */
.qobuz-results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-top: 1rem;
}

.qobuz-album-card {
  background: var(--surface);
  border-radius: 8px;
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}

.qobuz-album-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.qobuz-album-artwork {
  position: relative;
  aspect-ratio: 1;
  background: var(--surface-darker);
}

.qobuz-album-artwork img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.artwork-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-darker);
  color: var(--text-muted);
}

/* Quality Badge */
.quality-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(0, 0, 0, 0.7);
  color: white;
}

.quality-badge.hires {
  background: var(--accent);
}

.qobuz-album-info {
  padding: 0.75rem;
}

.qobuz-album-info .album-title {
  font-size: 0.9rem;
  font-weight: 600;
  margin: 0 0 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qobuz-album-info .album-artist {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0 0 0.25rem;
}

.qobuz-album-info .album-artist a {
  color: var(--text-muted);
  text-decoration: none;
}

.qobuz-album-info .album-artist a:hover {
  color: var(--accent);
  text-decoration: underline;
}

.qobuz-album-info .album-meta {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.qobuz-album-actions {
  padding: 0 0.75rem 0.75rem;
  display: flex;
  gap: 0.5rem;
}

.qobuz-album-actions button {
  flex: 1;
  font-size: 0.8rem;
  padding: 0.5rem;
}

/* Artist Card (in search results) */
.qobuz-artists-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.qobuz-artist-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem;
  background: var(--surface);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.qobuz-artist-card:hover {
  background: var(--surface-hover);
}

.qobuz-artist-card .artist-image {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-darker);
}

.qobuz-artist-card .artist-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.qobuz-artist-card .artist-info h3 {
  margin: 0;
  font-size: 1rem;
}

.qobuz-artist-card .artist-info p {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

/* Artist Page */
.page-qobuz-artist .artist-header {
  display: flex;
  gap: 2rem;
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--border);
}

.artist-image-large {
  width: 200px;
  height: 200px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--surface-darker);
  flex-shrink: 0;
}

.artist-image-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.artist-details .label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.artist-details h1 {
  margin: 0.5rem 0;
  font-size: 2.5rem;
}

.artist-details .album-count {
  color: var(--text-muted);
}

/* Album Page */
.page-qobuz-album .album-header {
  display: flex;
  gap: 2rem;
  margin-bottom: 2rem;
}

.album-artwork-large {
  width: 250px;
  height: 250px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface-darker);
  flex-shrink: 0;
}

.album-artwork-large img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.album-details .label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.album-details h1 {
  margin: 0.5rem 0;
  font-size: 2rem;
}

.album-details .artist-link {
  font-size: 1.1rem;
  color: var(--text-secondary);
  cursor: pointer;
}

.album-details .artist-link:hover {
  color: var(--accent);
  text-decoration: underline;
}

.album-details .album-meta {
  display: flex;
  gap: 1rem;
  margin: 1rem 0;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.album-details .quality-info {
  margin-bottom: 1.5rem;
}

.album-details .quality-badge {
  position: static;
  display: inline-block;
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.btn-large {
  padding: 0.75rem 2rem;
  font-size: 1rem;
}

/* Track Listing */
.tracks-table {
  width: 100%;
  border-collapse: collapse;
}

.tracks-table th {
  text-align: left;
  padding: 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.tracks-table td {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-light);
}

.tracks-table tr:hover {
  background: var(--surface-hover);
}

.col-num {
  width: 40px;
  text-align: center;
  color: var(--text-muted);
}

.col-duration {
  width: 80px;
  color: var(--text-muted);
}

.col-quality {
  width: 80px;
}

.quality-indicator {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--surface-darker);
}

.quality-indicator.hires {
  background: var(--accent);
  color: white;
}

/* Breadcrumb Navigation */
.breadcrumbs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}

.breadcrumb-sep {
  color: var(--text-muted);
}

.breadcrumb-link {
  color: var(--text-secondary);
  cursor: pointer;
}

.breadcrumb-link:hover {
  color: var(--accent);
  text-decoration: underline;
}

.breadcrumb-current {
  color: var(--text-primary);
  font-weight: 500;
}

/* In Library Badge */
.in-library-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: 600;
  background: var(--success);
  color: white;
  text-transform: uppercase;
}

.in-library-badge.large {
  position: static;
  display: inline-block;
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
}

.in-library-notice {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

/* Sort Options */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.sort-options {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.sort-options label {
  color: var(--text-muted);
}

.sort-options select {
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.85rem;
}

/* Album Extra Meta (Genre, Label) */
.album-extra-meta {
  display: flex;
  gap: 0.5rem;
  margin: 0.5rem 0;
}

.genre-tag,
.label-tag {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  background: var(--surface-darker);
  color: var(--text-secondary);
}

/* Disc Sections (Multi-disc albums) */
.disc-section {
  margin-bottom: 2rem;
}

.disc-header {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
}

/* Album Card Actions */
.album-card .album-actions {
  padding: 0.5rem;
  display: flex;
  justify-content: center;
}

.btn-sm {
  padding: 0.35rem 0.75rem;
  font-size: 0.8rem;
}

/* Responsive */
@media (max-width: 768px) {
  .page-qobuz-artist .artist-header,
  .page-qobuz-album .album-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .artist-details .album-meta,
  .album-details .album-meta {
    justify-content: center;
    flex-wrap: wrap;
  }

  .qobuz-results-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  }

  .breadcrumbs {
    flex-wrap: wrap;
    font-size: 0.8rem;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }
}
```

### Step 7.2: Import Styles

Add to `frontend/src/main.jsx` or `frontend/src/App.jsx`:

```jsx
import './styles/qobuz.css'
```

### Phase 7 Success Criteria

- [ ] Album cards show artwork properly sized
- [ ] Quality badges visible on hi-res content
- [ ] Artist/album pages have proper layout
- [ ] Responsive design works on mobile
- [ ] Hover states on interactive elements

---

## Phase 8: Testing and Polish

**Goal:** Ensure everything works end-to-end.

### Step 8.1: Test User Flow

Test the complete flow:

1. [ ] Search for an artist (e.g., "Pink Floyd")
2. [ ] See artist results with images
3. [ ] Click artist to see discography
4. [ ] All albums show with artwork and quality badges
5. [ ] Click album to see track listing
6. [ ] Download button starts download
7. [ ] Download completes and appears in library

### Step 8.2: Error Handling

Test error cases:

1. [ ] Search with no results shows appropriate message
2. [ ] Invalid artist ID shows error page
3. [ ] Invalid album ID shows error page
4. [ ] Network timeout shows retry option
5. [ ] Invalid credentials shows settings prompt

### Step 8.3: Performance

Check performance:

1. [ ] Search results load within 2 seconds
2. [ ] Artist page loads within 2 seconds
3. [ ] Album page loads within 2 seconds
4. [ ] Images lazy-load properly
5. [ ] No memory leaks on navigation

### Step 8.4: Update Changelog

Add entry to `changelog.md`:

```markdown
## [0.1.X] - 2026-01-XX

### Added
- Qobuz catalog browsing with album artwork
- Artist discography pages
- Album detail pages with track listings
- Quality badges showing hi-res availability
```

---

## Summary

| Phase | Description | New Files | Modified Files |
|-------|-------------|-----------|----------------|
| 1 | Backend API Client (with rate limiting, caching) | 1 | 1 (requirements.txt) |
| 2 | Backend API Routes (with auth, library check) | 1 | 2 |
| 3 | Frontend API Service | 0 | 1 |
| 4 | Update Search Page (with in_library badge) | 0 | 1 |
| 5 | Artist Page (with sort, breadcrumbs) | 1 | 1 |
| 6 | Album Page (with multi-disc, genre/label) | 1 | 1 |
| 7 | Styles (all new elements) | 1 | 1 |
| 8 | Testing | 1 | 1 |

**Total: 6 new files, 9 modified files**

### Key Features Added in Audit
- Rate limiting (50 req/min)
- Response caching (5 min TTL)
- "Already in Library" badges
- Multi-disc album handling
- Sort options (year/title)
- Breadcrumb navigation
- Image error fallbacks
- Genre and label display
- User authentication on endpoints

Each phase builds on the previous. Complete Phase 1 before starting Phase 2, etc.

---

## Appendix: Placeholder Images

Create simple SVG placeholders for missing images:

**`frontend/public/placeholder-album.svg`:**
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <rect fill="#2a2a2a" width="200" height="200"/>
  <circle fill="#3a3a3a" cx="100" cy="100" r="60"/>
  <circle fill="#2a2a2a" cx="100" cy="100" r="20"/>
</svg>
```

**`frontend/public/placeholder-artist.svg`:**
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <rect fill="#2a2a2a" width="200" height="200"/>
  <circle fill="#3a3a3a" cx="100" cy="80" r="40"/>
  <ellipse fill="#3a3a3a" cx="100" cy="170" rx="60" ry="40"/>
</svg>
```
