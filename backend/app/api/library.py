"""Library browsing and user library endpoints."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
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
    user_lib = UserLibraryService(db)
    result = service.list_artists(letter, page, limit)
    hearted_artist_ids = user_lib.get_hearted_artist_ids(user.id)

    items = []
    for a in result["items"]:
        artist_data = ArtistResponse.model_validate(a)
        artist_data.is_hearted = a.id in hearted_artist_ids
        items.append(artist_data)

    return ArtistListResponse(
        items=items,
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
    user_lib = UserLibraryService(db)
    artist = service.get_artist(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")
    response = ArtistResponse.model_validate(artist)
    response.is_hearted = user_lib.is_artist_hearted(user.id, artist_id)
    return response


@router.delete("/artists/{artist_id}", response_model=MessageResponse)
def delete_artist(
    artist_id: int,
    delete_files: bool = Query(True, description="Also delete files from disk"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete artist and all their albums from library."""
    service = LibraryService(db)

    success, error = service.delete_artist(artist_id, delete_files)

    if not success:
        if error == "Artist not found":
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=500, detail=error)

    return MessageResponse(message="Artist deleted")


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
            artist_name=artist.name,
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
            artist_name=a.artist.name if a.artist else None,
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
    """Get album details with tracks."""
    service = LibraryService(db)
    user_lib = UserLibraryService(db)

    album = service.get_album(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    is_hearted = user_lib.is_album_hearted(user.id, album_id)

    # Get tracks for this album
    tracks = service.get_album_tracks(album_id)
    hearted_track_ids = user_lib.get_hearted_track_ids(user.id)

    track_list = [
        {
            "id": t.id,
            "title": t.title,
            "track_number": t.track_number,
            "disc_number": t.disc_number,
            "duration": t.duration,
            "path": t.path,
            "sample_rate": t.sample_rate,
            "bit_depth": t.bit_depth,
            "format": t.format,
            "is_lossy": t.is_lossy,
            "quality_display": t.quality_display,
            "is_hearted": t.id in hearted_track_ids,
        }
        for t in tracks
    ]

    return AlbumDetailResponse(
        id=album.id,
        artist_id=album.artist_id,
        artist_name=album.artist.name,
        title=album.title,
        year=album.year,
        path=album.path,
        artwork_path=album.artwork_path,
        total_tracks=album.total_tracks,
        available_tracks=album.available_tracks,
        source=album.source,
        is_hearted=is_hearted,
        artist={"id": album.artist.id, "name": album.artist.name},
        tracks=track_list,
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
    delete_files: bool = Query(True, description="Also delete files from disk"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete album from library."""
    service = LibraryService(db)

    success, error = service.delete_album(album_id, delete_files)

    if not success:
        if error == "Album not found":
            raise HTTPException(status_code=404, detail=error)
        raise HTTPException(status_code=500, detail=error)

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
    hearted_artist_ids = user_lib.get_hearted_artist_ids(user.id)

    artists_with_hearted = []
    for a in results["artists"]:
        artist_data = ArtistResponse.model_validate(a)
        artist_data.is_hearted = a.id in hearted_artist_ids
        artists_with_hearted.append(artist_data)

    return {
        "artists": artists_with_hearted,
        "albums": [
            AlbumResponse(
                id=a.id,
                artist_id=a.artist_id,
                artist_name=a.artist.name if a.artist else None,
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
            artist_name=a.artist.name if a.artist else None,
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


@router.get("/me/library/artists", response_model=ArtistListResponse)
def get_user_library_artists(
    letter: Optional[str] = Query(None, max_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get artists in current user's library (artists with hearted albums)."""
    service = UserLibraryService(db)
    result = service.get_library_artists(user.id, letter, page, limit)

    items = [
        ArtistResponse.model_validate(a)
        for a in result["items"]
    ]
    # Mark all as hearted
    for item in items:
        item.is_hearted = True

    return ArtistListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
    )


@router.get("/me/library/artists/{artist_id}/albums", response_model=List[AlbumResponse])
def get_user_library_artist_albums(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get user's library albums for a specific artist.

    Includes albums that are:
    - Hearted directly (is_hearted=True), OR
    - Contain at least one hearted track (is_hearted=False)
    """
    service = UserLibraryService(db)
    albums = service.get_library_artist_albums(user.id, artist_id)

    if not albums:
        raise HTTPException(status_code=404, detail="No albums found for this artist in your library")

    return [
        AlbumResponse(
            id=a.id,
            artist_id=a.artist_id,
            artist_name=a.artist.name if a.artist else None,
            title=a.title,
            year=a.year,
            path=a.path,
            artwork_path=a.artwork_path,
            total_tracks=a.total_tracks,
            available_tracks=a.available_tracks,
            source=a.source,
            is_hearted=a.is_hearted,  # Use actual value from service
        )
        for a in albums
    ]


@router.get("/me/library/tracks", response_model=List[TrackResponse])
def get_user_library_tracks(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current user's hearted tracks."""
    service = UserLibraryService(db)
    result = service.get_library_tracks(user.id, page, limit)

    return [
        TrackResponse.from_orm_with_quality(t, is_hearted=True, include_album=True)
        for t in result["items"]
    ]


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


@router.post("/me/library/artists/{artist_id}", response_model=MessageResponse)
def heart_artist(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Heart all albums by an artist (add to user library)."""
    service = UserLibraryService(db)
    try:
        count = service.heart_artist(user.id, artist_id, user.username)
        if count > 0:
            return MessageResponse(message=f"Added {count} album(s) to library")
        return MessageResponse(message="All albums already in library")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/me/library/artists/{artist_id}", response_model=MessageResponse)
def unheart_artist(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unheart all albums by an artist (remove from user library)."""
    service = UserLibraryService(db)
    try:
        count = service.unheart_artist(user.id, artist_id, user.username)
        if count > 0:
            return MessageResponse(message=f"Removed {count} album(s) from library")
        return MessageResponse(message="No albums in library")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
