# Phase 5: Admin Features

**Goal:** Admin-only features operational: user management, TorrentLeech, exports, pending review.

**Prerequisites:** Phase 4 complete (frontend working)

---

## Checklist

- [x] User management (add/remove/update)
- [x] Pending review queue
- [x] Library maintenance tools
- [x] TorrentLeech integration
- [x] Export functionality
- [x] Settings page
- [x] Lidarr integration
- [x] Bandcamp sync
- [x] Custom artwork upload
- [x] Metadata editing

---

## 1. User Management

### app/api/admin.py

```python
"""Admin API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse


router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List all users."""
    return db.query(User).order_by(User.username).all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create new user."""
    # Check username not taken
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=data.username,
        password_hash=pwd_context.hash(data.password),
        is_admin=data.is_admin or False
    )
    db.add(user)
    db.commit()

    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Update user."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.password:
        user.password_hash = pwd_context.hash(data.password)

    if data.is_admin is not None:
        user.is_admin = data.is_admin

    db.commit()
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete user."""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    # Check if last admin
    admin_count = db.query(User).filter(User.is_admin == True).count()
    if user.is_admin and admin_count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete last admin")

    db.delete(user)
    db.commit()

    return {"status": "deleted"}
```

---

## 2. Pending Review Queue

### app/api/review.py

```python
"""Pending review API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.pending_review import PendingReview, ReviewStatus
from app.schemas.review import ReviewResponse, ApproveRequest, RejectRequest
from app.services.import_service import ImportService
from app.integrations.beets import BeetsClient
from app.integrations.exiftool import ExifToolClient


router = APIRouter(prefix="/admin/review", tags=["admin"])


@router.get("", response_model=list[ReviewResponse])
async def list_pending_review(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """List items pending review."""
    query = db.query(PendingReview).order_by(PendingReview.created_at.desc())

    if status:
        query = query.filter(PendingReview.status == status)
    else:
        query = query.filter(PendingReview.status == ReviewStatus.PENDING)

    return query.all()


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review_item(
    review_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get single review item with details."""
    review = db.query(PendingReview).get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    return review


@router.post("/{review_id}/approve")
async def approve_import(
    review_id: int,
    data: ApproveRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Approve and import pending item.

    Can override artist/album/year if auto-detection was wrong.
    """
    import asyncio
    from pathlib import Path

    review = db.query(PendingReview).get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Item already processed")

    try:
        beets = BeetsClient()
        exiftool = ExifToolClient()
        import_service = ImportService(db)

        folder = Path(review.path)

        # Import with overrides
        library_path = await beets.import_album(
            folder,
            artist=data.artist or review.suggested_artist,
            album=data.album or review.suggested_album,
            move=True
        )

        # Extract metadata
        tracks_metadata = await exiftool.get_album_metadata(library_path)

        # Import to database
        album = await import_service.import_album(
            path=library_path,
            tracks_metadata=tracks_metadata,
            source="import",
            source_url="",
            confidence=1.0  # Manual approval = full confidence
        )

        # Update review status
        review.status = ReviewStatus.APPROVED
        review.reviewed_by = admin.id
        review.result_album_id = album.id
        db.commit()

        return {"status": "approved", "album_id": album.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/reject")
async def reject_import(
    review_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Reject and optionally delete pending item."""
    import shutil
    from pathlib import Path

    review = db.query(PendingReview).get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Item already processed")

    # Optionally delete files
    if data.delete_files:
        folder = Path(review.path)
        if folder.exists():
            shutil.rmtree(folder)

    review.status = ReviewStatus.REJECTED
    review.reviewed_by = admin.id
    review.notes = data.reason
    db.commit()

    return {"status": "rejected"}
```

### app/schemas/review.py

```python
"""Review schemas."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class ReviewResponse(BaseModel):
    """Pending review response."""
    id: int
    path: str
    suggested_artist: Optional[str]
    suggested_album: Optional[str]
    suggested_year: Optional[int]
    beets_confidence: Optional[float]
    file_count: int
    total_size: Optional[int]
    status: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ApproveRequest(BaseModel):
    """Approve import request."""
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None


class RejectRequest(BaseModel):
    """Reject import request."""
    reason: Optional[str] = None
    delete_files: bool = False
```

---

## 3. TorrentLeech Integration

### app/integrations/torrentleech.py

```python
"""TorrentLeech integration for checking/uploading releases."""
import httpx
from typing import Optional
from pathlib import Path
from app.config import settings


class TorrentLeechClient:
    """TorrentLeech API client."""

    def __init__(self):
        self.api_key = settings.torrentleech_key
        self.base_url = "https://www.torrentleech.org/api"

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def search(self, query: str, category: str = "music") -> list[dict]:
        """Search TorrentLeech for existing releases.

        Args:
            query: Search query (release name)
            category: Category to search (music)

        Returns:
            List of matching torrents
        """
        if not self.api_key:
            raise TorrentLeechError("TorrentLeech API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/search",
                headers=self.headers,
                params={
                    "query": query,
                    "category": category
                }
            )
            response.raise_for_status()
            return response.json().get("torrents", [])

    async def check_exists(self, release_name: str) -> bool:
        """Check if release already exists on TorrentLeech.

        Normalizes the release name for comparison.
        """
        # Normalize: lowercase, replace spaces with dots
        normalized = release_name.lower().replace(" ", ".")

        results = await self.search(normalized)

        for result in results:
            result_normalized = result["name"].lower()
            if normalized in result_normalized:
                return True

        return False

    async def upload(
        self,
        torrent_path: Path,
        nfo_path: Optional[Path] = None,
        category: str = "music"
    ) -> dict:
        """Upload torrent to TorrentLeech.

        Args:
            torrent_path: Path to .torrent file
            nfo_path: Optional NFO file path
            category: Upload category

        Returns:
            Upload response with torrent ID
        """
        if not self.api_key:
            raise TorrentLeechError("TorrentLeech API key not configured")

        files = {
            "torrent": open(torrent_path, "rb")
        }

        if nfo_path and nfo_path.exists():
            files["nfo"] = open(nfo_path, "rb")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files=files,
                data={"category": category}
            )
            response.raise_for_status()
            return response.json()


class TorrentLeechError(Exception):
    """TorrentLeech operation failed."""
    pass
```

### app/api/torrentleech.py

```python
"""TorrentLeech API endpoints (admin only)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_admin
from app.models.user import User
from app.models.album import Album
from app.integrations.torrentleech import TorrentLeechClient, TorrentLeechError
from app.services.torrent import TorrentService


router = APIRouter(prefix="/tl", tags=["torrentleech"])


@router.get("/check/{release_name}")
async def check_release(
    release_name: str,
    admin: User = Depends(get_current_admin)
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
    tags: str = None,  # Comma-separated tags
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Create torrent and upload album to TorrentLeech.

    Steps:
    1. Check album exists in library
    2. Check not already on TorrentLeech
    3. Create .torrent file
    4. Generate NFO
    5. Upload
    """
    album = db.query(Album).get(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    client = TorrentLeechClient()
    torrent_service = TorrentService()

    # Build release name: Artist.Album.Year.Format
    first_track = album.tracks[0] if album.tracks else None
    format_str = first_track.format if first_track else "FLAC"
    quality = ""
    if first_track and not first_track.is_lossy:
        quality = f".{first_track.bit_depth}bit.{first_track.sample_rate // 1000}kHz"

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
```

### app/services/torrent.py

```python
"""Torrent creation service."""
import subprocess
from pathlib import Path
from typing import Optional
from app.config import settings
from app.models.album import Album


class TorrentService:
    """Creates .torrent files and NFOs."""

    def __init__(self):
        self.output_dir = Path(settings.paths_downloads) / "torrents"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def create_torrent(
        self,
        source_path: str,
        name: str,
        trackers: list[str],
        piece_size: int = 256  # KB
    ) -> Path:
        """Create .torrent file using mktorrent.

        Args:
            source_path: Path to album folder
            name: Release name
            trackers: List of tracker announce URLs
            piece_size: Piece size in KB

        Returns:
            Path to created .torrent file
        """
        output_path = self.output_dir / f"{name}.torrent"

        cmd = [
            "mktorrent",
            "-p",  # Private torrent
            "-l", str(piece_size),
        ]

        for tracker in trackers:
            cmd.extend(["-a", tracker])

        cmd.extend([
            "-o", str(output_path),
            source_path
        ])

        process = subprocess.run(cmd, capture_output=True)

        if process.returncode != 0:
            raise TorrentError(process.stderr.decode())

        return output_path

    async def generate_nfo(self, album: Album, release_name: str) -> Path:
        """Generate NFO file for release."""
        nfo_path = self.output_dir / f"{release_name}.nfo"

        # Get quality info
        first_track = album.tracks[0] if album.tracks else None
        quality = "Unknown"
        if first_track:
            if first_track.is_lossy:
                quality = f"{first_track.bitrate}kbps {first_track.format}"
            else:
                quality = f"{first_track.bit_depth}/{first_track.sample_rate // 1000}kHz {first_track.format}"

        nfo_content = f"""
================================================================================
                              {release_name}
================================================================================

Artist:  {album.artist.name}
Album:   {album.title}
Year:    {album.year or 'Unknown'}
Genre:   {album.genre or 'Unknown'}
Label:   {album.label or 'Unknown'}
Quality: {quality}
Tracks:  {len(album.tracks)}

--------------------------------------------------------------------------------
                                 TRACKLIST
--------------------------------------------------------------------------------
"""

        for track in sorted(album.tracks, key=lambda t: (t.disc_number, t.track_number)):
            duration = f"{track.duration // 60}:{track.duration % 60:02d}" if track.duration else "?:??"
            nfo_content += f"\n{track.track_number:02d}. {track.title} [{duration}]"

        nfo_content += f"""

--------------------------------------------------------------------------------

Source: {album.source or 'Unknown'}
Ripped with Barbossa Music Library
"""

        nfo_path.write_text(nfo_content.strip())
        return nfo_path


class TorrentError(Exception):
    """Torrent operation failed."""
    pass
```

---

## 4. Export Service

### app/services/export_service.py

```python
"""Export service for user libraries."""
import asyncio
import shutil
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.album import Album
from app.models.export import Export, ExportStatus, ExportFormat
from app.config import settings


class ExportService:
    """Exports user library to external location."""

    def __init__(self, db: Session):
        self.db = db

    async def create_export(
        self,
        user_id: int,
        destination: str,
        format: ExportFormat = ExportFormat.FLAC,
        include_artwork: bool = True,
        include_playlist: bool = False
    ) -> Export:
        """Create export job."""
        # Get user's hearted albums
        from app.models.user_album import UserAlbum

        album_count = self.db.query(UserAlbum).filter(
            UserAlbum.user_id == user_id
        ).count()

        export = Export(
            user_id=user_id,
            destination=destination,
            format=format,
            include_artwork=include_artwork,
            include_playlist=include_playlist,
            total_albums=album_count,
            status=ExportStatus.PENDING
        )
        self.db.add(export)
        self.db.commit()

        return export

    async def run_export(
        self,
        export_id: int,
        progress_callback: Optional[callable] = None
    ):
        """Execute export job.

        Steps:
        1. Get user's hearted albums
        2. For each album:
           a. Copy files (or convert if format != FLAC)
           b. Copy artwork if requested
        3. Generate M3U playlist if requested
        """
        export = self.db.query(Export).get(export_id)
        if not export:
            raise ExportError(f"Export {export_id} not found")

        export.status = ExportStatus.RUNNING
        self.db.commit()

        try:
            dest = Path(export.destination)
            dest.mkdir(parents=True, exist_ok=True)

            # Get user's albums
            from app.models.user_album import UserAlbum

            user_albums = self.db.query(UserAlbum).filter(
                UserAlbum.user_id == export.user_id
            ).all()

            playlist_entries = []
            total_size = 0

            for i, ua in enumerate(user_albums):
                album = self.db.query(Album).get(ua.album_id)
                if not album:
                    continue

                # Export album
                album_dest = dest / album.artist.name / f"{album.title} ({album.year})"
                album_dest.mkdir(parents=True, exist_ok=True)

                for track in album.tracks:
                    src = Path(track.path)
                    if not src.exists():
                        continue

                    if export.format == ExportFormat.FLAC:
                        # Direct copy
                        dst = album_dest / src.name
                        shutil.copy2(src, dst)
                    elif export.format == ExportFormat.MP3:
                        # Convert to MP3
                        dst = album_dest / f"{src.stem}.mp3"
                        await self._convert_to_mp3(src, dst)
                    elif export.format == ExportFormat.BOTH:
                        # Copy FLAC
                        shutil.copy2(src, album_dest / src.name)
                        # Also convert to MP3
                        mp3_dst = album_dest / f"{src.stem}.mp3"
                        await self._convert_to_mp3(src, mp3_dst)

                    total_size += dst.stat().st_size
                    playlist_entries.append(str(dst.relative_to(dest)))

                # Copy artwork
                if export.include_artwork and album.artwork_path:
                    artwork_src = Path(album.artwork_path)
                    if artwork_src.exists():
                        shutil.copy2(artwork_src, album_dest / artwork_src.name)

                # Update progress
                export.exported_albums = i + 1
                export.progress = int((i + 1) / export.total_albums * 100)
                self.db.commit()

                if progress_callback:
                    await progress_callback(export.progress)

            # Generate playlist
            if export.include_playlist:
                playlist_path = dest / "library.m3u"
                with open(playlist_path, "w") as f:
                    f.write("#EXTM3U\n")
                    for entry in playlist_entries:
                        f.write(f"{entry}\n")

            export.status = ExportStatus.COMPLETE
            export.total_size = total_size
            self.db.commit()

        except Exception as e:
            export.status = ExportStatus.FAILED
            export.error_message = str(e)
            self.db.commit()
            raise

    async def _convert_to_mp3(self, src: Path, dst: Path, bitrate: int = 320):
        """Convert audio file to MP3 using ffmpeg."""
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-codec:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            str(dst)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        if process.returncode != 0:
            raise ExportError(f"Failed to convert {src.name}")


class ExportError(Exception):
    """Export operation failed."""
    pass
```

### app/api/exports.py

```python
"""Export API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.export import Export, ExportStatus
from app.schemas.export import ExportCreate, ExportResponse
from app.services.export_service import ExportService
from app.tasks.exports import run_export_task


router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportResponse)
async def create_export(
    data: ExportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create new export job."""
    # Non-admins can only export their own library
    target_user_id = data.user_id if user.is_admin and data.user_id else user.id

    service = ExportService(db)
    export = await service.create_export(
        user_id=target_user_id,
        destination=data.destination,
        format=data.format,
        include_artwork=data.include_artwork,
        include_playlist=data.include_playlist
    )

    # Start background task
    task = run_export_task.delay(export.id)
    export.celery_task_id = task.id
    db.commit()

    return export


@router.get("", response_model=list[ExportResponse])
async def list_exports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List user's exports."""
    query = db.query(Export)

    if not user.is_admin:
        query = query.filter(Export.user_id == user.id)

    return query.order_by(Export.created_at.desc()).all()


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get export details."""
    export = db.query(Export).get(export_id)

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if not user.is_admin and export.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return export


@router.post("/{export_id}/cancel")
async def cancel_export(
    export_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Cancel running export."""
    export = db.query(Export).get(export_id)

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if not user.is_admin and export.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if export.status not in [ExportStatus.PENDING, ExportStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed export")

    # Cancel Celery task
    if export.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(export.celery_task_id, terminate=True)

    export.status = ExportStatus.CANCELLED
    db.commit()

    return {"status": "cancelled"}
```

---

## 5. Lidarr Integration

### app/integrations/lidarr.py

```python
"""Lidarr integration for artist requests."""
import httpx
from typing import Optional
from app.config import settings


class LidarrClient:
    """Lidarr API client."""

    def __init__(self):
        self.base_url = settings.lidarr_url
        self.api_key = settings.lidarr_api_key

    @property
    def headers(self) -> dict:
        return {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def test_connection(self) -> bool:
        """Test connection to Lidarr."""
        if not self.base_url or not self.api_key:
            return False

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/system/status",
                    headers=self.headers,
                    timeout=10
                )
                return response.status_code == 200
            except Exception:
                return False

    async def search_artist(self, query: str) -> list[dict]:
        """Search for artist in Lidarr/MusicBrainz."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/artist/lookup",
                headers=self.headers,
                params={"term": query}
            )
            response.raise_for_status()
            return response.json()

    async def add_artist(
        self,
        mbid: str,
        name: str,
        quality_profile_id: int = 1,
        metadata_profile_id: int = 1,
        monitored: bool = True,
        search_for_missing: bool = True
    ) -> dict:
        """Add artist to Lidarr for monitoring/downloading."""
        # Get root folder
        root_folder = await self._get_root_folder()

        payload = {
            "foreignArtistId": mbid,
            "artistName": name,
            "qualityProfileId": quality_profile_id,
            "metadataProfileId": metadata_profile_id,
            "rootFolderPath": root_folder,
            "monitored": monitored,
            "addOptions": {
                "searchForMissingAlbums": search_for_missing
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/artist",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()

    async def get_queue(self) -> list[dict]:
        """Get current download queue."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/queue",
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            return data.get("records", [])

    async def get_artists(self) -> list[dict]:
        """Get all monitored artists."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/artist",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def _get_root_folder(self) -> str:
        """Get first root folder path."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/rootfolder",
                headers=self.headers
            )
            response.raise_for_status()
            folders = response.json()
            if not folders:
                raise LidarrError("No root folders configured in Lidarr")
            return folders[0]["path"]


class LidarrError(Exception):
    """Lidarr operation failed."""
    pass
```

---

## 6. Bandcamp Sync

### app/integrations/bandcamp.py

```python
"""Bandcamp integration for syncing purchased collection."""
import asyncio
import json
from pathlib import Path
from typing import Optional
from app.config import settings


class BandcampClient:
    """Bandcamp collection sync via bandcamp-collection-downloader."""

    def __init__(self):
        self.cookies_path = Path(settings.bandcamp_cookies) if settings.bandcamp_cookies else None
        self.download_path = Path(settings.paths_downloads)

    async def sync_collection(
        self,
        cookies_file: Optional[Path] = None,
        progress_callback: Optional[callable] = None
    ) -> list[Path]:
        """Download user's purchased Bandcamp collection.

        Args:
            cookies_file: Path to cookies.txt with Bandcamp session
            progress_callback: Callback for progress updates

        Returns:
            List of downloaded album paths
        """
        cookies = cookies_file or self.cookies_path
        if not cookies or not cookies.exists():
            raise BandcampError("Bandcamp cookies file not found")

        cmd = [
            "bandcamp-collection-downloader",
            "--cookies", str(cookies),
            "--output", str(self.download_path),
            "--format", "flac",
            "--skip-existing"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        downloaded = []
        async for line in process.stdout:
            text = line.decode().strip()

            # Parse output for downloaded albums
            if "Downloaded:" in text:
                path = text.split("Downloaded:")[-1].strip()
                downloaded.append(Path(path))

                if progress_callback:
                    await progress_callback(f"Downloaded: {path}")

        await process.wait()

        if process.returncode != 0:
            raise BandcampError("Bandcamp sync failed")

        return downloaded


class BandcampError(Exception):
    """Bandcamp operation failed."""
    pass
```

---

## 7. Settings Page (Frontend)

### frontend/src/pages/Settings.jsx

```jsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function Settings() {
  return (
    <div className="page-settings">
      <header className="page-header">
        <h1 className="text-2xl">Settings</h1>
      </header>

      <div className="settings-layout">
        <nav className="settings-nav">
          <a href="#users" className="settings-nav-item">Users</a>
          <a href="#review" className="settings-nav-item">Pending Review</a>
          <a href="#integrations" className="settings-nav-item">Integrations</a>
          <a href="#maintenance" className="settings-nav-item">Maintenance</a>
        </nav>

        <div className="settings-content">
          <UserManagement />
          <PendingReviewSection />
          <IntegrationsSection />
          <MaintenanceSection />
        </div>
      </div>
    </div>
  )
}

function UserManagement() {
  const [newUser, setNewUser] = useState({ username: '', password: '', is_admin: false })
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const { data: users } = useQuery('users', () => api.getUsers().then(r => r.data))

  const createUser = useMutation(
    (data) => api.createUser(data),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('users')
        setNewUser({ username: '', password: '', is_admin: false })
        addNotification({ type: 'success', message: 'User created' })
      },
      onError: (error) => {
        addNotification({ type: 'error', message: error.response?.data?.detail || 'Failed to create user' })
      }
    }
  )

  const deleteUser = useMutation(
    (id) => api.deleteUser(id),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('users')
        addNotification({ type: 'success', message: 'User deleted' })
      }
    }
  )

  return (
    <section id="users" className="settings-section">
      <h2 className="text-xl">User Management</h2>

      <form
        className="user-form"
        onSubmit={(e) => {
          e.preventDefault()
          createUser.mutate(newUser)
        }}
      >
        <input
          type="text"
          placeholder="Username"
          value={newUser.username}
          onChange={e => setNewUser({ ...newUser, username: e.target.value })}
          className="input-default"
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={newUser.password}
          onChange={e => setNewUser({ ...newUser, password: e.target.value })}
          className="input-default"
          required
        />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={newUser.is_admin}
            onChange={e => setNewUser({ ...newUser, is_admin: e.target.checked })}
          />
          Admin
        </label>
        <button type="submit" className="btn-primary" disabled={createUser.isLoading}>
          Add User
        </button>
      </form>

      <table className="data-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Role</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users?.map(user => (
            <tr key={user.id}>
              <td>{user.username}</td>
              <td>{user.is_admin ? 'Admin' : 'User'}</td>
              <td>{new Date(user.created_at).toLocaleDateString()}</td>
              <td>
                <button
                  className="btn-ghost text-error"
                  onClick={() => {
                    if (confirm(`Delete user ${user.username}?`)) {
                      deleteUser.mutate(user.id)
                    }
                  }}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}

function PendingReviewSection() {
  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const { data: reviews } = useQuery(
    'pending-review',
    () => api.getPendingReview().then(r => r.data)
  )

  const approve = useMutation(
    ({ id, overrides }) => api.approveImport(id, overrides),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('pending-review')
        addNotification({ type: 'success', message: 'Import approved' })
      }
    }
  )

  const reject = useMutation(
    ({ id, reason }) => api.rejectImport(id, reason),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('pending-review')
        addNotification({ type: 'success', message: 'Import rejected' })
      }
    }
  )

  return (
    <section id="review" className="settings-section">
      <h2 className="text-xl">Pending Review</h2>

      {reviews?.length === 0 ? (
        <p className="text-muted">No items pending review</p>
      ) : (
        <div className="review-list">
          {reviews?.map(item => (
            <div key={item.id} className="review-item">
              <div className="review-item-info">
                <strong>{item.suggested_artist} - {item.suggested_album}</strong>
                <span className="text-muted">
                  Confidence: {Math.round((item.beets_confidence || 0) * 100)}%
                </span>
                <span className="text-muted">{item.file_count} files</span>
              </div>
              <div className="review-item-actions">
                <button
                  className="btn-secondary"
                  onClick={() => approve.mutate({ id: item.id, overrides: {} })}
                >
                  Approve
                </button>
                <button
                  className="btn-ghost text-error"
                  onClick={() => {
                    const reason = prompt('Rejection reason:')
                    if (reason !== null) {
                      reject.mutate({ id: item.id, reason })
                    }
                  }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function IntegrationsSection() {
  const { data: settings } = useQuery('settings', () => api.getSettings().then(r => r.data))

  return (
    <section id="integrations" className="settings-section">
      <h2 className="text-xl">Integrations</h2>

      <div className="integration-grid">
        <IntegrationCard
          name="Qobuz"
          status={settings?.['qobuz.enabled'] ? 'enabled' : 'disabled'}
          description="High-quality music downloads"
        />
        <IntegrationCard
          name="Lidarr"
          status={settings?.['lidarr.enabled'] ? 'enabled' : 'disabled'}
          description="Automated music collection"
        />
        <IntegrationCard
          name="Plex"
          status={settings?.['plex.enabled'] ? 'enabled' : 'disabled'}
          description="Media server integration"
        />
        <IntegrationCard
          name="TorrentLeech"
          status={settings?.['torrentleech.enabled'] ? 'enabled' : 'disabled'}
          description="Torrent uploads (admin)"
        />
      </div>
    </section>
  )
}

function IntegrationCard({ name, status, description }) {
  return (
    <div className="integration-card">
      <h3>{name}</h3>
      <p className="text-muted text-sm">{description}</p>
      <span className={`badge badge-${status === 'enabled' ? 'success' : 'muted'}`}>
        {status}
      </span>
    </div>
  )
}

function MaintenanceSection() {
  const { addNotification } = useNotificationStore()

  const rescan = useMutation(
    () => api.rescanLibrary(),
    {
      onSuccess: () => {
        addNotification({ type: 'success', message: 'Library rescan started' })
      }
    }
  )

  return (
    <section id="maintenance" className="settings-section">
      <h2 className="text-xl">Maintenance</h2>

      <div className="maintenance-actions">
        <div className="maintenance-action">
          <h3>Rescan Library</h3>
          <p className="text-muted text-sm">Scan for new or modified files in the library folder</p>
          <button
            className="btn-secondary"
            onClick={() => rescan.mutate()}
            disabled={rescan.isLoading}
          >
            Start Rescan
          </button>
        </div>
      </div>
    </section>
  )
}
```

---

## 8. Artwork Upload

### app/api/artwork.py

```python
"""Artwork upload and management."""
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.album import Album


router = APIRouter(prefix="/api/albums", tags=["albums"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_SIZE = 10 * 1024 * 1024  # 10MB


@router.put("/{album_id}/artwork")
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
    album = db.query(Album).get(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    # Validate file type
    ext = Path(artwork.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validate file size
    content = await artwork.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save artwork
    album_path = Path(album.path)
    artwork_path = album_path / "cover.jpg"

    # Backup existing if present
    if artwork_path.exists():
        backup_path = album_path / "cover.original.jpg"
        if not backup_path.exists():
            shutil.copy2(artwork_path, backup_path)

    # Write new artwork (convert to jpg if needed)
    if ext == ".png":
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGB")
        img.save(artwork_path, "JPEG", quality=95)
    else:
        with open(artwork_path, "wb") as f:
            f.write(content)

    # Update database
    album.artwork_path = str(artwork_path)
    db.commit()

    return {"status": "uploaded", "path": str(artwork_path)}


@router.delete("/{album_id}/artwork")
async def restore_original_artwork(
    album_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Restore original artwork if backup exists."""
    album = db.query(Album).get(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    album_path = Path(album.path)
    backup_path = album_path / "cover.original.jpg"
    artwork_path = album_path / "cover.jpg"

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail="No original artwork backup found")

    shutil.copy2(backup_path, artwork_path)
    return {"status": "restored"}
```

---

## 9. Metadata Editing

### app/api/metadata.py

```python
"""Metadata editing endpoints."""
from typing import Optional
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
    album = db.query(Album).get(album_id)
    if not album:
        raise HTTPException(status_code=404, detail="Album not found")

    exiftool = ExifToolClient()

    # Update database
    if data.title is not None:
        album.title = data.title
    if data.year is not None:
        album.year = data.year
    if data.genre is not None:
        album.genre = data.genre
    if data.label is not None:
        album.label = data.label

    # Update file tags for all tracks
    for track in album.tracks:
        from pathlib import Path
        await exiftool.write_metadata(
            Path(track.path),
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
    track = db.query(Track).get(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    exiftool = ExifToolClient()

    # Update database
    if data.title is not None:
        track.title = data.title
    if data.track_number is not None:
        track.track_number = data.track_number
    if data.disc_number is not None:
        track.disc_number = data.disc_number

    # Update file tags
    from pathlib import Path
    await exiftool.write_metadata(
        Path(track.path),
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
    artist = db.query(Artist).get(artist_id)
    if not artist:
        raise HTTPException(status_code=404, detail="Artist not found")

    if not data.name:
        raise HTTPException(status_code=400, detail="Name required")

    old_name = artist.name
    new_name = data.name

    # Update database
    artist.name = new_name

    # Rename folder
    from pathlib import Path
    old_path = Path(artist.path)
    new_path = old_path.parent / new_name

    if old_path.exists():
        old_path.rename(new_path)
        artist.path = str(new_path)

        # Update all album paths
        for album in artist.albums:
            album.path = album.path.replace(str(old_path), str(new_path))
            for track in album.tracks:
                track.path = track.path.replace(str(old_path), str(new_path))

    # Update file tags
    exiftool = ExifToolClient()
    for album in artist.albums:
        for track in album.tracks:
            await exiftool.write_metadata(
                Path(track.path),
                artist=new_name
            )

    db.commit()
    return {"status": "updated", "old_name": old_name, "new_name": new_name}
```

### frontend/src/components/MetadataEditor.jsx

```jsx
import { useState } from 'react'
import { useMutation, useQueryClient } from 'react-query'
import * as api from '../services/api'
import { useNotificationStore } from '../stores/notifications'

export default function MetadataEditor({ type, item, onClose }) {
  const [formData, setFormData] = useState({
    title: item.title || item.name || '',
    year: item.year || '',
    genre: item.genre || '',
    track_number: item.track_number || ''
  })

  const queryClient = useQueryClient()
  const { addNotification } = useNotificationStore()

  const updateMutation = useMutation(
    (data) => {
      if (type === 'album') {
        return api.updateAlbumMetadata(item.id, data)
      } else if (type === 'track') {
        return api.updateTrackMetadata(item.id, data)
      } else if (type === 'artist') {
        return api.updateArtistMetadata(item.id, data)
      }
    },
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['album', item.id])
        queryClient.invalidateQueries(['artist', item.artist_id])
        addNotification({ type: 'success', message: 'Metadata updated' })
        onClose()
      },
      onError: (error) => {
        addNotification({
          type: 'error',
          message: error.response?.data?.detail || 'Update failed'
        })
      }
    }
  )

  const handleSubmit = (e) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-sm" onClick={e => e.stopPropagation()}>
        <header className="modal-header">
          <h2 className="text-lg">Edit {type}</h2>
          <button className="btn-icon" onClick={onClose}>X</button>
        </header>

        <form onSubmit={handleSubmit} className="modal-body">
          {(type === 'album' || type === 'track') && (
            <div className="form-field">
              <label>Title</label>
              <input
                type="text"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          {type === 'artist' && (
            <div className="form-field">
              <label>Artist Name</label>
              <input
                type="text"
                value={formData.title}
                onChange={e => setFormData({ ...formData, title: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          {type === 'album' && (
            <>
              <div className="form-field">
                <label>Year</label>
                <input
                  type="number"
                  value={formData.year}
                  onChange={e => setFormData({ ...formData, year: e.target.value })}
                  className="input-default"
                />
              </div>
              <div className="form-field">
                <label>Genre</label>
                <input
                  type="text"
                  value={formData.genre}
                  onChange={e => setFormData({ ...formData, genre: e.target.value })}
                  className="input-default"
                />
              </div>
            </>
          )}

          {type === 'track' && (
            <div className="form-field">
              <label>Track Number</label>
              <input
                type="number"
                value={formData.track_number}
                onChange={e => setFormData({ ...formData, track_number: e.target.value })}
                className="input-default"
              />
            </div>
          )}

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
              disabled={updateMutation.isLoading}
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
```

---

## Validation

Before moving to Phase 6, verify:

1. [ ] User add/remove/update working
2. [ ] Pending review queue shows imports
3. [ ] Approve/reject updates status and imports
4. [ ] TorrentLeech check endpoint works
5. [ ] TorrentLeech upload creates torrent
6. [ ] Export job runs and copies files
7. [ ] Lidarr connection test passes
8. [ ] Settings page displays correctly
9. [ ] Custom artwork upload replaces cover.jpg
10. [ ] Metadata editing updates both DB and file tags

---

## Exit Criteria

- [ ] User management operational
- [ ] Review queue functional
- [ ] TorrentLeech integration working
- [ ] Export functionality working
- [ ] All admin features accessible
- [ ] Non-admins blocked from admin routes
- [ ] Artwork upload working for all users
- [ ] Metadata editing working for all users
