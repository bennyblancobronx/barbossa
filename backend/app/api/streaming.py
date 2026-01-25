"""Streaming endpoints for audio preview and artwork."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.services.library import LibraryService
from app.models.user import User

router = APIRouter()


@router.get("/tracks/{track_id}/stream")
def stream_track(
    track_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream a track for preview playback."""
    service = LibraryService(db)
    track = service.get_track(track_id)

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.path:
        raise HTTPException(status_code=404, detail="Track file not found")

    file_path = Path(track.path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Track file not found")

    # Determine content type
    suffix = file_path.suffix.lower()
    content_types = {
        ".flac": "audio/flac",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
    }
    content_type = content_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=content_type,
        filename=file_path.name,
    )


@router.get("/albums/{album_id}/artwork")
def get_album_artwork(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get album cover artwork."""
    service = LibraryService(db)
    album = service.get_album(album_id)

    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Try artwork_path first
    if album.artwork_path:
        artwork_path = Path(album.artwork_path)
        if artwork_path.exists():
            return FileResponse(
                path=artwork_path,
                media_type="image/jpeg",
            )

    # Try common artwork filenames in album folder
    if album.path:
        album_path = Path(album.path)
        for name in ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "artwork.jpg", "artwork.png"]:
            artwork_path = album_path / name
            if artwork_path.exists():
                content_type = "image/png" if name.endswith(".png") else "image/jpeg"
                return FileResponse(
                    path=artwork_path,
                    media_type=content_type,
                )

    raise HTTPException(status_code=404, detail="Artwork not found")
