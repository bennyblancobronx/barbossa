"""Metadata editing endpoints."""
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.album import Album
from app.models.track import Track
from app.models.artist import Artist
from app.integrations.exiftool import ExifToolClient
from app.utils.normalize import normalize_text


router = APIRouter(prefix="/metadata", tags=["metadata"])


class AlbumMetadataUpdate(BaseModel):
    """Album metadata update request."""
    title: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    label: Optional[str] = None


class TrackMetadataUpdate(BaseModel):
    """Track metadata update request."""
    title: Optional[str] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None


class ArtistMetadataUpdate(BaseModel):
    """Artist metadata update request."""
    name: Optional[str] = None


@router.put("/albums/{album_id}")
async def update_album_metadata(
    album_id: int,
    data: AlbumMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update album metadata.

    Updates database AND writes to file tags.
    """
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    exiftool = ExifToolClient()

    # Update database
    if data.title is not None:
        album.title = data.title
        album.normalized_title = normalize_text(data.title)
    if data.year is not None:
        album.year = data.year
    if data.genre is not None:
        album.genre = data.genre
    if data.label is not None:
        album.label = data.label

    # Update file tags for all tracks
    for track in album.tracks:
        track_path = Path(track.path)
        if track_path.exists():
            await exiftool.write_metadata(
                track_path,
                album=data.title or album.title,
                year=data.year or album.year
            )

    db.commit()
    return {"status": "updated"}


@router.put("/tracks/{track_id}")
async def update_track_metadata(
    track_id: int,
    data: TrackMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update track metadata."""
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    exiftool = ExifToolClient()

    # Update database
    if data.title is not None:
        track.title = data.title
        track.normalized_title = normalize_text(data.title)
    if data.track_number is not None:
        track.track_number = data.track_number
    if data.disc_number is not None:
        track.disc_number = data.disc_number

    # Update file tags
    track_path = Path(track.path)
    if track_path.exists():
        await exiftool.write_metadata(
            track_path,
            title=data.title,
            track_number=data.track_number
        )

    db.commit()
    return {"status": "updated"}


@router.put("/artists/{artist_id}")
async def update_artist_metadata(
    artist_id: int,
    data: ArtistMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update artist name.

    WARNING: This renames the artist folder and updates all album/track tags.
    """
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if not data.name:
        raise HTTPException(status_code=400, detail="Name required")

    old_name = artist.name
    new_name = data.name

    # Update database
    artist.name = new_name
    artist.normalized_name = normalize_text(new_name)

    # Rename folder if exists
    if artist.path:
        old_path = Path(artist.path)
        new_path = old_path.parent / new_name

        if old_path.exists():
            old_path.rename(new_path)
            artist.path = str(new_path)

            # Update all album paths
            for album in artist.albums:
                if album.path:
                    album.path = album.path.replace(str(old_path), str(new_path))
                    for track in album.tracks:
                        if track.path:
                            track.path = track.path.replace(str(old_path), str(new_path))

    # Update file tags
    exiftool = ExifToolClient()
    for album in artist.albums:
        for track in album.tracks:
            track_path = Path(track.path) if track.path else None
            if track_path and track_path.exists():
                await exiftool.write_metadata(
                    track_path,
                    artist=new_name
                )

    db.commit()
    return {"status": "updated", "old_name": old_name, "new_name": new_name}
