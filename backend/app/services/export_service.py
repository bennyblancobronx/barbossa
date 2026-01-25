"""Export service for user libraries."""
import asyncio
import shutil
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.album import Album
from app.models.user_library import user_albums
from app.models.export import Export, ExportStatus, ExportFormat
from app.config import settings


class ExportError(Exception):
    """Export operation failed."""
    pass


class ExportService:
    """Exports user library to external location."""

    def __init__(self, db: Session):
        self.db = db

    def create_export(
        self,
        user_id: int,
        destination: str,
        format: ExportFormat = ExportFormat.FLAC,
        include_artwork: bool = True,
        include_playlist: bool = False
    ) -> Export:
        """Create export job."""
        # Count user's hearted albums
        album_count = self.db.query(user_albums).filter(
            user_albums.c.user_id == user_id
        ).count()

        export = Export(
            user_id=user_id,
            destination=destination,
            format=format.value if isinstance(format, ExportFormat) else format,
            include_artwork=include_artwork,
            include_playlist=include_playlist,
            total_albums=album_count,
            status=ExportStatus.PENDING
        )
        self.db.add(export)
        self.db.commit()
        self.db.refresh(export)

        return export

    async def run_export(
        self,
        export_id: int,
        progress_callback: Optional[Callable] = None
    ):
        """Execute export job.

        Steps:
        1. Get user's hearted albums
        2. For each album:
           a. Copy files (or convert if format != FLAC)
           b. Copy artwork if requested
        3. Generate M3U playlist if requested
        """
        export = self.db.query(Export).filter(Export.id == export_id).first()
        if not export:
            raise ExportError(f"Export {export_id} not found")

        export.status = ExportStatus.RUNNING
        export.started_at = datetime.utcnow()
        self.db.commit()

        try:
            dest = Path(export.destination)
            dest.mkdir(parents=True, exist_ok=True)

            # Get user's albums
            user_album_ids = self.db.query(user_albums.c.album_id).filter(
                user_albums.c.user_id == export.user_id
            ).all()
            album_ids = [a[0] for a in user_album_ids]

            playlist_entries = []
            total_size = 0

            for i, album_id in enumerate(album_ids):
                album = self.db.query(Album).filter(Album.id == album_id).first()
                if not album:
                    continue

                # Export album
                album_dest = dest / album.artist.name / f"{album.title} ({album.year or 'Unknown'})"
                album_dest.mkdir(parents=True, exist_ok=True)

                for track in album.tracks:
                    src = Path(track.path)
                    if not src.exists():
                        continue

                    export_format = export.format
                    if isinstance(export_format, str):
                        export_format = ExportFormat(export_format)

                    if export_format == ExportFormat.FLAC:
                        # Direct copy
                        dst = album_dest / src.name
                        shutil.copy2(src, dst)
                        total_size += dst.stat().st_size
                        playlist_entries.append(str(dst.relative_to(dest)))

                    elif export_format == ExportFormat.MP3:
                        # Convert to MP3
                        dst = album_dest / f"{src.stem}.mp3"
                        await self._convert_to_mp3(src, dst)
                        total_size += dst.stat().st_size
                        playlist_entries.append(str(dst.relative_to(dest)))

                    elif export_format == ExportFormat.BOTH:
                        # Copy FLAC
                        flac_dst = album_dest / src.name
                        shutil.copy2(src, flac_dst)
                        total_size += flac_dst.stat().st_size
                        playlist_entries.append(str(flac_dst.relative_to(dest)))

                        # Also convert to MP3
                        mp3_dst = album_dest / f"{src.stem}.mp3"
                        await self._convert_to_mp3(src, mp3_dst)
                        total_size += mp3_dst.stat().st_size

                # Copy artwork
                if export.include_artwork and album.artwork_path:
                    artwork_src = Path(album.artwork_path)
                    if artwork_src.exists():
                        shutil.copy2(artwork_src, album_dest / artwork_src.name)

                # Update progress
                export.exported_albums = i + 1
                export.progress = int((i + 1) / export.total_albums * 100) if export.total_albums > 0 else 100
                self.db.commit()

                if progress_callback:
                    await progress_callback(export.progress)

            # Generate playlist
            if export.include_playlist and playlist_entries:
                playlist_path = dest / "library.m3u"
                with open(playlist_path, "w") as f:
                    f.write("#EXTM3U\n")
                    for entry in playlist_entries:
                        f.write(f"{entry}\n")

            export.status = ExportStatus.COMPLETE
            export.total_size = total_size
            export.completed_at = datetime.utcnow()
            self.db.commit()

        except Exception as e:
            export.status = ExportStatus.FAILED
            export.error_message = str(e)
            export.completed_at = datetime.utcnow()
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
