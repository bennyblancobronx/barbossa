# Barbossa Search Redesign - Technical Implementation Guide

**Last Updated:** 2026-01-25

## Overview

This document addresses four critical issues with the current search implementation:

1. **Search fallback to Qobuz missing** - Local search returns empty, no external fallback
2. **Streamrip GUI feature gaps** - Missing features compared to reference implementations
3. **Search bar placement** - Currently in header, needs to move to sidebar
4. **Search page UX** - Currently fragmented across pages, needs unified clean page

---

## 1. Issue Analysis: Search Not Falling Back to Qobuz

### Current Behavior

**Frontend** (`Library.jsx:16-24`):
```javascript
const { data: albums } = useQuery(
  ['albums', selectedLetter, searchQuery],
  () => {
    if (searchQuery) {
      // PROBLEM: Only searches local library, never falls back
      return api.searchLibrary(searchQuery, 'album').then(r => r.data.albums || [])
    }
    return api.getAlbums({ letter: selectedLetter }).then(r => r.data.items || [])
  }
)
```

**Backend** (`/api/search`):
- Endpoint exists and works: `GET /api/search?q=&type=`
- Only searches local PostgreSQL database
- Returns empty array when no matches

**Qobuz Search** (`/api/downloads/search/qobuz`):
- Separate endpoint on Downloads page only
- Never called from main search flow

### contracts.md Specification (Lines 91-94)
```
Search (Header Right)
- Search local library first
- If no local results, auto-fallback to Qobuz (streamrip)
- Force user to select search type: Artist / Track / Album
- Do NOT auto-search playlists from header search
```

### Root Cause
The frontend never implements the fallback logic. When `api.searchLibrary()` returns empty results, the code simply displays "no results" instead of cascading to Qobuz.

---

## 2. Streamrip GUI Feature Comparison

### Reference Implementations Analyzed

| Project | URL | Key Insight |
|---------|-----|-------------|
| streamrip-web-gui | github.com/AnOddName/streamrip-web-gui | Tab-based: Home, Search, Active DL, History, Files, Config |
| streamrip-gui v4 | github.com/trick23/streamrip-gui | URL-first, Recent History panel, Dark theme |
| ripstream | github.com/tomkoid/ripstream | Rust GUI, early stage |

### Feature Gap Analysis

| Feature | Streamrip GUIs | Barbossa Current | Priority |
|---------|---------------|------------------|----------|
| Unified search across sources | Yes | No (separate pages) | HIGH |
| Search type selector (Album/Track/Artist) | Prominent tabs | Hidden in Downloads | HIGH |
| "No results" -> external search prompt | Automatic | Missing | HIGH |
| Download history view | Dedicated tab | None | MEDIUM |
| Active downloads panel | Dedicated tab | Mixed with search | MEDIUM |
| URL paste field | Primary input | Buried in Downloads | MEDIUM |
| Quality selector per search | Dropdown always visible | Hidden in Settings | LOW |
| Drag-and-drop URLs | Yes | No | LOW |

### Features to Implement (Prioritized)

**Phase 1 - Critical**
1. Unified search with source fallback
2. Search type selector in main UI (NO playlist option per contracts.md)
3. "Not found locally" -> external search buttons

**Phase 2 - Important**
4. Separate download history view
5. Active downloads as sidebar section
6. Prominent URL paste field

**Phase 3 - Nice to Have**
7. Drag-and-drop URL support
8. Quality preselection dropdown

---

## 3. Search Bar Relocation Plan

### Current Layout
```
+------------------+----------------------------------------+
| SIDEBAR          | HEADER (search bar here)               |
|------------------|----------------------------------------|
| barbossa         | [Search input........................]  |
| - Master Library |----------------------------------------|
| - My Library     | PAGE CONTENT                           |
| - Downloads      |                                        |
| - Settings       |                                        |
+------------------+----------------------------------------+
```

### Target Layout
```
+------------------+----------------------------------------+
| SIDEBAR          | HEADER (breadcrumbs only)              |
|------------------|----------------------------------------|
| barbossa         |                                        |
|                  |----------------------------------------|
| [Search........] | PAGE CONTENT                           |
| [Type: Album v]  |                                        |
|                  | When searching:                        |
| - Master Library | - Local results (if any)               |
| - My Library     | - "Not in library" prompt              |
| - Downloads      |   [Qobuz] [Lidarr] [YouTube] [URL]     |
| - Settings       |                                        |
|------------------|                                        |
| User / Theme     |                                        |
+------------------+----------------------------------------+
```

### Component Changes Required

| Component | Current | Change |
|-----------|---------|--------|
| `Header.jsx` | Contains SearchBar | Remove SearchBar, keep breadcrumbs only |
| `Sidebar.jsx` | Navigation only | Add SearchBar + type selector above nav |
| `SearchBar.jsx` | Basic input | No change needed (reused) |
| `Layout.jsx` | Renders Header with search | No change needed |

### Mobile Considerations

On screens < 768px:
- Sidebar collapses to hamburger menu
- Search moves to top of main content area
- Type selector becomes inline with search input

---

## 4. Unified Search Page Design

### New Search Flow

```
User types in sidebar search (Enter to submit)
        |
        v
Navigate to /search?q=X&type=album
        |
        v
Frontend calls: GET /api/search/unified?q=X&type=album
        |
        v
Backend returns local results
        |
        +--- Results found? ---> Display in main content (AlbumGrid/ArtistList/TrackList)
        |
        v (No results)
Frontend shows source selection card:
+---------------------------------------------+
|  "Album Name" not found in library          |
|                                             |
|  Search externally:                         |
|  [Search Qobuz]     24/192 max              |
|  [Request Lidarr]   automated               |
|  [Search YouTube]   lossy warning           |
|  [Paste URL]        Bandcamp, etc           |
+---------------------------------------------+
        |
        v (User clicks "Search Qobuz")
Frontend calls: GET /api/downloads/search/qobuz?q=X&type=album
        |
        v
Display Qobuz results with Download buttons
```

### New Route Structure

| Route | Page | Description |
|-------|------|-------------|
| `/` | Library | Browse master library (no active search) |
| `/search?q=X&type=Y` | Search | Unified search results page |
| `/my-library` | UserLibrary | User's hearted albums |
| `/downloads` | Downloads | Active queue + history only |
| `/settings` | Settings | Configuration |

### Search Results Page States

**State 1: No Query**
```
Enter a search term in the sidebar
```

**State 2: Loading**
```
Searching library...
```

**State 3: Local results found**
```
Results for "Beatles" (12 albums in library)
[Album grid with artwork, heart, source badges]
```

**State 4: No local results**
```
"Beatles" not found in your library

Search externally:
[Search Qobuz]      High quality (24/192)
[Request Lidarr]    Automated monitoring
[Search YouTube]    Lossy source
[Paste URL]         Bandcamp, Soundcloud, etc
```

**State 5: External results displayed**
```
"Beatles" - Qobuz Results
+------------------------------------------+
| [Artwork] Abbey Road - The Beatles       |
|           1969 | 24-bit/96kHz            |
|                            [Download]    |
+------------------------------------------+
| [Artwork] Let It Be - The Beatles        |
|           1970 | 16-bit/44.1kHz          |
|                            [Download]    |
+------------------------------------------+
```

**State 6: Error**
```
Search failed. Please try again.
[Retry]
```

---

## 5. Implementation Plan

### Phase 1: Backend Changes

#### 5.1.1 New Unified Search Endpoint

**File:** `backend/app/api/search.py` (new)

```python
from fastapi import APIRouter, Query, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Any
import logging

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services.library import LibraryService
from app.services.download import DownloadService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


# ---- Response Schemas ----

class LocalResults(BaseModel):
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


# ---- Endpoints ----

@router.get("/search/unified", response_model=UnifiedSearchResponse)
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

    # Build response
    albums = local_results.get("albums", [])
    artists = local_results.get("artists", [])
    tracks = local_results.get("tracks", [])

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
                count=len(qobuz_results),
                items=qobuz_results
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
```

#### 5.1.2 Register New Router

**File:** `backend/app/api/__init__.py`

Add to exports:
```python
from app.api.search import router as search_router
```

**File:** `backend/app/main.py`

Add in `create_app()`:
```python
from app.api import search_router

# After other router includes:
app.include_router(search_router)
```

#### 5.1.3 Add Tests

**File:** `backend/tests/test_search_unified.py` (new)

```python
import pytest
from fastapi.testclient import TestClient


class TestUnifiedSearch:
    """Tests for /api/search/unified endpoint."""

    def test_search_requires_auth(self, client: TestClient):
        """Unauthenticated requests should fail."""
        response = client.get("/api/search/unified?q=test")
        assert response.status_code == 401

    def test_search_requires_query(self, client: TestClient, auth_headers):
        """Query parameter is required."""
        response = client.get("/api/search/unified", headers=auth_headers)
        assert response.status_code == 422

    def test_search_rejects_playlist_type(self, client: TestClient, auth_headers):
        """Playlist type should be rejected per contracts.md."""
        response = client.get(
            "/api/search/unified?q=test&type=playlist",
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_search_local_only(self, client: TestClient, auth_headers, test_album):
        """Search returns local results without external flag."""
        response = client.get(
            f"/api/search/unified?q={test_album.title}&type=album",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == test_album.title
        assert data["type"] == "album"
        assert data["local"]["count"] >= 1
        assert data["external"] is None

    def test_search_external_when_empty(
        self, client: TestClient, auth_headers, mocker
    ):
        """External search triggered when local empty and flag set."""
        # Mock Qobuz search
        mock_qobuz = mocker.patch(
            "app.services.download.DownloadService.search_qobuz",
            return_value=[{"id": "123", "title": "Test Album"}]
        )

        response = client.get(
            "/api/search/unified?q=nonexistent&type=album&include_external=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["local"]["count"] == 0
        assert data["external"] is not None
        assert data["external"]["source"] == "qobuz"
        mock_qobuz.assert_called_once()

    def test_search_no_external_when_local_found(
        self, client: TestClient, auth_headers, test_album, mocker
    ):
        """External search NOT triggered when local results exist."""
        mock_qobuz = mocker.patch(
            "app.services.download.DownloadService.search_qobuz"
        )

        response = client.get(
            f"/api/search/unified?q={test_album.title}&type=album&include_external=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["local"]["count"] >= 1
        assert data["external"] is None
        mock_qobuz.assert_not_called()
```

### Phase 2: Frontend Changes

#### 5.2.1 Move Search to Sidebar

**File:** `frontend/src/components/Sidebar.jsx`

```jsx
import { useState } from 'react'
import { NavLink, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

export default function Sidebar() {
  const { user, logout } = useAuthStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  // Initialize from URL if on search page
  const [searchQuery, setSearchQuery] = useState(searchParams.get('q') || '')
  const [searchType, setSearchType] = useState(searchParams.get('type') || 'album')

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}&type=${searchType}`)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setSearchQuery('')
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1 className="text-2xl">barbossa</h1>
      </div>

      {/* Search Section */}
      <div className="sidebar-search">
        <form onSubmit={handleSearch}>
          <div className="search-bar">
            <SearchIcon />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Search... (Enter)"
              className="search-input"
              aria-label="Search library"
            />
            {searchQuery && (
              <button
                type="button"
                className="search-clear"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search"
              >
                <CloseIcon />
              </button>
            )}
          </div>
          {/* NO playlist option per contracts.md line 94 */}
          <select
            value={searchType}
            onChange={e => setSearchType(e.target.value)}
            className="search-type-select"
            aria-label="Search type"
          >
            <option value="album">Albums</option>
            <option value="artist">Artists</option>
            <option value="track">Tracks</option>
          </select>
        </form>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Master Library
        </NavLink>

        <NavLink to="/my-library" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          My Library
        </NavLink>

        <NavLink to="/downloads" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Downloads
        </NavLink>

        <NavLink to="/settings" className={({ isActive }) =>
          `nav-link ${isActive ? 'is-active' : ''}`
        }>
          Settings
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-footer-row">
          <span className="text-muted text-sm">{user?.username}</span>
          <button onClick={logout} className="btn-ghost text-sm">
            Logout
          </button>
        </div>
        <button onClick={toggleTheme} className="theme-toggle">
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
          <span className="text-sm">{theme === 'dark' ? 'Light' : 'Dark'} Mode</span>
        </button>
      </div>
    </aside>
  )
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" fill="none" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" fill="none" strokeWidth="2">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  )
}
```

#### 5.2.2 Simplify Header

**File:** `frontend/src/components/Header.jsx`

```jsx
import { useLocation } from 'react-router-dom'

const pageTitles = {
  '/': 'Master Library',
  '/search': 'Search',
  '/my-library': 'My Library',
  '/downloads': 'Downloads',
  '/settings': 'Settings'
}

export default function Header() {
  const location = useLocation()
  const basePath = '/' + (location.pathname.split('/')[1] || '')
  const title = pageTitles[basePath] || 'Barbossa'

  return (
    <header className="app-header">
      <div className="header-left">
        <h2 className="header-title">{title}</h2>
      </div>
      <div className="header-right">
        {/* Empty - search moved to sidebar */}
      </div>
    </header>
  )
}
```

#### 5.2.3 New Unified Search Page

**File:** `frontend/src/pages/Search.jsx` (new)

```jsx
import { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import AlbumGrid from '../components/AlbumGrid'
import AlbumModal from '../components/AlbumModal'
import { useNotificationStore } from '../stores/notifications'

export default function Search() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const query = searchParams.get('q') || ''
  const type = searchParams.get('type') || 'album'

  const [selectedAlbum, setSelectedAlbum] = useState(null)
  const [showExternal, setShowExternal] = useState(false)
  const [externalSource, setExternalSource] = useState(null)

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  // Reset external state when query/type changes
  useEffect(() => {
    setShowExternal(false)
    setExternalSource(null)
  }, [query, type])

  // Local search
  const {
    data: localResults,
    isLoading: localLoading,
    error: localError,
    refetch: retryLocal
  } = useQuery(
    ['search-local', query, type],
    () => api.searchLibrary(query, type).then(r => r.data),
    {
      enabled: !!query,
      retry: 1
    }
  )

  // External search (Qobuz) - only when triggered
  const {
    data: qobuzResults,
    isLoading: qobuzLoading,
    refetch: searchQobuz
  } = useQuery(
    ['search-qobuz', query, type],
    () => api.searchQobuz(query, type).then(r => r.data.items || []),
    { enabled: false }
  )

  // Download mutation
  const downloadMutation = useMutation(
    ({ url, source }) => {
      if (source === 'qobuz') {
        return api.downloadQobuz(url, 4, type)
      }
      return api.downloadUrl(url, false, type)
    },
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Download started' })
        queryClient.invalidateQueries('downloads')
      },
      onError: (error) => {
        const message = error.response?.data?.detail || 'Download failed'
        // Handle lossy warning
        if (message.includes('lossy')) {
          addNotification({
            type: 'warning',
            message: 'This is a lossy source. Go to Downloads page to confirm.'
          })
          navigate('/downloads')
        } else {
          addNotification({ type: 'error', message })
        }
      }
    }
  )

  const hasLocalResults = localResults && (
    (localResults.albums?.length > 0) ||
    (localResults.artists?.length > 0) ||
    (localResults.tracks?.length > 0)
  )

  const handleSearchExternal = (source) => {
    setShowExternal(true)
    setExternalSource(source)
    if (source === 'qobuz') {
      searchQobuz()
    }
  }

  // No query state
  if (!query) {
    return (
      <div className="page-search">
        <div className="empty-state">
          <p className="text-muted">Enter a search term in the sidebar</p>
          <p className="text-sm text-muted">Press Enter to search</p>
        </div>
      </div>
    )
  }

  // Error state
  if (localError) {
    return (
      <div className="page-search">
        <div className="error-state">
          <p className="text-error">Search failed</p>
          <button className="btn-primary" onClick={() => retryLocal()}>
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page-search">
      <header className="page-header">
        <h1 className="text-2xl">Search Results</h1>
        <span className="text-muted">for "{query}" ({type}s)</span>
      </header>

      {/* Loading State */}
      {localLoading && (
        <div className="loading-state">
          <div className="spinner" />
          <p>Searching library...</p>
        </div>
      )}

      {/* Local Results */}
      {!localLoading && hasLocalResults && (
        <section className="search-section">
          <h2 className="section-title">In Your Library</h2>
          {type === 'album' && localResults.albums?.length > 0 && (
            <AlbumGrid
              albums={localResults.albums}
              onAlbumClick={setSelectedAlbum}
            />
          )}
          {type === 'artist' && localResults.artists?.length > 0 && (
            <div className="artist-list">
              {localResults.artists.map(artist => (
                <div
                  key={artist.id}
                  className="artist-item"
                  onClick={() => navigate(`/artist/${artist.id}`)}
                >
                  <span className="artist-name">{artist.name}</span>
                  <span className="text-muted">{artist.album_count} albums</span>
                </div>
              ))}
            </div>
          )}
          {type === 'track' && localResults.tracks?.length > 0 && (
            <div className="track-list">
              {localResults.tracks.map(track => (
                <div key={track.id} className="track-item">
                  <span className="track-title">{track.title}</span>
                  <span className="track-artist text-muted">{track.artist_name}</span>
                  <span className="track-album text-muted">{track.album_title}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* No Local Results - Show External Options */}
      {!localLoading && !hasLocalResults && !showExternal && (
        <section className="search-not-found">
          <div className="not-found-card">
            <p className="text-lg">"{query}" not found in your library</p>
            <p className="text-muted">Search externally:</p>

            <div className="external-options">
              <button
                className="btn-primary external-option"
                onClick={() => handleSearchExternal('qobuz')}
              >
                <span>Search Qobuz</span>
                <span className="text-sm text-muted">24/192 max</span>
              </button>

              <button
                className="btn-secondary external-option"
                onClick={() => navigate('/downloads')}
              >
                <span>Request via Lidarr</span>
                <span className="text-sm text-muted">automated</span>
              </button>

              <button
                className="btn-secondary external-option"
                onClick={() => handleSearchExternal('youtube')}
              >
                <span>Search YouTube</span>
                <span className="text-sm text-warning">lossy source</span>
              </button>

              <button
                className="btn-ghost external-option"
                onClick={() => navigate('/downloads')}
              >
                <span>Paste URL</span>
                <span className="text-sm text-muted">Bandcamp, Soundcloud, etc</span>
              </button>
            </div>
          </div>
        </section>
      )}

      {/* External Results (Qobuz) */}
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

          {!qobuzLoading && qobuzResults && qobuzResults.length > 0 && (
            <div className="external-results">
              {qobuzResults.map(result => (
                <div key={result.id} className="external-result-item">
                  {result.artwork_url && (
                    <img
                      src={result.artwork_url}
                      alt=""
                      className="external-result-artwork"
                    />
                  )}
                  <div className="external-result-info">
                    <span className="external-result-title">{result.title}</span>
                    <span className="external-result-artist">
                      {result.artist || result.artist_name}
                    </span>
                    <div className="external-result-meta">
                      {result.year && (
                        <span className="external-result-year">{result.year}</span>
                      )}
                      {result.quality && (
                        <span className="external-result-quality badge">
                          {result.quality}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    className="btn-primary"
                    onClick={() => downloadMutation.mutate({
                      url: result.url,
                      source: 'qobuz'
                    })}
                    disabled={downloadMutation.isLoading}
                  >
                    {downloadMutation.isLoading ? 'Starting...' : 'Download'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {!qobuzLoading && (!qobuzResults || qobuzResults.length === 0) && (
            <div className="empty-state">
              <p className="text-muted">No results found on Qobuz</p>
              <button
                className="btn-ghost"
                onClick={() => setShowExternal(false)}
              >
                Try other sources
              </button>
            </div>
          )}
        </section>
      )}

      {/* YouTube redirect notice */}
      {showExternal && externalSource === 'youtube' && (
        <section className="search-section">
          <div className="lossy-warning-card">
            <p className="text-warning">YouTube downloads are lossy (~256kbps max)</p>
            <p className="text-muted">
              Use only for content unavailable on Qobuz or Lidarr.
            </p>
            <button
              className="btn-primary"
              onClick={() => {
                navigate(`/downloads?url=https://music.youtube.com/search?q=${encodeURIComponent(query)}`)
              }}
            >
              Continue to Downloads
            </button>
            <button
              className="btn-ghost"
              onClick={() => setShowExternal(false)}
            >
              Back
            </button>
          </div>
        </section>
      )}

      {selectedAlbum && (
        <AlbumModal
          album={selectedAlbum}
          onClose={() => setSelectedAlbum(null)}
        />
      )}
    </div>
  )
}
```

#### 5.2.4 Update App Routes

**File:** `frontend/src/App.jsx`

Add the search route:
```jsx
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from 'react-query'
import Layout from './components/Layout'
import Library from './pages/Library'
import UserLibrary from './pages/UserLibrary'
import Downloads from './pages/Downloads'
import Settings from './pages/Settings'
import Search from './pages/Search'
import Login from './pages/Login'
import { useAuthStore } from './stores/auth'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1
    }
  }
})

function PrivateRoute() {
  const token = useAuthStore(state => state.token)
  return token ? <Outlet /> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<PrivateRoute />}>
            <Route element={<Layout />}>
              <Route index element={<Library />} />
              <Route path="search" element={<Search />} />
              <Route path="my-library" element={<UserLibrary />} />
              <Route path="downloads" element={<Downloads />} />
              <Route path="settings" element={<Settings />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

#### 5.2.5 Update API Service

**File:** `frontend/src/services/api.js`

Verify these exports exist (they already do per current codebase):

```javascript
// Search - these already exist
export const searchLibrary = (query, type = 'all') =>
  api.get('/search', { params: { q: query, type } })

export const searchQobuz = (q, type, limit = 20) =>
  api.get('/downloads/search/qobuz', { params: { q, type, limit } })

export const searchLidarr = (q) =>
  api.get('/lidarr/search', { params: { q } })

// Add unified search endpoint
export const searchUnified = (q, type, includeExternal = false, limit = 20) =>
  api.get('/search/unified', {
    params: { q, type, include_external: includeExternal, limit }
  })
```

### Phase 3: Styling Updates

#### 5.3.1 Sidebar Search Styles

**File:** `frontend/src/styles/design-system.css`

Add after `.sidebar-brand`:

```css
/* ---- Sidebar Search ---- */
.sidebar-search {
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.sidebar-search form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sidebar-search .search-bar {
  position: relative;
  display: flex;
  align-items: center;
}

.sidebar-search .search-input {
  width: 100%;
  padding-left: 36px;
  padding-right: 32px;
}

.sidebar-search .search-bar > svg:first-child {
  position: absolute;
  left: var(--space-3);
  color: var(--color-text-muted);
  pointer-events: none;
}

.sidebar-search .search-clear {
  position: absolute;
  right: var(--space-2);
  padding: var(--space-1);
  background: none;
  border: none;
  color: var(--color-text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.sidebar-search .search-clear:hover {
  color: var(--color-text);
  background: var(--color-surface-hover);
}

.search-type-select {
  width: 100%;
  height: 36px;
  padding: 0 var(--space-3);
  font-size: var(--text-sm);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  cursor: pointer;
}

.search-type-select:focus {
  outline: none;
  border-color: var(--color-primary);
}

/* Dark mode select */
[data-theme="dark"] .search-type-select {
  background: var(--color-surface);
  color: var(--color-text);
}

[data-theme="dark"] .search-type-select option {
  background: var(--color-surface-elevated);
  color: var(--color-text);
}

/* ---- Search Page ---- */
.page-search {
  padding: var(--space-6);
  max-width: 1200px;
}

.page-search .page-header {
  margin-bottom: var(--space-6);
}

.search-section {
  margin-bottom: var(--space-8);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 500;
  margin-bottom: var(--space-4);
}

.section-header .section-title {
  margin-bottom: 0;
}

/* Loading & Empty States */
.loading-state,
.empty-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
  gap: var(--space-4);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Not Found Card */
.search-not-found {
  display: flex;
  justify-content: center;
  padding: var(--space-8) 0;
}

.not-found-card {
  max-width: 400px;
  padding: var(--space-8);
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  text-align: center;
}

.not-found-card > p {
  margin-bottom: var(--space-4);
}

.external-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-6);
}

.external-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: var(--space-4);
  text-align: left;
}

.external-option .text-warning {
  color: var(--color-warning);
}

/* External Results */
.external-results {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.external-result-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.external-result-artwork {
  width: 64px;
  height: 64px;
  border-radius: var(--radius-sm);
  object-fit: cover;
  background: var(--color-surface-hover);
}

.external-result-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.external-result-title {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.external-result-artist {
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}

.external-result-meta {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.external-result-year {
  color: var(--color-text-muted);
}

.external-result-quality {
  font-size: var(--text-xs);
}

/* Lossy Warning */
.lossy-warning-card {
  max-width: 400px;
  margin: 0 auto;
  padding: var(--space-6);
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-lg);
  text-align: center;
}

.lossy-warning-card p {
  margin-bottom: var(--space-4);
}

.lossy-warning-card .btn-primary {
  margin-bottom: var(--space-2);
}

/* Artist/Track Lists */
.artist-list,
.track-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.artist-item,
.track-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.artist-item:hover,
.track-item:hover {
  background: var(--color-surface-hover);
}

.artist-name,
.track-title {
  font-weight: 500;
}

.track-artist,
.track-album {
  flex: 1;
}

/* Mobile: Move search to content area */
@media (max-width: 768px) {
  .sidebar-search {
    display: none;
  }

  .page-search {
    padding: var(--space-4);
  }

  .external-result-item {
    flex-wrap: wrap;
  }

  .external-result-artwork {
    width: 48px;
    height: 48px;
  }

  .external-result-item .btn-primary {
    width: 100%;
    margin-top: var(--space-2);
  }
}
```

---

## 6. Testing Checklist

### Backend Tests

- [ ] `GET /api/search/unified` requires authentication
- [ ] `GET /api/search/unified` requires `q` parameter
- [ ] `GET /api/search/unified?type=playlist` returns 422 (rejected)
- [ ] `GET /api/search/unified?q=X&type=album` returns local results
- [ ] `GET /api/search/unified?include_external=true` triggers Qobuz when local empty
- [ ] External search NOT triggered when local results exist
- [ ] Error handling when Qobuz API fails returns graceful error

### Frontend Tests

- [ ] Sidebar search input navigates to `/search?q=X&type=Y`
- [ ] Enter key submits search
- [ ] Escape key clears input
- [ ] Type selector excludes "playlist" option
- [ ] Search page displays local album results in grid
- [ ] Search page displays local artist results in list
- [ ] Search page displays local track results in list
- [ ] Search page shows "not found" card when local empty
- [ ] "Search Qobuz" button triggers external search
- [ ] "Search YouTube" button shows lossy warning
- [ ] Download button works from Qobuz results
- [ ] Download button shows loading state
- [ ] Back button returns to source options
- [ ] External state resets when query changes
- [ ] Error state shows retry button

### Integration Tests

- [ ] Full flow: search -> no local -> click Qobuz -> results -> download
- [ ] Download appears in queue after clicking Download
- [ ] Downloaded album appears in library after import
- [ ] Mobile layout: search accessible via hamburger menu

---

## 7. Cleanup Tasks

After implementation:

1. **Header.jsx** - Remove SearchBar import and state
2. **Library.jsx** - Remove `searchQuery` state and filtering (now browse-only)
3. **Downloads.jsx** - Keep only URL paste and queue (remove Qobuz search form)
4. **contracts.md** - Update line 90-94 to reflect sidebar search location
5. **techguide.md** - Update component diagram
6. **backend/api/openapi.yaml** - Add `/search/unified` endpoint spec

---

## 8. File Change Summary

| File | Action | Notes |
|------|--------|-------|
| `backend/app/api/search.py` | NEW | Unified search endpoint with Pydantic schemas |
| `backend/app/api/__init__.py` | MODIFY | Export search_router |
| `backend/app/main.py` | MODIFY | Include search router |
| `backend/tests/test_search_unified.py` | NEW | Endpoint tests |
| `frontend/src/components/Sidebar.jsx` | MODIFY | Add search input + type selector |
| `frontend/src/components/Header.jsx` | MODIFY | Remove search, add page title |
| `frontend/src/pages/Search.jsx` | NEW | Unified search page with all states |
| `frontend/src/pages/Library.jsx` | MODIFY | Remove search handling |
| `frontend/src/pages/Downloads.jsx` | MODIFY | Remove Qobuz search (keep URL paste) |
| `frontend/src/App.jsx` | MODIFY | Add /search route |
| `frontend/src/services/api.js` | MODIFY | Add searchUnified export |
| `frontend/src/styles/design-system.css` | MODIFY | Add search styles + dark mode |

---

## 9. contracts.md Update Required

After implementation, update contracts.md lines 90-94:

```markdown
### Search (Sidebar)
- Search input in sidebar (above navigation)
- Force user to select search type: Artist / Track / Album
- Do NOT include playlist option in sidebar search
- Search local library first
- If no local results, show external source options:
  - [Search Qobuz] - 24/192 max
  - [Request Lidarr] - automated
  - [Search YouTube] - lossy warning
  - [Paste URL] - redirect to Downloads
```

---

## References

- contracts.md lines 20-28: Downloads page search spec
- contracts.md lines 90-106: Search and source selection spec
- streamrip-web-gui: github.com/AnOddName/streamrip-web-gui
- streamrip-gui: github.com/trick23/streamrip-gui
