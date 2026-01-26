"""Artwork upload and management."""
import shutil
from pathlib import Path
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.album import Album
from app.models.artist import Artist
from app.config import settings


router = APIRouter(tags=["artwork"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.put("/albums/{album_id}/artwork")
async def upload_album_artwork(
    album_id: int,
    artwork: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Upload custom artwork for album.

    Replaces existing cover.jpg in album folder.
    Available to all users (not just admin).
    """
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    if not album.path:
        raise HTTPException(status_code=400, detail="Album has no path")

    # Validate file type
    ext = Path(artwork.filename).suffix.lower() if artwork.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read content
    content = await artwork.read()

    # Validate file size
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save artwork
    album_path = Path(album.path)
    if not album_path.exists():
        raise HTTPException(status_code=404, detail="Album folder not found")

    artwork_path = album_path / "cover.jpg"

    # Backup existing if present
    if artwork_path.exists():
        backup_path = album_path / "cover.original.jpg"
        if not backup_path.exists():
            shutil.copy2(artwork_path, backup_path)

    # Write new artwork (convert to jpg if needed)
    if ext == ".png":
        try:
            from PIL import Image
            img = Image.open(BytesIO(content))
            img = img.convert("RGB")
            img.save(artwork_path, "JPEG", quality=95)
        except ImportError:
            # If PIL not available, just save as-is
            with open(artwork_path, "wb") as f:
                f.write(content)
    else:
        with open(artwork_path, "wb") as f:
            f.write(content)

    # Update database
    album.artwork_path = str(artwork_path)
    db.commit()

    return {"status": "uploaded", "path": str(artwork_path)}


@router.delete("/albums/{album_id}/artwork")
async def restore_original_artwork(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Restore original artwork if backup exists."""
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    if not album.path:
        raise HTTPException(status_code=400, detail="Album has no path")

    album_path = Path(album.path)
    backup_path = album_path / "cover.original.jpg"
    artwork_path = album_path / "cover.jpg"

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="No original artwork backup found")

    shutil.copy2(backup_path, artwork_path)
    return {"status": "restored"}


@router.put("/artists/{artist_id}/artwork")
async def upload_artist_artwork(
    artist_id: int,
    artwork: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Upload custom artwork for artist.

    Saves as artist.jpg in the artist's folder.
    Available to all users (not just admin).
    """
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    # Validate file type
    ext = Path(artwork.filename).suffix.lower() if artwork.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read content
    content = await artwork.read()

    # Validate file size
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Determine artist folder - use existing path or create from library root
    if artist.path and Path(artist.path).exists():
        artist_path = Path(artist.path)
    else:
        # Create artist folder in library
        artist_path = Path(settings.music_library) / artist.name
        artist_path.mkdir(parents=True, exist_ok=True)
        artist.path = str(artist_path)

    artwork_path = artist_path / "artist.jpg"

    # Backup existing if present
    if artwork_path.exists():
        backup_path = artist_path / "artist.original.jpg"
        if not backup_path.exists():
            shutil.copy2(artwork_path, backup_path)

    # Write new artwork (convert to jpg if needed)
    if ext == ".png":
        try:
            from PIL import Image
            img = Image.open(BytesIO(content))
            img = img.convert("RGB")
            img.save(artwork_path, "JPEG", quality=95)
        except ImportError:
            # If PIL not available, just save as-is
            with open(artwork_path, "wb") as f:
                f.write(content)
    else:
        with open(artwork_path, "wb") as f:
            f.write(content)

    # Update database
    artist.artwork_path = str(artwork_path)
    db.commit()

    return {"status": "uploaded", "path": str(artwork_path)}


@router.delete("/artists/{artist_id}/artwork")
async def restore_artist_original_artwork(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Restore original artist artwork if backup exists."""
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if not artist.path:
        raise HTTPException(status_code=400, detail="Artist has no path")

    artist_path = Path(artist.path)
    backup_path = artist_path / "artist.original.jpg"
    artwork_path = artist_path / "artist.jpg"

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="No original artwork backup found")

    shutil.copy2(backup_path, artwork_path)
    return {"status": "restored"}


@router.post("/artists/{artist_id}/artwork/fetch")
async def fetch_artist_artwork_from_qobuz(
    artist_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Fetch artist artwork from Qobuz API.

    Downloads artist image from Qobuz and saves as artist.jpg.
    """
    artist = db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    from app.services.import_service import ImportService
    import_service = ImportService(db)

    artwork_path = await import_service.fetch_artist_image_from_qobuz(artist, artist.name)

    if artwork_path:
        return {"status": "fetched", "path": artwork_path}
    else:
        raise HTTPException(status_code=404, detail="No artwork found on Qobuz for this artist")


@router.post("/artwork/artists/fetch-all")
async def fetch_all_missing_artist_artwork(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Fetch artwork from Qobuz for all artists missing artwork.

    Batch operation to backfill missing artist images.
    """
    from app.services.import_service import ImportService
    import_service = ImportService(db)

    # Find artists without artwork
    artists = db.query(Artist).filter(
        (Artist.artwork_path == None) | (Artist.artwork_path == "")
    ).all()

    results = []
    for artist in artists:
        try:
            artwork_path = await import_service.fetch_artist_image_from_qobuz(artist, artist.name)
            results.append({
                "artist_id": artist.id,
                "name": artist.name,
                "status": "fetched" if artwork_path else "not_found",
                "path": artwork_path
            })
        except Exception as e:
            results.append({
                "artist_id": artist.id,
                "name": artist.name,
                "status": "error",
                "error": str(e)
            })

    fetched = sum(1 for r in results if r["status"] == "fetched")
    return {
        "total": len(artists),
        "fetched": fetched,
        "not_found": len(artists) - fetched,
        "results": results
    }
