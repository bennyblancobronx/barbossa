"""Album import and duplicate detection service."""
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.import_history import ImportHistory
from app.models.pending_review import PendingReview, PendingReviewStatus
from app.utils.normalize import normalize_text
from app.integrations.exiftool import quality_score, format_quality
from app.services.quality import generate_checksum
from app.services.integrity import IntegrityService, IntegrityStatus

logger = logging.getLogger(__name__)


class ImportError(Exception):
    """Import operation failed."""
    pass


class MetadataValidationError(Exception):
    """Metadata failed validation - needs manual review."""
    def __init__(self, issues: list[str]):
        self.issues = issues
        super().__init__(f"Metadata validation failed: {', '.join(issues)}")


class DuplicateContentError(Exception):
    """Content duplicate detected via checksum comparison."""
    def __init__(self, existing_album: Album, matching_checksums: int, total_tracks: int):
        self.existing_album = existing_album
        self.matching_checksums = matching_checksums
        self.total_tracks = total_tracks
        super().__init__(
            f"Content duplicate: {matching_checksums}/{total_tracks} tracks match "
            f"'{existing_album.title}' by {existing_album.artist.name if existing_album.artist else 'Unknown'}"
        )


# Audio file extensions for checksum generation
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac", ".aac"}

# Patterns that indicate missing/bad metadata
INVALID_ARTIST_PATTERNS = [
    "unknown artist",
    "various artists",  # Only invalid if all tracks have same artist
    "unknown",
    "",
]

INVALID_TRACK_PATTERNS = [
    r"^track\s*\d+$",  # "Track 1", "Track 01", etc.
    r"^\d+$",  # Just a number
    r"^untitled",
    r"^unknown",
]


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

    def find_duplicate_by_checksum(self, checksums: list[str]) -> Optional[tuple[Album, int]]:
        """Find existing album containing tracks with matching checksums.

        Content-based deduplication catches exact copies regardless of metadata.
        If ANY track checksum matches, we've found the same album (or partial re-import).

        Args:
            checksums: List of BLAKE3 hashes of tracks being imported

        Returns:
            Tuple of (existing Album, count of matching tracks) if duplicate found,
            None otherwise
        """
        if not checksums:
            return None

        # Query for tracks with matching checksums
        matching_tracks = self.db.query(Track).filter(
            Track.checksum.in_(checksums),
            Track.checksum.isnot(None)
        ).all()

        if not matching_tracks:
            return None

        # Count matches per album to find the best match
        album_matches: dict[int, list[Track]] = {}
        for track in matching_tracks:
            if track.album_id not in album_matches:
                album_matches[track.album_id] = []
            album_matches[track.album_id].append(track)

        # Return album with most matching tracks
        best_album_id = max(album_matches, key=lambda k: len(album_matches[k]))
        best_album = self.db.query(Album).filter(Album.id == best_album_id).first()

        if best_album:
            return (best_album, len(album_matches[best_album_id]))

        return None

    def find_all_duplicate_tracks(self, checksums: list[str]) -> dict[str, Track]:
        """Find all existing tracks matching any of these checksums.

        Args:
            checksums: List of BLAKE3 hashes

        Returns:
            Dict mapping checksum -> existing Track
        """
        if not checksums:
            return {}

        matching = self.db.query(Track).filter(
            Track.checksum.in_(checksums),
            Track.checksum.isnot(None)
        ).all()

        return {t.checksum: t for t in matching}

    def generate_track_checksums(self, path: Path) -> list[tuple[Path, str]]:
        """Generate checksums for all audio files in a directory.

        Args:
            path: Path to album directory

        Returns:
            List of tuples (file_path, checksum) for all audio files
        """
        checksums = []
        audio_files = sorted([
            f for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        ])

        for audio_file in audio_files:
            try:
                checksum = generate_checksum(audio_file)
                checksums.append((audio_file, checksum))
            except Exception as e:
                logger.warning(f"Failed to generate checksum for {audio_file}: {e}")

        return checksums

    def validate_metadata(
        self,
        tracks_metadata: list[dict],
        folder_name: str,
        strict: bool = True
    ) -> tuple[bool, list[str]]:
        """Validate track metadata before import.

        Checks for:
        - Missing or invalid artist names
        - Generic track titles ("Track 1", "Track 01", etc.)
        - Album title that's just the folder name
        - Inconsistent metadata across tracks

        Args:
            tracks_metadata: List of track metadata from exiftool
            folder_name: Name of the album folder
            strict: If True, reject on any issue. If False, only reject critical issues.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        import re

        issues = []

        if not tracks_metadata:
            issues.append("No tracks found")
            return False, issues

        first_track = tracks_metadata[0]

        # Check artist
        artist = first_track.get("artist") or ""
        artist_lower = artist.lower().strip()

        is_comp = self._detect_compilation(tracks_metadata)
        if not artist or (artist_lower in INVALID_ARTIST_PATTERNS and not is_comp):
            issues.append(f"Invalid artist: '{artist or 'missing'}'")

        # Check album
        album = first_track.get("album") or ""
        if not album:
            issues.append("Missing album title")
        elif album == folder_name:
            # Album title is just the folder name - suspicious
            issues.append(f"Album title matches folder name (possibly missing tag): '{album}'")

        # Check track titles
        invalid_tracks = []
        missing_titles = 0
        for i, meta in enumerate(tracks_metadata):
            title = meta.get("title") or ""
            title_lower = title.lower().strip()

            if not title:
                missing_titles += 1
                continue

            # Check against invalid patterns
            for pattern in INVALID_TRACK_PATTERNS:
                if re.match(pattern, title_lower):
                    invalid_tracks.append(f"Track {i + 1}: '{title}'")
                    break

        if missing_titles > 0:
            issues.append(f"{missing_titles} tracks missing titles")

        if invalid_tracks:
            if len(invalid_tracks) <= 3:
                issues.append(f"Generic track names: {', '.join(invalid_tracks)}")
            else:
                issues.append(f"{len(invalid_tracks)} tracks have generic names (e.g., {invalid_tracks[0]})")

        # Check for consistency - all tracks should have same artist/album
        artists = set(m.get("artist") or "" for m in tracks_metadata)
        albums = set(m.get("album") or "" for m in tracks_metadata)

        if len(artists) > 1 and "" in artists:
            issues.append("Inconsistent artist metadata across tracks")

        if len(albums) > 1 and "" in albums:
            issues.append("Inconsistent album metadata across tracks")

        # Determine validity
        if strict:
            is_valid = len(issues) == 0
        else:
            # In non-strict mode, only fail on critical issues
            critical_issues = [
                i for i in issues
                if "Invalid artist" in i or "missing titles" in i
            ]
            is_valid = len(critical_issues) == 0

        return is_valid, issues

    async def import_album(
        self,
        path: Path,
        tracks_metadata: list[dict],
        source: str,
        source_url: str,
        imported_by: Optional[int] = None,
        confidence: float = 1.0,
        validate: bool = True,
        check_content_dupe: bool = True,
        verify_integrity: bool = True,
        enrich_on_import: bool = True
    ) -> Album:
        """Import album and tracks to database.

        Args:
            path: Path to album folder in library
            tracks_metadata: List of track metadata from exiftool
            source: Download source (qobuz, youtube, etc.)
            source_url: Original URL
            imported_by: User ID who triggered import
            confidence: Beets identification confidence
            validate: If True, validate metadata before import (default True)
            check_content_dupe: If True, check for content duplicates via checksum (default True)
            verify_integrity: If True, verify FLAC integrity before import (default True)
            enrich_on_import: If True, trigger lyrics enrichment after import (default True)

        Returns:
            Created Album model

        Raises:
            MetadataValidationError: If metadata fails validation
            DuplicateContentError: If content duplicate detected
            ImportError: If import fails (including integrity failures)
        """
        if not tracks_metadata:
            raise ImportError("No tracks found in album")

        first_track = tracks_metadata[0]

        # PHASE 5: Generate checksums FIRST, before any database operations
        # This enables content-based deduplication regardless of metadata
        track_checksums: list[tuple[Path, str]] = []
        if check_content_dupe:
            track_checksums = self.generate_track_checksums(path)
            checksums_only = [cs for _, cs in track_checksums]

            # Check for content duplicates FIRST (most reliable)
            content_dupe = self.find_duplicate_by_checksum(checksums_only)
            if content_dupe:
                existing_album, match_count = content_dupe
                logger.info(
                    f"Content duplicate found: {match_count}/{len(track_checksums)} tracks "
                    f"match existing album '{existing_album.title}'"
                )
                # Raise exception to let caller decide (replace with better quality, skip, etc.)
                raise DuplicateContentError(existing_album, match_count, len(track_checksums))

        # PHASE 6: Verify file integrity before import
        # Uses flac -t for FLAC files, logs warnings for issues
        if verify_integrity:
            integrity_service = IntegrityService()
            integrity_result = await integrity_service.verify_album(path)

            if integrity_result.failed > 0:
                # Critical: files are corrupted
                failed_files = [r.path.name for r in integrity_result.results if r.status == IntegrityStatus.FAILED]
                raise ImportError(
                    f"Integrity check failed for {integrity_result.failed} file(s): {', '.join(failed_files[:3])}"
                    + (f" and {len(failed_files) - 3} more" if len(failed_files) > 3 else "")
                )

            if integrity_result.errors > 0:
                # flac command not installed or other error - log but continue
                logger.warning(
                    f"Integrity check had {integrity_result.errors} error(s) for {path.name} - "
                    "install 'flac' package for full verification"
                )

            if integrity_result.no_md5 > 0:
                # INT-004: Qobuz files lack embedded MD5 - this is normal, not an error
                logger.debug(
                    f"Album {path.name}: {integrity_result.no_md5}/{integrity_result.total_files} "
                    "FLAC files have no embedded MD5 (typical for Qobuz)"
                )

            if integrity_result.verified > 0:
                logger.info(
                    f"Integrity verified: {integrity_result.verified}/{integrity_result.total_files} files OK"
                )

        # Validate metadata before proceeding
        if validate:
            is_valid, issues = self.validate_metadata(
                tracks_metadata,
                folder_name=path.name,
                strict=True
            )
            if not is_valid:
                logger.warning(f"Metadata validation failed for {path.name}: {issues}")
                raise MetadataValidationError(issues)

        # Find or create artist - validation passed, so we know artist is valid
        artist_name = first_track.get("artist")
        is_comp = self._detect_compilation(tracks_metadata)
        if not artist_name or (artist_name.lower().strip() in INVALID_ARTIST_PATTERNS and not is_comp):
            # This shouldn't happen if validation is on, but be safe
            raise ImportError(f"Invalid artist name: '{artist_name}'")

        # Substitute artist name for compilations with generic artist
        if is_comp and artist_name and artist_name.lower().strip() in INVALID_ARTIST_PATTERNS:
            album_title_check = (first_track.get("album") or "").lower()
            release_type = (first_track.get("release_type") or "").lower()
            if "soundtrack" in album_title_check or release_type == "soundtrack":
                artist_name = "Soundtrack"
            else:
                artist_name = "Compilations"

        artist = self._get_or_create_artist(
            artist_name,
            path.parent,
            musicbrainz_id=first_track.get("musicbrainz_artist_id"),
            country=first_track.get("artist_country")
        )

        # Determine album title
        album_title = first_track.get("album") or path.name
        normalized_title = normalize_text(album_title)

        # Find artwork
        artwork_path = self._find_artwork(path)

        # Calculate disc count and detect compilation
        disc_count = self._calculate_disc_count(tracks_metadata)
        is_compilation = self._detect_compilation(tracks_metadata)

        # Create album with full metadata
        album = Album(
            artist_id=artist.id,
            title=album_title,
            normalized_title=normalized_title,
            year=first_track.get("year"),
            path=str(path),
            artwork_path=artwork_path,
            total_tracks=len(tracks_metadata),
            available_tracks=len(tracks_metadata),
            disc_count=disc_count,
            source=source,
            source_url=source_url,
            # Extended metadata from exiftool/beets
            genre=first_track.get("genre"),
            label=first_track.get("label"),
            catalog_number=first_track.get("catalog_number"),
            musicbrainz_id=first_track.get("musicbrainz_album_id"),
            is_compilation=is_compilation,
            # Phase 7: UPC from Qobuz API
            upc=first_track.get("upc"),
        )
        self.db.add(album)
        self.db.flush()

        # Build checksum lookup map from pre-computed values (Phase 5)
        checksum_map = {str(fp): cs for fp, cs in track_checksums} if track_checksums else {}

        # Create tracks
        for i, meta in enumerate(tracks_metadata):
            # Get track title - validation should have caught missing titles
            track_title = meta.get("title")
            if not track_title:
                if validate:
                    # This shouldn't happen if validation passed
                    logger.error(f"Track {i + 1} missing title despite validation")
                track_title = f"Track {i + 1}"  # Fallback for validate=False mode
                logger.warning(f"Using fallback title '{track_title}' for {path.name}")

            track = Track(
                album_id=album.id,
                title=track_title,
                normalized_title=normalize_text(track_title),
                track_number=meta.get("track_number") or (i + 1),
                disc_number=meta.get("disc_number") or 1,
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
                imported_by=imported_by,
                # Extended metadata
                lyrics=meta.get("lyrics"),
                isrc=meta.get("isrc"),
                composer=meta.get("composer"),
                explicit=meta.get("explicit", False),
                musicbrainz_id=meta.get("musicbrainz_track_id"),
            )
            self.db.add(track)
            self.db.flush()

            # Use pre-computed checksum if available, otherwise generate on the fly
            track_path = Path(track.path)
            if checksum_map:
                track.checksum = checksum_map.get(str(track_path))
            elif track_path.exists():
                # Fallback: generate if not pre-computed (check_content_dupe=False case)
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

        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            # Race condition - another process inserted the same album
            if 'uq_album_artist_title' in str(e.orig):
                logger.info(f"Duplicate album detected via constraint: {album_title} by {artist.name}")
                existing = self.find_duplicate(
                    first_track.get("artist") or "Unknown Artist",
                    album_title
                )
                if existing:
                    return existing
            raise ImportError(f"Database error during import: {e}")

        # PHASE 8: Trigger lyrics enrichment if enabled
        # Only for tracks that don't already have embedded lyrics
        if enrich_on_import:
            tracks_missing_lyrics = sum(
                1 for meta in tracks_metadata
                if not meta.get("lyrics")
            )
            if tracks_missing_lyrics > 0:
                try:
                    from app.tasks.enrichment import enrich_album_lyrics_task
                    enrich_album_lyrics_task.delay(album.id)
                    logger.info(
                        f"Triggered lyrics enrichment for album {album.id} "
                        f"({tracks_missing_lyrics} tracks missing lyrics)"
                    )
                except Exception as e:
                    # Don't fail import if enrichment task fails to queue
                    logger.warning(f"Failed to queue enrichment task: {e}")

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

        # Update album metadata
        first_track = tracks_metadata[0] if tracks_metadata else {}
        album.path = str(new_path)
        album.artwork_path = self._find_artwork(new_path)
        album.total_tracks = len(tracks_metadata)
        album.available_tracks = len(tracks_metadata)
        album.disc_count = self._calculate_disc_count(tracks_metadata)
        # Update extended metadata if not already set
        if not album.genre and first_track.get("genre"):
            album.genre = first_track.get("genre")
        if not album.label and first_track.get("label"):
            album.label = first_track.get("label")
        if not album.musicbrainz_id and first_track.get("musicbrainz_album_id"):
            album.musicbrainz_id = first_track.get("musicbrainz_album_id")
        # Phase 7: UPC from Qobuz API
        if not album.upc and first_track.get("upc"):
            album.upc = first_track.get("upc")

        # Add new tracks
        for i, meta in enumerate(tracks_metadata):
            track = Track(
                album_id=album.id,
                title=meta.get("title") or f"Track {i + 1}",
                normalized_title=normalize_text(meta.get("title") or f"Track {i + 1}"),
                track_number=meta.get("track_number") or (i + 1),
                disc_number=meta.get("disc_number") or 1,
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
                ),
                # Extended metadata
                lyrics=meta.get("lyrics"),
                isrc=meta.get("isrc"),
                composer=meta.get("composer"),
                explicit=meta.get("explicit", False),
                musicbrainz_id=meta.get("musicbrainz_track_id"),
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

    def _get_or_create_artist(
        self,
        name: str,
        path: Path,
        musicbrainz_id: str = None,
        biography: str = None,
        country: str = None
    ) -> Artist:
        """Find or create artist with metadata.

        If artist exists, updates missing metadata fields.

        Args:
            name: Artist name
            path: Path to artist folder
            musicbrainz_id: Optional MusicBrainz artist ID
            biography: Optional artist biography
            country: Optional ISO 3166-1 alpha-2 country code
        """
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
                path=str(path),
                musicbrainz_id=musicbrainz_id,
                biography=biography,
                country=country,
            )
            self.db.add(artist)
            self.db.flush()
        else:
            # Update with new metadata if missing
            updated = False
            if not artist.sort_name:
                artist.sort_name = sort_name
                updated = True
            if musicbrainz_id and not artist.musicbrainz_id:
                artist.musicbrainz_id = musicbrainz_id
                updated = True
            if biography and not artist.biography:
                artist.biography = biography
                updated = True
            if country and not artist.country:
                artist.country = country
                updated = True
            if updated:
                self.db.add(artist)

        return artist

    def _normalize_sort_name(self, name: str) -> str:
        """Generate a sort-friendly name for artist ordering."""
        normalized = normalize_text(name)
        if normalized.startswith("the "):
            return normalized[4:]
        return normalized

    def _calculate_disc_count(self, tracks_metadata: list[dict]) -> int:
        """Calculate disc count from track metadata.

        Returns the maximum disc number found, defaulting to 1.
        """
        disc_numbers = set()
        for meta in tracks_metadata:
            disc = meta.get("disc_number") or 1
            disc_numbers.add(disc)
        return max(disc_numbers) if disc_numbers else 1

    def _detect_compilation(self, tracks_metadata: list[dict]) -> bool:
        """Detect if album is a compilation (various artists).

        An album is considered a compilation if:
        1. Explicitly marked as compilation in metadata
        2. Has more than 3 unique non-empty artist names

        Returns True if compilation detected.
        """
        # Check if any track is explicitly marked as compilation
        for meta in tracks_metadata:
            if meta.get("is_compilation"):
                return True

        # Count unique artists (excluding empty/generic)
        artists = set()
        generic_artists = {"various artists", "va", "various", ""}
        for meta in tracks_metadata:
            artist = (meta.get("artist") or "").lower().strip()
            if artist and artist not in generic_artists:
                artists.add(artist)

        # More than 3 unique artists suggests a compilation
        return len(artists) > 3

    def compare_duplicate_quality(
        self,
        new_path: Path,
        existing_album: Album
    ) -> dict:
        """Compare quality of new import vs existing album.

        Used when DuplicateContentError is raised to help callers decide
        whether to replace the existing album with a higher quality version.

        Args:
            new_path: Path to the new album being imported
            existing_album: Existing album found via checksum match

        Returns:
            Dict with comparison result:
            - action: "replace" (new is better), "skip" (existing is better/same), "review" (unclear)
            - new_quality: Quality info for new files
            - existing_quality: Quality info for existing files
            - reason: Human-readable explanation
        """
        from app.services.quality import QualityService

        quality_service = QualityService()

        # Get first audio file from new import
        new_audio_files = [
            f for f in new_path.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        ]
        if not new_audio_files:
            return {
                "action": "skip",
                "new_quality": None,
                "existing_quality": None,
                "reason": "No audio files in new import"
            }

        # Get first track from existing album
        existing_track = existing_album.tracks[0] if existing_album.tracks else None
        if not existing_track or not existing_track.path:
            return {
                "action": "replace",
                "new_quality": None,
                "existing_quality": None,
                "reason": "Existing album has no valid tracks"
            }

        existing_path = Path(existing_track.path)
        if not existing_path.exists():
            return {
                "action": "replace",
                "new_quality": None,
                "existing_quality": None,
                "reason": "Existing track file not found"
            }

        # Extract quality from both
        new_quality = quality_service.extract(new_audio_files[0])
        existing_quality = quality_service.extract(existing_path)

        if not new_quality or not existing_quality:
            return {
                "action": "review",
                "new_quality": quality_service.quality_display(new_quality) if new_quality else None,
                "existing_quality": quality_service.quality_display(existing_quality) if existing_quality else None,
                "reason": "Could not extract quality from one or both albums"
            }

        # Compare quality
        if quality_service.is_better_quality(new_quality, existing_quality):
            return {
                "action": "replace",
                "new_quality": quality_service.quality_display(new_quality),
                "existing_quality": quality_service.quality_display(existing_quality),
                "reason": f"New quality ({quality_service.quality_display(new_quality)}) is better than existing ({quality_service.quality_display(existing_quality)})"
            }
        elif quality_service.is_better_quality(existing_quality, new_quality):
            return {
                "action": "skip",
                "new_quality": quality_service.quality_display(new_quality),
                "existing_quality": quality_service.quality_display(existing_quality),
                "reason": f"Existing quality ({quality_service.quality_display(existing_quality)}) is better than new ({quality_service.quality_display(new_quality)})"
            }
        else:
            return {
                "action": "skip",
                "new_quality": quality_service.quality_display(new_quality),
                "existing_quality": quality_service.quality_display(existing_quality),
                "reason": f"Same quality ({quality_service.quality_display(new_quality)}), keeping existing"
            }

    def _find_artwork(self, path: Path) -> Optional[str]:
        """Find album artwork in folder, extracting from audio files if needed.

        Checks for existing artwork files first, then tries to extract
        embedded artwork from FLAC/MP3 files if no file exists.
        """
        # Check for existing artwork files
        artwork_names = ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "artwork.jpg", "front.jpg"]
        for name in artwork_names:
            artwork_path = path / name
            if artwork_path.exists():
                return str(artwork_path)

        # Try to extract embedded artwork from audio files (Qobuz embeds art in FLAC)
        extracted = self._extract_embedded_artwork_sync(path)
        if extracted:
            return extracted

        return None

    def _extract_embedded_artwork_sync(self, album_path: Path) -> Optional[str]:
        """Extract embedded artwork from audio files (synchronous version).

        Uses ffmpeg to extract cover art embedded in FLAC/MP3 files.
        Qobuz downloads embed high-quality artwork in the audio files.

        Args:
            album_path: Path to album folder

        Returns:
            Path to extracted cover.jpg or None
        """
        import subprocess

        audio_extensions = {".flac", ".mp3", ".m4a"}
        audio_files = [f for f in album_path.iterdir() if f.suffix.lower() in audio_extensions]

        if not audio_files:
            return None

        cover_path = album_path / "cover.jpg"

        # Try ffmpeg to extract artwork from first few files
        for audio_file in audio_files[:3]:
            cmd = [
                "ffmpeg", "-y", "-i", str(audio_file),
                "-an", "-vcodec", "copy",
                str(cover_path)
            ]

            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30
                )

                if cover_path.exists() and cover_path.stat().st_size > 0:
                    logger.info(f"Extracted embedded artwork from {audio_file.name}")
                    return str(cover_path)
            except subprocess.TimeoutExpired:
                logger.warning(f"ffmpeg timeout extracting artwork from {audio_file}")
            except Exception as e:
                logger.debug(f"Failed to extract artwork from {audio_file}: {e}")

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

    async def fetch_artist_image_from_qobuz(self, artist: Artist, artist_name: str) -> Optional[str]:
        """Fetch artist image and biography from Qobuz API.

        Updates artist with:
        - Image (saved to disk)
        - Biography (stored in database)

        Args:
            artist: Artist model
            artist_name: Artist name to search

        Returns:
            Path to saved artist image or None
        """
        import httpx

        # Skip if we already have both image and biography
        has_image = artist.artwork_path and Path(artist.artwork_path).exists()
        has_bio = bool(artist.biography)
        if has_image and has_bio:
            return artist.artwork_path

        try:
            from app.integrations.qobuz_api import get_qobuz_api

            qobuz = get_qobuz_api()
            artists = await qobuz.search_artists(artist_name, limit=1)

            if not artists:
                logger.debug(f"No Qobuz artist found for: {artist_name}")
                return None

            qobuz_artist = artists[0]

            # Store biography if not already set
            if not artist.biography and qobuz_artist.get("biography"):
                artist.biography = qobuz_artist["biography"]
                logger.info(f"Stored Qobuz biography for: {artist_name}")

            # Skip image download if already exists
            if has_image:
                self.db.commit()
                return artist.artwork_path

            image_url = qobuz_artist.get("image_large") or qobuz_artist.get("image_medium")

            if not image_url:
                logger.debug(f"No image URL for Qobuz artist: {artist_name}")
                # Still commit biography if it was updated
                self.db.commit()
                return None

            # Determine artist folder
            if artist.path and Path(artist.path).exists():
                artist_path = Path(artist.path)
            else:
                from app.config import settings
                artist_path = Path(settings.music_library) / artist.name
                artist_path.mkdir(parents=True, exist_ok=True)
                artist.path = str(artist_path)

            artwork_path = artist_path / "artist.jpg"

            # Download image
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url)
                if response.status_code == 200:
                    with open(artwork_path, "wb") as f:
                        f.write(response.content)

                    artist.artwork_path = str(artwork_path)
                    self.db.commit()
                    logger.info(f"Downloaded Qobuz artist image for: {artist_name}")
                    return str(artwork_path)

        except Exception as e:
            logger.warning(f"Failed to fetch Qobuz artist data for {artist_name}: {e}")

        return None

    async def auto_heart_for_followers(self, album: Album) -> int:
        """Auto-heart album for users following the artist.

        When a new album is imported, automatically add it to the libraries
        of users who have hearted the artist with auto_add_new=True.

        Args:
            album: Newly imported album

        Returns:
            Count of users who received the album
        """
        from app.services.user_library import UserLibraryService
        from app.websocket import notify_user

        user_lib = UserLibraryService(self.db)
        followers = user_lib.get_users_following_artist(album.artist_id)

        if not followers:
            return 0

        count = 0
        for user_id, username in followers:
            try:
                if user_lib.heart_album(user_id, album.id, username):
                    count += 1
                    logger.info(f"Auto-hearted album {album.id} for user {username}")
                    # Notify user via WebSocket
                    try:
                        await notify_user(user_id, {
                            "title": "New Album Added",
                            "message": f"'{album.title}' by {album.artist.name} added to your library",
                            "album_id": album.id,
                            "artist_id": album.artist_id
                        })
                    except Exception as ws_error:
                        logger.debug(f"WebSocket notification failed for user {user_id}: {ws_error}")
            except Exception as e:
                logger.warning(f"Failed to auto-heart album {album.id} for user {user_id}: {e}")

        return count
