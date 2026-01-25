"""Download orchestration service."""
from pathlib import Path
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session

from app.models.download import Download, DownloadStatus, DownloadSource
from app.models.album import Album
from app.integrations.streamrip import StreamripClient, StreamripError
from app.integrations.ytdlp import YtdlpClient, YtdlpError
from app.integrations.beets import BeetsClient, BeetsError
from app.integrations.exiftool import ExifToolClient, quality_score
from app.services.import_service import ImportService, ImportError


class DuplicateError(Exception):
    """Album already exists with equal or better quality."""
    pass


class DownloadService:
    """Orchestrates download, tagging, and import.

    IMPORTANT RULES:
    1. Always download full album even if user requests single track
    2. Auto-heart behavior: Only auto-heart if search_type is 'track'
    3. Quality comparison: sample_rate > bit_depth > file_size
    """

    def __init__(self, db: Session):
        self.db = db
        self.streamrip = StreamripClient()
        self.ytdlp = YtdlpClient()
        self.beets = BeetsClient()
        self.exiftool = ExifToolClient()
        self.import_service = ImportService(db)

    async def search_qobuz(
        self,
        query: str,
        search_type: str = "album",
        limit: int = 20
    ) -> list[dict]:
        """Search Qobuz catalog."""
        return await self.streamrip.search(query, search_type, limit)

    async def download_qobuz(
        self,
        download_id: int,
        url: str,
        quality: int = 4,
        progress_callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Album:
        """Download from Qobuz and import.

        Args:
            download_id: Database download record ID
            url: Qobuz URL
            quality: Quality tier (0-4)
            progress_callback: Progress callback(percent, speed, eta)

        Returns:
            Imported Album model
        """
        download = self.db.query(Download).filter(Download.id == download_id).first()
        if not download:
            raise ValueError(f"Download not found: {download_id}")

        try:
            # Update status
            download.status = DownloadStatus.DOWNLOADING.value
            self.db.commit()

            # Download via streamrip
            downloaded_path = await self.streamrip.download(
                url,
                quality=quality,
                callback=progress_callback
            )

            # Import to library
            download.status = DownloadStatus.IMPORTING.value
            self.db.commit()

            album = await self._import_album(
                downloaded_path,
                source=DownloadSource.QOBUZ.value,
                source_url=url,
                user_id=download.user_id
            )

            # Complete
            download.status = DownloadStatus.COMPLETE.value
            download.result_album_id = album.id
            self.db.commit()

            # Auto-heart logic: Only if single track was requested
            if download.search_type == 'track':
                await self._auto_heart_album(download.user_id, album.id)

            return album

        except (StreamripError, BeetsError, ImportError) as e:
            download.status = DownloadStatus.FAILED.value
            download.error_message = str(e)
            self.db.commit()
            raise

        except Exception as e:
            download.status = DownloadStatus.FAILED.value
            download.error_message = str(e)
            self.db.commit()
            raise

    async def download_url(
        self,
        download_id: int,
        url: str,
        progress_callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Album:
        """Download from YouTube/Bandcamp/Soundcloud and import.

        Args:
            download_id: Database download record ID
            url: Media URL
            progress_callback: Progress callback(percent, speed, eta)

        Returns:
            Imported Album model
        """
        download = self.db.query(Download).filter(Download.id == download_id).first()
        if not download:
            raise ValueError(f"Download not found: {download_id}")

        try:
            # Get info first
            info = await self.ytdlp.get_info(url)
            source = info["source"]

            # Update status
            download.status = DownloadStatus.DOWNLOADING.value
            self.db.commit()

            # Download via yt-dlp
            downloaded_path = await self.ytdlp.download(
                url,
                callback=progress_callback
            )

            # Import to library
            download.status = DownloadStatus.IMPORTING.value
            self.db.commit()

            album = await self._import_album(
                downloaded_path,
                source=source,
                source_url=url,
                user_id=download.user_id,
                is_lossy=True
            )

            # Complete
            download.status = DownloadStatus.COMPLETE.value
            download.result_album_id = album.id
            self.db.commit()

            return album

        except (YtdlpError, BeetsError, ImportError) as e:
            download.status = DownloadStatus.FAILED.value
            download.error_message = str(e)
            self.db.commit()
            raise

        except Exception as e:
            download.status = DownloadStatus.FAILED.value
            download.error_message = str(e)
            self.db.commit()
            raise

    async def _import_album(
        self,
        path: Path,
        source: str,
        source_url: str,
        user_id: Optional[int] = None,
        is_lossy: bool = False
    ) -> Album:
        """Tag and import album to library.

        Steps:
        1. Identify via beets
        2. Extract quality via exiftool
        3. Check for duplicates
        4. Import to database
        """
        # Identify
        identification = await self.beets.identify(path)
        artist = identification.get("artist") or "Unknown Artist"
        album_title = identification.get("album") or path.name

        # Check duplicates
        existing = self.import_service.find_duplicate(artist, album_title)

        # Extract quality metadata
        tracks_metadata = await self.exiftool.get_album_metadata(path)

        if existing:
            # Compare quality
            new_quality = self._get_average_quality(tracks_metadata)
            old_quality = self._get_existing_quality(existing)

            if new_quality <= old_quality:
                raise DuplicateError(
                    f"Album already exists with equal or better quality: {existing.id}"
                )

            # Replace with higher quality
            # First, tag via beets
            library_path = await self.beets.import_album(path, move=True)

            # Re-extract after beets processing
            tracks_metadata = await self.exiftool.get_album_metadata(library_path)

            return self.import_service.replace_album(
                existing.id,
                library_path,
                tracks_metadata
            )

        # Tag via beets (moves to library)
        library_path = await self.beets.import_album(path, move=True)

        # Re-extract quality metadata after beets processing
        tracks_metadata = await self.exiftool.get_album_metadata(library_path)

        # Import to database
        return self.import_service.import_album(
            path=library_path,
            tracks_metadata=tracks_metadata,
            source=source,
            source_url=source_url,
            imported_by=user_id,
            confidence=identification.get("confidence", 1.0)
        )

    def _get_average_quality(self, tracks: list[dict]) -> int:
        """Get average quality score for tracks."""
        if not tracks:
            return 0

        scores = [
            quality_score(t.get("sample_rate"), t.get("bit_depth"))
            for t in tracks
        ]
        return sum(scores) // len(scores)

    def _get_existing_quality(self, album: Album) -> int:
        """Get average quality score for existing album."""
        tracks = album.tracks.all() if hasattr(album.tracks, 'all') else list(album.tracks)
        if not tracks:
            return 0

        scores = [
            quality_score(t.sample_rate, t.bit_depth)
            for t in tracks
        ]
        return sum(scores) // len(scores)

    async def _auto_heart_album(self, user_id: int, album_id: int) -> None:
        """Auto-add album to user's library when single track was requested."""
        from app.services.user_library import UserLibraryService
        user_library = UserLibraryService(self.db)
        await user_library.heart_album(user_id, album_id)
