"""Download orchestration service."""
import shutil
from pathlib import Path
from typing import Optional, Callable, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.download import Download, DownloadStatus, DownloadSource
from app.models.album import Album
from app.models.pending_review import PendingReview, PendingReviewStatus
from app.integrations.streamrip import StreamripClient, StreamripError
from app.integrations.ytdlp import YtdlpClient, YtdlpError
from app.integrations.beets import BeetsClient, BeetsError
from app.integrations.exiftool import ExifToolClient, quality_score
from app.services.import_service import ImportService, ImportError, MetadataValidationError, DuplicateContentError


class DuplicateError(Exception):
    """Album already exists with equal or better quality."""
    def __init__(self, existing_id: int):
        self.existing_id = existing_id
        super().__init__(f"Album already exists with equal or better quality: {existing_id}")


class NeedsReviewError(Exception):
    """Album needs manual review due to low beets confidence."""
    def __init__(self, review_id: int, confidence: float):
        self.review_id = review_id
        self.confidence = confidence
        super().__init__(f"Needs review (confidence: {confidence:.0%})")


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

    def _merge_beets_identification(
        self,
        tracks_metadata: list[dict],
        identification: dict
    ) -> list[dict]:
        """Merge beets identification data with ExifTool metadata.

        Beets/MusicBrainz data is authoritative for:
        - MusicBrainz IDs (album, artist, track)
        - Label and catalog number
        - ISRC codes (if not in file tags)

        ExifTool data is authoritative for:
        - Audio quality metrics (sample rate, bit depth, etc)
        - Lyrics (embedded in file)
        - Composer (embedded in file)

        Args:
            tracks_metadata: List of track metadata from ExifTool
            identification: Beets identification dict with track_data

        Returns:
            Updated tracks_metadata with merged data
        """
        import logging
        logger = logging.getLogger(__name__)

        # Merge album-level data into first track (used for album creation)
        if tracks_metadata:
            first_track = tracks_metadata[0]

            # Album-level MusicBrainz data from beets
            if identification.get("musicbrainz_album_id") and not first_track.get("musicbrainz_album_id"):
                first_track["musicbrainz_album_id"] = identification["musicbrainz_album_id"]

            if identification.get("musicbrainz_artist_id") and not first_track.get("musicbrainz_artist_id"):
                first_track["musicbrainz_artist_id"] = identification["musicbrainz_artist_id"]

            if identification.get("label") and not first_track.get("label"):
                first_track["label"] = identification["label"]

            if identification.get("catalog_number") and not first_track.get("catalog_number"):
                first_track["catalog_number"] = identification["catalog_number"]

            # Artist country from MusicBrainz (ISO 3166-1 alpha-2)
            if identification.get("country") and not first_track.get("artist_country"):
                first_track["artist_country"] = identification["country"]

        # Merge track-level data
        beets_tracks = identification.get("track_data") or []
        if not beets_tracks:
            return tracks_metadata

        for meta in tracks_metadata:
            track_num = meta.get("track_number")
            disc_num = meta.get("disc_number", 1)

            # Find matching beets track by position
            beets_track = next(
                (t for t in beets_tracks
                 if t.get("track_number") == track_num
                 and t.get("disc_number", 1) == disc_num),
                None
            )

            if not beets_track:
                continue

            # Merge MusicBrainz track ID (beets is authoritative)
            if beets_track.get("musicbrainz_track_id") and not meta.get("musicbrainz_track_id"):
                meta["musicbrainz_track_id"] = beets_track["musicbrainz_track_id"]

            if beets_track.get("musicbrainz_recording_id") and not meta.get("musicbrainz_recording_id"):
                meta["musicbrainz_recording_id"] = beets_track["musicbrainz_recording_id"]

            # Merge ISRC if not in file tags
            if beets_track.get("isrc") and not meta.get("isrc"):
                meta["isrc"] = beets_track["isrc"]

        logger.debug(f"Merged beets data: {len(beets_tracks)} tracks from beets")
        return tracks_metadata

    def _merge_qobuz_metadata(
        self,
        tracks_metadata: list[dict],
        qobuz_album: dict
    ) -> list[dict]:
        """Merge Qobuz API metadata with ExifTool metadata.

        Phase 7: Qobuz Enrichment

        Qobuz API is authoritative for (when available):
        - Label (commercial source)
        - Genre (commercial categorization)
        - UPC/barcode (unique release identifier)
        - ISRC per track (recording identifier)
        - Explicit/parental warning flag

        Args:
            tracks_metadata: List of track metadata from ExifTool
            qobuz_album: Album data from Qobuz API (from get_album())

        Returns:
            Updated tracks_metadata with Qobuz data merged
        """
        import logging
        logger = logging.getLogger(__name__)

        if not qobuz_album:
            return tracks_metadata

        # Merge album-level data into first track (used for album creation)
        if tracks_metadata:
            first_track = tracks_metadata[0]

            # QOB-001: Label from Qobuz API (Qobuz is authoritative)
            if qobuz_album.get("label") and not first_track.get("label"):
                first_track["label"] = qobuz_album["label"]
                logger.debug(f"Merged Qobuz label: {qobuz_album['label']}")

            # QOB-002: Genre from Qobuz API
            if qobuz_album.get("genre") and not first_track.get("genre"):
                first_track["genre"] = qobuz_album["genre"]
                logger.debug(f"Merged Qobuz genre: {qobuz_album['genre']}")

            # QOB-003: UPC/barcode from Qobuz API
            if qobuz_album.get("upc"):
                first_track["upc"] = qobuz_album["upc"]
                logger.debug(f"Merged Qobuz UPC: {qobuz_album['upc']}")

            # Album-level explicit flag (if any track is explicit)
            if qobuz_album.get("explicit"):
                first_track["album_explicit"] = True

        # QOB-004: Merge track-level data (ISRC, explicit)
        qobuz_tracks = qobuz_album.get("tracks") or []
        if not qobuz_tracks:
            logger.debug("No Qobuz track data to merge")
            return tracks_metadata

        merged_isrc = 0
        merged_explicit = 0

        for meta in tracks_metadata:
            track_num = meta.get("track_number")
            disc_num = meta.get("disc_number", 1)

            # Find matching Qobuz track by position
            qobuz_track = next(
                (t for t in qobuz_tracks
                 if t.get("track_number") == track_num
                 and t.get("disc_number", 1) == disc_num),
                None
            )

            if not qobuz_track:
                continue

            # Merge ISRC (Qobuz is authoritative if not already set)
            if qobuz_track.get("isrc") and not meta.get("isrc"):
                meta["isrc"] = qobuz_track["isrc"]
                merged_isrc += 1

            # Merge explicit flag
            if qobuz_track.get("explicit") and not meta.get("explicit"):
                meta["explicit"] = qobuz_track["explicit"]
                merged_explicit += 1

        logger.info(
            f"Merged Qobuz data: label={qobuz_album.get('label', 'N/A')}, "
            f"genre={qobuz_album.get('genre', 'N/A')}, "
            f"upc={qobuz_album.get('upc', 'N/A')}, "
            f"isrc={merged_isrc}/{len(tracks_metadata)} tracks"
        )
        return tracks_metadata

    async def _fetch_qobuz_album_metadata(self, url: str) -> Optional[dict]:
        """Fetch album metadata from Qobuz API for enrichment.

        Phase 7: Extract album ID from URL and fetch full metadata.

        Args:
            url: Qobuz album URL (e.g., https://www.qobuz.com/us-en/album/...)

        Returns:
            Album dict with tracks from Qobuz API, or None if fetch fails
        """
        import logging
        import re
        logger = logging.getLogger(__name__)

        try:
            # Extract album ID from URL
            # Formats: /album/title/id or /album/id
            match = re.search(r'/album/[^/]+/(\d+)|/album/(\d+)', url)
            if not match:
                logger.warning(f"Could not extract album ID from URL: {url}")
                return None

            album_id = match.group(1) or match.group(2)

            # Fetch from Qobuz API
            from app.integrations.qobuz_api import get_qobuz_api
            qobuz = get_qobuz_api()
            album_data = await qobuz.get_album(album_id)

            logger.debug(f"Fetched Qobuz metadata for album ID {album_id}")
            return album_data

        except Exception as e:
            # Non-fatal: we can still import without Qobuz metadata
            logger.warning(f"Failed to fetch Qobuz metadata: {e}")
            return None

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
        import logging
        logger = logging.getLogger(__name__)

        download = self.db.query(Download).filter(Download.id == download_id).first()
        if not download:
            raise ValueError(f"Download not found: {download_id}")

        try:
            # Phase 7: Fetch Qobuz metadata BEFORE download for enrichment
            # This gives us label, genre, UPC, ISRC per track
            qobuz_metadata = await self._fetch_qobuz_album_metadata(url)
            if qobuz_metadata:
                logger.info(
                    f"Pre-fetched Qobuz metadata: {qobuz_metadata.get('title')} - "
                    f"label={qobuz_metadata.get('label')}, genre={qobuz_metadata.get('genre')}"
                )

            # Update status
            download.status = DownloadStatus.DOWNLOADING.value
            self.db.commit()

            # Download via streamrip
            downloaded_path = await self.streamrip.download(
                url,
                quality=quality,
                callback=progress_callback
            )

            # Import to library - Qobuz is trusted, skip confidence check but run beets for lyrics/artwork
            download.status = DownloadStatus.IMPORTING.value
            self.db.commit()

            album = await self._import_album(
                downloaded_path,
                source=DownloadSource.QOBUZ.value,
                source_url=url,
                user_id=download.user_id,
                min_confidence=0.0,  # Trust Qobuz - never send to review
                qobuz_metadata=qobuz_metadata  # Phase 7: Pass Qobuz metadata
            )

            # Fetch artist artwork from Qobuz
            await self._ensure_artist_artwork(album, DownloadSource.QOBUZ.value)

            # Complete
            download.status = DownloadStatus.COMPLETE.value
            download.result_album_id = album.id
            self.db.commit()

            # Auto-heart logic: Only if single track was requested
            if download.search_type == 'track':
                await self._auto_heart_album(download.user_id, album.id)

            return album

        except NeedsReviewError as e:
            # Not a failure - album moved to review queue
            download.status = DownloadStatus.PENDING_REVIEW.value
            download.error_message = f"Needs review: {e.confidence:.0%} confidence"
            download.result_review_id = e.review_id
            self.db.commit()
            raise
        except DuplicateError as e:
            download.status = DownloadStatus.DUPLICATE.value
            download.error_message = str(e)
            download.result_album_id = e.existing_id
            self.db.commit()
            return None
        except DuplicateContentError as e:
            # Content-based duplicate (same file checksums)
            download.status = DownloadStatus.DUPLICATE.value
            download.error_message = f"Content duplicate: {e.matching_checksums}/{e.total_tracks} tracks match existing album"
            download.result_album_id = e.existing_album.id
            self.db.commit()
            return None

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

        except NeedsReviewError as e:
            # Not a failure - album moved to review queue
            download.status = DownloadStatus.PENDING_REVIEW.value
            download.error_message = f"Needs review: {e.confidence:.0%} confidence"
            download.result_review_id = e.review_id
            self.db.commit()
            raise
        except DuplicateError as e:
            download.status = DownloadStatus.DUPLICATE.value
            download.error_message = str(e)
            download.result_album_id = e.existing_id
            self.db.commit()
            return None
        except DuplicateContentError as e:
            # Content-based duplicate (same file checksums)
            download.status = DownloadStatus.DUPLICATE.value
            download.error_message = f"Content duplicate: {e.matching_checksums}/{e.total_tracks} tracks match existing album"
            download.result_album_id = e.existing_album.id
            self.db.commit()
            return None

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
        is_lossy: bool = False,
        min_confidence: float = 0.85,
        qobuz_metadata: Optional[dict] = None
    ) -> Album:
        """Tag and import album to library.

        Steps:
        1. Identify via beets
        2. Check confidence (< min_confidence -> review queue)
        3. Extract quality via exiftool
        4. Merge Qobuz metadata (Phase 7: label, genre, UPC, ISRC)
        5. Check for duplicates
        6. Import to database

        Args:
            path: Path to downloaded album
            source: Download source (qobuz, youtube, etc.)
            source_url: Original URL
            user_id: User who triggered download
            is_lossy: If True, mark tracks as lossy
            min_confidence: Minimum beets confidence (0-1)
            qobuz_metadata: Optional Qobuz API metadata for enrichment (Phase 7)
        """
        # Identify
        identification = await self.beets.identify(path)
        artist = identification.get("artist")  # No fallback - let validation catch it
        album_title = identification.get("album") or path.name
        confidence = identification.get("confidence", 0)

        # Check confidence - low confidence goes to review queue
        if confidence < min_confidence:
            review = await self._move_to_review(
                path=path,
                identification=identification,
                source=source,
                source_url=source_url,
                note="Low beets confidence"
            )
            raise NeedsReviewError(review.id, confidence)

        # Pre-validate metadata before expensive beets import
        tracks_metadata_raw = await self.exiftool.get_album_metadata(path)
        is_valid, issues = self.import_service.validate_metadata(
            tracks_metadata_raw,
            folder_name=path.name,
            strict=True
        )
        if not is_valid:
            review = await self._move_to_review(
                path=path,
                identification=identification,
                source=source,
                source_url=source_url,
                note=f"Metadata validation failed: {'; '.join(issues)}"
            )
            raise NeedsReviewError(review.id, 0.0)

        # Check duplicates (validation passed, so artist should be valid)
        # Use artist from raw metadata if beets didn't identify
        if not artist:
            artist = tracks_metadata_raw[0].get("artist") if tracks_metadata_raw else None

        existing = None
        if artist:
            existing = self.import_service.find_duplicate(artist, album_title)

        # Use pre-extracted metadata for quality comparison
        tracks_metadata = tracks_metadata_raw

        if existing:
            # Compare quality
            new_quality = self._get_average_quality(tracks_metadata)
            old_quality = self._get_existing_quality(existing)

            if new_quality <= old_quality:
                raise DuplicateError(existing.id)

            # Replace with higher quality
            # First, tag via beets
            library_path = await self.beets.import_album(path, move=True)

            # Re-extract after beets processing
            tracks_metadata = await self.exiftool.get_album_metadata(library_path)
            # Merge MusicBrainz data from beets identification
            tracks_metadata = self._merge_beets_identification(tracks_metadata, identification)
            # Phase 7: Merge Qobuz metadata (label, genre, UPC, ISRC)
            if qobuz_metadata:
                tracks_metadata = self._merge_qobuz_metadata(tracks_metadata, qobuz_metadata)

            album = await self.import_service.replace_album(
                existing.id,
                library_path,
                tracks_metadata
            )
            await self._ensure_artwork(album)
            return album

        # Tag via beets (moves to library)
        library_path = await self.beets.import_album(path, move=True)
        original_path = path  # Keep reference for potential rollback

        try:
            # Re-extract quality metadata after beets processing
            tracks_metadata = await self.exiftool.get_album_metadata(library_path)
            # Merge MusicBrainz data from beets identification
            tracks_metadata = self._merge_beets_identification(tracks_metadata, identification)
            # Phase 7: Merge Qobuz metadata (label, genre, UPC, ISRC)
            if qobuz_metadata:
                tracks_metadata = self._merge_qobuz_metadata(tracks_metadata, qobuz_metadata)

            # Import to database
            album = await self.import_service.import_album(
                path=library_path,
                tracks_metadata=tracks_metadata,
                source=source,
                source_url=source_url,
                imported_by=user_id,
                confidence=confidence
            )
            await self._ensure_artwork(album)
            return album

        except Exception as e:
            # ROLLBACK: Move files to failed folder for recovery
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Import failed after file move, attempting rollback: {e}")

            try:
                if library_path.exists():
                    # Move to failed imports folder instead of back to downloads
                    failed_dir = Path(settings.music_import) / "failed"
                    failed_dir.mkdir(parents=True, exist_ok=True)

                    failed_path = failed_dir / library_path.name
                    counter = 1
                    while failed_path.exists():
                        failed_path = failed_dir / f"{library_path.name}_{counter}"
                        counter += 1

                    shutil.move(str(library_path), str(failed_path))
                    logger.info(f"Moved failed import to: {failed_path}")

                    # Clean up empty directories in library
                    artist_dir = library_path.parent
                    if artist_dir.exists() and not any(artist_dir.iterdir()):
                        artist_dir.rmdir()
            except Exception as rollback_error:
                logger.critical(
                    f"CRITICAL: Rollback failed! Orphaned files at {library_path}. "
                    f"Rollback error: {rollback_error}"
                )

            raise  # Re-raise the original exception

    async def _ensure_artwork(self, album: Album) -> None:
        """Fetch artwork if missing and update DB."""
        if album.artwork_path:
            return

        artwork = await self.import_service.fetch_artwork_if_missing(album)
        if artwork:
            album.artwork_path = artwork
            self.db.commit()

    async def _ensure_artist_artwork(self, album: Album, source: str) -> None:
        """Fetch artist artwork from Qobuz if missing.

        Only runs for Qobuz downloads to leverage the Qobuz API.
        """
        if source != DownloadSource.QOBUZ.value:
            return

        if not album.artist:
            return

        if album.artist.artwork_path and Path(album.artist.artwork_path).exists():
            return

        await self.import_service.fetch_artist_image_from_qobuz(
            album.artist,
            album.artist.name
        )

    async def _move_to_review(
        self,
        path: Path,
        identification: dict,
        source: str,
        source_url: str,
        note: str = ""
    ) -> PendingReview:
        """Move low-confidence album to review queue.

        Args:
            path: Path to downloaded album
            identification: Beets identification result
            source: Download source (qobuz, youtube, etc.)
            source_url: Original URL
            note: Reason for review (e.g., validation failure details)

        Returns:
            Created PendingReview record
        """
        # Determine review path
        review_dir = Path(settings.music_import) / "review"
        review_dir.mkdir(parents=True, exist_ok=True)

        review_path = review_dir / path.name
        counter = 1
        while review_path.exists():
            review_path = review_dir / f"{path.name}_{counter}"
            counter += 1

        # Move files
        shutil.move(str(path), str(review_path))

        # Count audio files
        audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
        track_count = sum(
            1 for f in review_path.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        )

        # Extract quality info
        tracks_metadata = await self.exiftool.get_album_metadata(review_path)
        quality_info = None
        if tracks_metadata:
            first = tracks_metadata[0]
            quality_info = {
                "sample_rate": first.get("sample_rate"),
                "bit_depth": first.get("bit_depth"),
                "format": first.get("format")
            }

        # Create review record
        review = PendingReview(
            path=str(review_path),
            suggested_artist=identification.get("artist"),
            suggested_album=identification.get("album"),
            beets_confidence=identification.get("confidence", 0),
            track_count=track_count,
            quality_info=quality_info,
            source=source,
            source_url=source_url,
            status=PendingReviewStatus.PENDING,
            notes=note if note else None
        )
        self.db.add(review)
        self.db.commit()

        return review

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
