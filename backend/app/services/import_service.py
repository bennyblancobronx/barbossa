"""Album import and duplicate detection service."""
import shutil
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.import_history import ImportHistory
from app.models.pending_review import PendingReview, PendingReviewStatus
from app.utils.normalize import normalize_text
from app.integrations.exiftool import quality_score, format_quality
from app.services.quality import generate_checksum

logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Import operation failed."""
    pass


class ImportService:
    """Handles album import and duplicate detection."""

    def __init__(self, db: Session):
        self.db = db

    def find_duplicate(self, artist: str, album: str) -> Optional[Album]:
        """Check if album already exists (sync version).

        Uses normalized names to catch variations like:
        - "Dark Side of the Moon" vs "The Dark Side of the Moon"
        - "Dark Side of the Moon (Remaster)" vs "Dark Side of the Moon"
        """
        norm_artist = normalize_text(artist)
        norm_album = normalize_text(album)

        # Check import history first (faster)
        existing = self.db.query(ImportHistory).filter(
            ImportHistory.artist_normalized == norm_artist,
            ImportHistory.album_normalized == norm_album
        ).first()

        if existing and existing.album_id:
            album_record = self.db.query(Album).filter(Album.id == existing.album_id).first()
            if album_record:
                return album_record

        # Fallback to direct album lookup
        return self.db.query(Album).join(Artist).filter(
            Artist.normalized_name == norm_artist,
            Album.normalized_title == norm_album
        ).first()

    async def find_duplicate_async(self, artist: str, album: str) -> Optional[Album]:
        """Async wrapper for find_duplicate."""
        return self.find_duplicate(artist, album)

    async def import_album(
        self,
        path: Path,
        tracks_metadata: list[dict],
        source: str,
        source_url: str,
        imported_by: Optional[int] = None,
        confidence: float = 1.0
    ) -> Album:
        """Import album and tracks to database.

        Args:
            path: Path to album folder in library
            tracks_metadata: List of track metadata from exiftool
            source: Download source (qobuz, youtube, etc.)
            source_url: Original URL
            imported_by: User ID who triggered import
            confidence: Beets identification confidence

        Returns:
            Created Album model
        """
        if not tracks_metadata:
            raise ImportError("No tracks found in album")

        first_track = tracks_metadata[0]

        # Find or create artist
        artist = self._get_or_create_artist(
            first_track.get("artist") or "Unknown Artist",
            path.parent
        )

        # Determine album title
        album_title = first_track.get("album") or path.name
        normalized_title = normalize_text(album_title)

        # Find artwork
        artwork_path = self._find_artwork(path)

        # Create album
        album = Album(
            artist_id=artist.id,
            title=album_title,
            normalized_title=normalized_title,
            year=first_track.get("year"),
            path=str(path),
            artwork_path=artwork_path,
            total_tracks=len(tracks_metadata),
            available_tracks=len(tracks_metadata),
            source=source,
            source_url=source_url
        )
        self.db.add(album)
        self.db.flush()

        # Create tracks
        for i, meta in enumerate(tracks_metadata):
            track = Track(
                album_id=album.id,
                title=meta.get("title") or f"Track {i + 1}",
                normalized_title=normalize_text(meta.get("title") or f"Track {i + 1}"),
                track_number=meta.get("track_number") or (i + 1),
                disc_number=1,
                duration=meta.get("duration"),
                path=meta.get("path") or str(path / f"track_{i + 1}"),
                sample_rate=meta.get("sample_rate"),
                bit_depth=meta.get("bit_depth"),
                bitrate=meta.get("bitrate"),
                channels=meta.get("channels") or 2,
                file_size=meta.get("file_size"),
                format=meta.get("format"),
                is_lossy=meta.get("is_lossy", False),
                source=source,
                source_url=source_url,
                source_quality=format_quality(
                    meta.get("sample_rate"),
                    meta.get("bit_depth"),
                    meta.get("format", ""),
                    meta.get("is_lossy", False),
                    meta.get("bitrate")
                ),
                imported_by=imported_by
            )
            self.db.add(track)
            self.db.flush()

            # Generate checksum if file exists
            track_path = Path(track.path)
            if track_path.exists():
                track.checksum = generate_checksum(track_path)

            # Add to import history for duplicate detection
            history = ImportHistory(
                artist_normalized=artist.normalized_name,
                album_normalized=normalized_title,
                track_normalized=normalize_text(track.title),
                source=source,
                quality_score=quality_score(meta.get("sample_rate"), meta.get("bit_depth")),
                track_id=track.id,
                album_id=album.id
            )
            self.db.add(history)

        self.db.commit()
        return album

    def replace_album(self, album_id: int, new_path: Path, tracks_metadata: list[dict]) -> Album:
        """Replace existing album with higher quality version.

        Preserves user library associations (hearts).
        """
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            raise ImportError(f"Album not found: {album_id}")

        old_path = Path(album.path) if album.path else None

        # Delete old tracks and import history from database
        self.db.query(Track).filter(Track.album_id == album_id).delete()
        self.db.query(ImportHistory).filter(ImportHistory.album_id == album_id).delete()

        # Update album path
        album.path = str(new_path)
        album.artwork_path = self._find_artwork(new_path)
        album.total_tracks = len(tracks_metadata)
        album.available_tracks = len(tracks_metadata)

        # Add new tracks
        for i, meta in enumerate(tracks_metadata):
            track = Track(
                album_id=album.id,
                title=meta.get("title") or f"Track {i + 1}",
                normalized_title=normalize_text(meta.get("title") or f"Track {i + 1}"),
                track_number=meta.get("track_number") or (i + 1),
                disc_number=1,
                duration=meta.get("duration"),
                path=meta.get("path"),
                sample_rate=meta.get("sample_rate"),
                bit_depth=meta.get("bit_depth"),
                bitrate=meta.get("bitrate"),
                channels=meta.get("channels") or 2,
                file_size=meta.get("file_size"),
                format=meta.get("format"),
                is_lossy=meta.get("is_lossy", False),
                source=album.source,
                source_url=album.source_url,
                source_quality=format_quality(
                    meta.get("sample_rate"),
                    meta.get("bit_depth"),
                    meta.get("format", ""),
                    meta.get("is_lossy", False),
                    meta.get("bitrate")
                )
            )
            self.db.add(track)
            self.db.flush()

            track_path = Path(track.path) if track.path else None
            if track_path and track_path.exists():
                track.checksum = generate_checksum(track_path)

            history = ImportHistory(
                artist_normalized=album.artist.normalized_name if album.artist else normalize_text(album.title),
                album_normalized=album.normalized_title,
                track_normalized=normalize_text(track.title),
                source=album.source or "import",
                quality_score=quality_score(meta.get("sample_rate"), meta.get("bit_depth")),
                track_id=track.id,
                album_id=album.id
            )
            self.db.add(history)

        self.db.commit()

        # Delete old files after database update succeeds
        if old_path and old_path.exists() and old_path != new_path:
            shutil.rmtree(old_path, ignore_errors=True)

        return album

    def create_pending_review(
        self,
        path: Path,
        beets_output: str,
        source: str,
        quality_info: Optional[dict] = None,
        error_message: Optional[str] = None
    ) -> PendingReview:
        """Create pending review entry for unidentified album.

        Args:
            path: Path to album folder
            beets_output: Output from beets identify
            source: Original download source
            quality_info: Quality metadata dict
            error_message: Error details

        Returns:
            Created PendingReview model
        """
        # Parse suggested metadata from beets output
        suggested_artist = None
        suggested_album = None
        confidence = 0.0

        for line in beets_output.split("\n"):
            if "Artist:" in line:
                suggested_artist = line.split(":", 1)[1].strip()
            elif "Album:" in line:
                suggested_album = line.split(":", 1)[1].strip()
            elif "Similarity:" in line:
                import re
                match = re.search(r"(\d+\.?\d*)%", line)
                if match:
                    confidence = float(match.group(1)) / 100

        # Count tracks
        track_count = sum(1 for f in path.iterdir() if f.suffix.lower() in {".flac", ".mp3", ".m4a"})

        review = PendingReview(
            path=str(path),
            suggested_artist=suggested_artist,
            suggested_album=suggested_album,
            beets_confidence=confidence,
            track_count=track_count,
            quality_info=quality_info,
            source=source,
            status=PendingReviewStatus.PENDING,
            error_message=error_message
        )
        self.db.add(review)
        self.db.commit()

        return review

    def _get_or_create_artist(self, name: str, path: Path) -> Artist:
        """Find or create artist."""
        normalized = normalize_text(name)
        sort_name = self._normalize_sort_name(name)

        artist = self.db.query(Artist).filter(
            Artist.normalized_name == normalized
        ).first()

        if not artist:
            artist = Artist(
                name=name,
                normalized_name=normalized,
                sort_name=sort_name,
                path=str(path)
            )
            self.db.add(artist)
            self.db.flush()
        elif not artist.sort_name:
            artist.sort_name = sort_name
            self.db.add(artist)

        return artist

    def _normalize_sort_name(self, name: str) -> str:
        """Generate a sort-friendly name for artist ordering."""
        normalized = normalize_text(name)
        if normalized.startswith("the "):
            return normalized[4:]
        return normalized

    def _find_artwork(self, path: Path) -> Optional[str]:
        """Find album artwork in folder."""
        artwork_names = ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "artwork.jpg", "front.jpg"]
        for name in artwork_names:
            artwork_path = path / name
            if artwork_path.exists():
                return str(artwork_path)
        return None

    async def fetch_artwork_if_missing(self, album: Album) -> Optional[str]:
        """Fetch artwork for album if not present.

        Tries beets fetchart first, then embedded art extraction.

        Args:
            album: Album model to fetch artwork for

        Returns:
            Path to artwork file or None if not found
        """
        if not album.path:
            return None

        album_path = Path(album.path)
        if not album_path.exists():
            return None

        # Check if artwork already exists
        existing = self._find_artwork(album_path)
        if existing:
            return existing

        # Try beets fetchart
        try:
            from app.integrations.beets import BeetsClient
            beets = BeetsClient()
            artwork_path = await beets.fetch_artwork(album_path)
            if artwork_path:
                logger.info(f"Fetched artwork for {album.title}: {artwork_path}")
                return str(artwork_path)
        except Exception as e:
            logger.warning(f"Beets fetchart failed for {album.title}: {e}")

        # Try extracting embedded artwork from audio files
        try:
            artwork_path = await self._extract_embedded_artwork(album_path)
            if artwork_path:
                logger.info(f"Extracted embedded artwork for {album.title}: {artwork_path}")
                return str(artwork_path)
        except Exception as e:
            logger.warning(f"Embedded art extraction failed for {album.title}: {e}")

        logger.warning(f"No artwork found for {album.title}")
        return None

    async def _extract_embedded_artwork(self, album_path: Path) -> Optional[str]:
        """Extract embedded artwork from audio files.

        Args:
            album_path: Path to album folder

        Returns:
            Path to extracted cover.jpg or None
        """
        import asyncio

        audio_extensions = {".flac", ".mp3", ".m4a"}
        audio_files = [f for f in album_path.iterdir() if f.suffix.lower() in audio_extensions]

        if not audio_files:
            return None

        cover_path = album_path / "cover.jpg"

        # Try ffmpeg to extract artwork
        for audio_file in audio_files[:3]:  # Try first 3 files
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_file),
                "-an", "-vcodec", "copy",
                str(cover_path)
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await process.wait()

                if cover_path.exists() and cover_path.stat().st_size > 0:
                    return str(cover_path)
            except Exception:
                continue

        # Clean up empty file if created
        if cover_path.exists() and cover_path.stat().st_size == 0:
            cover_path.unlink()

        return None
