"""TorrentLeech API endpoints (admin only)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.user import User
from app.models.album import Album
from app.integrations.torrentleech import TorrentLeechClient, TorrentLeechError
from app.services.torrent import TorrentService


router = APIRouter(prefix="/tl", tags=["torrentleech"])


@router.get("/check/{release_name}")
async def check_release(
    release_name: str,
    admin: User = Depends(require_admin)
):
    """Check if release exists on TorrentLeech."""
    client = TorrentLeechClient()

    try:
        exists = await client.check_exists(release_name)
        return {
            "release_name": release_name,
            "exists": exists,
            "safe_to_upload": not exists
        }
    except TorrentLeechError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/{album_id}")
async def upload_album(
    album_id: int,
    tags: str = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Create torrent and upload album to TorrentLeech.

    Steps:
    1. Check album exists in library
    2. Check not already on TorrentLeech
    3. Create .torrent file
    4. Generate NFO
    5. Upload
    """
    album = db.query(Album).filter(Album.id == album_id).first()
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    client = TorrentLeechClient()
    torrent_service = TorrentService()

    # Build release name: Artist.Album.Year.Format
    first_track = album.tracks.first()
    format_str = first_track.format if first_track else "FLAC"
    quality = ""
    if first_track and not first_track.is_lossy:
        bd = first_track.bit_depth or 16
        sr = first_track.sample_rate // 1000 if first_track.sample_rate else 44
        quality = f".{bd}bit.{sr}kHz"

    release_name = (
        f"{album.artist.name}.{album.title}.{album.year or 'XXXX'}"
        f"{quality}.{format_str}"
    ).replace(" ", ".")

    try:
        # Check exists
        if await client.check_exists(release_name):
            raise HTTPException(
                status_code=400,
                detail="Release already exists on TorrentLeech"
            )

        # Create torrent
        torrent_path = await torrent_service.create_torrent(
            source_path=album.path,
            name=release_name,
            trackers=["https://tracker.torrentleech.org/announce"]
        )

        # Generate NFO
        nfo_path = await torrent_service.generate_nfo(album, release_name)

        # Upload
        result = await client.upload(
            torrent_path=torrent_path,
            nfo_path=nfo_path,
            category="music"
        )

        return {
            "status": "uploaded",
            "release_name": release_name,
            "torrent_id": result.get("id")
        }

    except TorrentLeechError as e:
        raise HTTPException(status_code=500, detail=str(e))
