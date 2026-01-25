"""Library browsing and user library endpoints."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.services.library import LibraryService
from app.services.user_library import UserLibraryService
from app.schemas.artist import ArtistResponse, ArtistListResponse
from app.schemas.album import AlbumResponse, AlbumDetailResponse, AlbumListResponse
from app.schemas.track import TrackResponse
from app.schemas.common import MessageResponse
from app.models.user import User

router = APIRouter()


# ============================================================================
# Master Library - Artists
# ============================================================================

@router.get("/artists", response_model=ArtistListResponse)
def list_artists(
    letter: Optional[str] = Query(None, max_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all artists in the library."""
    service = LibraryService(db)
    result = service.list_artists(letter, page, limit)
    return ArtistListResponse(
        items=[ArtistResponse.model_validate(a) for a in result["items"]],
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
    )


@router.get("/artists/{artist_id}", response_model=ArtistResponse)
def get_artist(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single artist by ID."""
    service = LibraryService(db)
    artist = service.get_artist(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    return ArtistResponse.model_validate(artist)


@router.get("/artists/{artist_id}/albums", response_model=List[AlbumResponse])
def get_artist_albums(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all albums for an artist."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    # Check artist exists
    artist = service.get_artist(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    albums = service.get_artist_albums(artist_id)
    hearted_ids = user_lib.get_hearted_album_ids(user.id)

    return [
        AlbumResponse(
            id=a.id,
            artist_id=a.artist_id,
            title=a.title,
            year=a.year,
            path=a.path,
            artwork_path=a.artwork_path,
            total_tracks=a.total_tracks,
            available_tracks=a.available_tracks,
            source=a.source,
            is_hearted=a.id in hearted_ids,
        )
        for a in albums
    ]


# ============================================================================
# Master Library - Albums
# ============================================================================

@router.get("/albums", response_model=AlbumListResponse)
def list_albums(
    artist_id: Optional[int] = None,
    letter: Optional[str] = Query(None, max_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List albums with optional filters."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    result = service.list_albums(artist_id, letter, page, limit)
    hearted_ids = user_lib.get_hearted_album_ids(user.id)

    items = [
        AlbumResponse(
            id=a.id,
            artist_id=a.artist_id,
            title=a.title,
            year=a.year,
            path=a.path,
            artwork_path=a.artwork_path,
            total_tracks=a.total_tracks,
            available_tracks=a.available_tracks,
            source=a.source,
            is_hearted=a.id in hearted_ids,
        )
        for a in result["items"]
    ]

    return AlbumListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
    )


@router.get("/albums/{album_id}", response_model=AlbumDetailResponse)
def get_album(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get album details."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    album = service.get_album(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    is_hearted = user_lib.is_album_hearted(user.id, album_id)

    return AlbumDetailResponse(
        id=album.id,
        artist_id=album.artist_id,
        title=album.title,
        year=album.year,
        path=album.path,
        artwork_path=album.artwork_path,
        total_tracks=album.total_tracks,
        available_tracks=album.available_tracks,
        source=album.source,
        is_hearted=is_hearted,
        artist={"id": album.artist.id, "name": album.artist.name},
        disc_count=album.disc_count,
        genre=album.genre,
        label=album.label,
        musicbrainz_id=album.musicbrainz_id,
        created_at=album.created_at,
    )


@router.get("/albums/{album_id}/tracks", response_model=List[TrackResponse])
def get_album_tracks(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get all tracks for an album."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    album = service.get_album(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    tracks = service.get_album_tracks(album_id)
    hearted_ids = user_lib.get_hearted_track_ids(user.id)

    return [
        TrackResponse.from_orm_with_quality(t, t.id in hearted_ids)
        for t in tracks
    ]


@router.delete("/albums/{album_id}", response_model=MessageResponse)
def delete_album(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Delete album from library (admin only)."""
    service = LibraryService(db)

    if not service.delete_album(album_id):
        raise HTTPException(status_code=404, detail="Album not found")

    return MessageResponse(message="Album deleted")


# ============================================================================
# Search
# ============================================================================

@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    type: str = Query("all", pattern="^(all|artist|album|track)$"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Search the library."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    results = service.search(q, type, limit)
    hearted_album_ids = user_lib.get_hearted_album_ids(user.id)
    hearted_track_ids = user_lib.get_hearted_track_ids(user.id)

    return {
        "artists": [ArtistResponse.model_validate(a) for a in results["artists"]],
        "albums": [
            AlbumResponse(
                id=a.id,
                artist_id=a.artist_id,
                title=a.title,
                year=a.year,
                path=a.path,
                artwork_path=a.artwork_path,
                total_tracks=a.total_tracks,
                available_tracks=a.available_tracks,
                source=a.source,
                is_hearted=a.id in hearted_album_ids,
            )
            for a in results["albums"]
        ],
        "tracks": [
            TrackResponse.from_orm_with_quality(t, t.id in hearted_track_ids)
            for t in results["tracks"]
        ],
    }


# ============================================================================
# User Library
# ============================================================================

@router.get("/me/library", response_model=AlbumListResponse)
def get_user_library(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's hearted albums."""
    service = UserLibraryService(db)
    result = service.get_library(user.id, page, limit)

    items = [
        AlbumResponse(
            id=a.id,
            artist_id=a.artist_id,
            title=a.title,
            year=a.year,
            path=a.path,
            artwork_path=a.artwork_path,
            total_tracks=a.total_tracks,
            available_tracks=a.available_tracks,
            source=a.source,
            is_hearted=True,
        )
        for a in result["items"]
    ]

    return AlbumListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
    )


@router.post("/me/library/albums/{album_id}", response_model=MessageResponse)
def heart_album(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Heart an album (add to user library)."""
    service = UserLibraryService(db)
    try:
        if service.heart_album(user.id, album_id, user.username):
            return MessageResponse(message="Album added to library")
        return MessageResponse(message="Album already in library")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/me/library/albums/{album_id}", response_model=MessageResponse)
def unheart_album(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unheart an album (remove from user library)."""
    service = UserLibraryService(db)
    if service.unheart_album(user.id, album_id, user.username):
        return MessageResponse(message="Album removed from library")
    return MessageResponse(message="Album not in library")


@router.post("/me/library/tracks/{track_id}", response_model=MessageResponse)
def heart_track(
    track_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Heart a track (add to user library)."""
    service = UserLibraryService(db)
    try:
        if service.heart_track(user.id, track_id, user.username):
            return MessageResponse(message="Track added to library")
        return MessageResponse(message="Track already in library")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/me/library/tracks/{track_id}", response_model=MessageResponse)
def unheart_track(
    track_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unheart a track (remove from user library)."""
    service = UserLibraryService(db)
    if service.unheart_track(user.id, track_id, user.username):
        return MessageResponse(message="Track removed from library")
    return MessageResponse(message="Track not in library")
