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
