"""Qobuz catalog browsing API endpoints.

Enables browsing Qobuz catalog with full artwork URLs before downloading.
Downloads still use streamrip via the /downloads endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.integrations.qobuz_api import get_qobuz_api, QobuzAPIError
from app.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.album import Album
from app.utils.normalize import normalize_text


router = APIRouter(prefix="/qobuz", tags=["qobuz"])


# Response schemas
class AlbumResult(BaseModel):
    """Qobuz album search result."""
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
    hires_streamable: bool = False
    maximum_bit_depth: int
    maximum_sampling_rate: float
    artwork_small: str
    artwork_thumbnail: str
    artwork_large: str
    artwork_url: str
    url: str
    # Popularity and explicit
    popularity: int = 0
    explicit: bool = False
    # Library status
    in_library: bool = False
    local_album_id: Optional[int] = None


class ArtistResult(BaseModel):
    """Qobuz artist search result."""
    id: str
    name: str
    biography: str = ""
    album_count: int
    image_small: str
    image_medium: str
    image_large: str
    image_url: str


class TrackResult(BaseModel):
    """Qobuz track search result."""
    id: str
    title: str
    track_number: int
    disc_number: int = 1
    duration: int
    album_id: str
    album_title: str
    album_artwork: str = ""
    artist_name: str
    hires: bool
    maximum_bit_depth: int
    maximum_sampling_rate: float
    preview_url: str = ""


class SearchResponse(BaseModel):
    """Qobuz search response."""
    query: str
    type: str
    count: int
    albums: List[AlbumResult] = []
    artists: List[ArtistResult] = []
    tracks: List[TrackResult] = []


class ArtistDetailResponse(ArtistResult):
    """Qobuz artist detail with discography."""
    albums: List[AlbumResult] = []


class AlbumDetailResponse(AlbumResult):
    """Qobuz album detail with track listing."""
    tracks: List[TrackResult] = []


def check_albums_in_library(db: Session, albums: List[dict]) -> List[dict]:
    """Check which Qobuz albums exist in local library.

    Matches by normalized artist + album title.
    """
    for album in albums:
        # Normalize for comparison
        artist_norm = normalize_text(album["artist_name"])
        title_norm = normalize_text(album["title"])

        # Check if exists locally (using has() for relationship filter)
        local = db.query(Album).filter(
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
    user: User = Depends(get_current_user),
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
                albums=[AlbumResult(**item) for item in items],
            )
        elif type == "artist":
            items = await api.search_artists(q, limit)
            return SearchResponse(
                query=q,
                type=type,
                count=len(items),
                artists=[ArtistResult(**item) for item in items],
            )
        elif type == "track":
            items = await api.search_tracks(q, limit)
            return SearchResponse(
                query=q,
                type=type,
                count=len(items),
                tracks=[TrackResult(**item) for item in items],
            )
    except QobuzAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/artist/{artist_id}", response_model=ArtistDetailResponse)
async def get_qobuz_artist(
    artist_id: str,
    sort: str = Query("year", pattern="^(year|title|popularity)$"),
    explicit_only: bool = Query(False, description="Show only explicit albums"),
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

            # Filter explicit only
            if explicit_only:
                artist["albums"] = [a for a in artist["albums"] if a.get("explicit", False)]

            # Sort albums
            if sort == "year":
                artist["albums"].sort(key=lambda a: a.get("year", ""), reverse=True)
            elif sort == "title":
                artist["albums"].sort(key=lambda a: a.get("title", "").lower())
            elif sort == "popularity":
                artist["albums"].sort(key=lambda a: a.get("popularity", 0), reverse=True)

        return ArtistDetailResponse(
            id=artist["id"],
            name=artist["name"],
            biography=artist.get("biography", ""),
            album_count=artist.get("album_count", 0),
            image_small=artist.get("image_small", ""),
            image_medium=artist.get("image_medium", ""),
            image_large=artist.get("image_large", ""),
            image_url=artist.get("image_url", ""),
            albums=[AlbumResult(**a) for a in artist.get("albums", [])],
        )
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

        return AlbumDetailResponse(
            id=album["id"],
            title=album["title"],
            artist_id=album["artist_id"],
            artist_name=album["artist_name"],
            year=album.get("year", ""),
            track_count=album.get("track_count", 0),
            duration=album.get("duration", 0),
            label=album.get("label", ""),
            genre=album.get("genre", ""),
            hires=album.get("hires", False),
            hires_streamable=album.get("hires_streamable", False),
            maximum_bit_depth=album.get("maximum_bit_depth", 16),
            maximum_sampling_rate=album.get("maximum_sampling_rate", 44.1),
            artwork_small=album.get("artwork_small", ""),
            artwork_thumbnail=album.get("artwork_thumbnail", ""),
            artwork_large=album.get("artwork_large", ""),
            artwork_url=album.get("artwork_url", ""),
            url=album.get("url", ""),
            in_library=album.get("in_library", False),
            local_album_id=album.get("local_album_id"),
            tracks=[TrackResult(**t) for t in album.get("tracks", [])],
        )
    except QobuzAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
