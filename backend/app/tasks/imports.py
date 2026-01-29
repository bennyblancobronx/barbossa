"""Import tasks for Celery."""
import asyncio
import logging
from pathlib import Path
from celery import shared_task

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Audio file extensions
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac"}


def merge_beets_identification(
    tracks_metadata: list[dict],
    identification: dict
) -> list[dict]:
    """Merge beets identification data with ExifTool metadata.

    Beets/MusicBrainz is authoritative for MusicBrainz IDs and ISRC codes.
    ExifTool is authoritative for audio quality and embedded lyrics/composer.
    """
    # Merge album-level data into first track
    if tracks_metadata:
        first_track = tracks_metadata[0]

        if identification.get("musicbrainz_album_id") and not first_track.get("musicbrainz_album_id"):
            first_track["musicbrainz_album_id"] = identification["musicbrainz_album_id"]

        if identification.get("musicbrainz_artist_id") and not first_track.get("musicbrainz_artist_id"):
            first_track["musicbrainz_artist_id"] = identification["musicbrainz_artist_id"]

        if identification.get("label") and not first_track.get("label"):
            first_track["label"] = identification["label"]

        if identification.get("catalog_number") and not first_track.get("catalog_number"):
            first_track["catalog_number"] = identification["catalog_number"]

        # Year from beets/MusicBrainz
        if identification.get("year") and not first_track.get("year"):
            first_track["year"] = identification["year"]

        # Artist country from MusicBrainz (ISO 3166-1 alpha-2)
        if identification.get("country") and not first_track.get("artist_country"):
            first_track["artist_country"] = identification["country"]

    # Merge track-level MusicBrainz data
    beets_tracks = identification.get("track_data") or []
    for meta in tracks_metadata:
        track_num = meta.get("track_number")
        disc_num = meta.get("disc_number", 1)

        beets_track = next(
            (t for t in beets_tracks
             if t.get("track_number") == track_num
             and t.get("disc_number", 1) == disc_num),
            None
        )

        if beets_track:
            if beets_track.get("musicbrainz_track_id") and not meta.get("musicbrainz_track_id"):
                meta["musicbrainz_track_id"] = beets_track["musicbrainz_track_id"]
            if beets_track.get("isrc") and not meta.get("isrc"):
                meta["isrc"] = beets_track["isrc"]

    return tracks_metadata


@shared_task(name="app.tasks.imports.scan_import_folder")
def scan_import_folder():
    """Scan import pending folder for new albums.

    This is a scheduled task that runs periodically to catch any
    albums that might have been missed by the watch folder service.
    """
    pending_path = Path(settings.music_import) / "pending"

    if not pending_path.exists():
        return {"scanned": 0, "found": 0}

    albums_found = []

    for folder in pending_path.iterdir():
        if not folder.is_dir():
            continue

        has_audio = any(
            f.suffix.lower() in AUDIO_EXTENSIONS
            for f in folder.iterdir()
            if f.is_file()
        )

        if has_audio:
            albums_found.append(str(folder))
            # Trigger import task
            process_import.delay(str(folder))

    logger.info(f"Scan found {len(albums_found)} albums to import")

    return {
        "scanned": len(list(pending_path.iterdir())),
        "found": len(albums_found)
    }


@shared_task(
    name="app.tasks.imports.process_import",
    bind=True,
    max_retries=2,
    default_retry_delay=300
)
def process_import(self, folder_path: str):
    """Process a single import folder.

    Args:
        folder_path: Path to album folder to import
    """

    async def run():
        from app.integrations.beets import BeetsClient
        from app.integrations.exiftool import ExifToolClient
        from app.services.import_service import ImportService, DuplicateContentError
        from app.integrations.plex import trigger_plex_scan
        from app.websocket import broadcast_import_complete, broadcast_review_needed, broadcast_library_update

        folder = Path(folder_path)

        if not folder.exists():
            return {"status": "not_found", "path": folder_path}

        db = SessionLocal()
        try:
            beets = BeetsClient()
            exiftool = ExifToolClient()
            import_service = ImportService(db)

            # Identify via beets
            identification = await beets.identify(folder)
            confidence = identification.get("confidence", 0)

            logger.info(
                f"Identified: {identification.get('artist')} - "
                f"{identification.get('album')} (confidence: {confidence:.0%})"
            )

            # Minimum confidence for auto-import
            if confidence < 0.85:
                # Move to review
                review_path = Path(settings.music_import) / "review" / folder.name
                if review_path.exists():
                    import shutil
                    counter = 1
                    while review_path.exists():
                        review_path = Path(settings.music_import) / "review" / f"{folder.name}_{counter}"
                        counter += 1

                import shutil
                shutil.move(str(folder), str(review_path))

                # Create review entry
                from app.models.pending_review import PendingReview
                tracks_metadata = await exiftool.get_album_metadata(review_path)
                quality_info = None
                if tracks_metadata:
                    first = tracks_metadata[0]
                    quality_info = {
                        "sample_rate": first.get("sample_rate"),
                        "bit_depth": first.get("bit_depth"),
                        "format": first.get("format")
                    }
                file_count = len([
                    f for f in review_path.iterdir()
                    if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
                ])

                review = PendingReview(
                    path=str(review_path),
                    suggested_artist=identification.get("artist"),
                    suggested_album=identification.get("album"),
                    suggested_year=identification.get("year"),
                    beets_confidence=confidence,
                    track_count=file_count,
                    quality_info=quality_info,
                    source="import",
                    source_url="",
                    status="pending"
                )
                db.add(review)
                db.commit()

                await broadcast_review_needed(
                    review_id=review.id,
                    path=str(review_path),
                    suggested_artist=identification.get("artist"),
                    suggested_album=identification.get("album"),
                    confidence=confidence
                )

                return {"status": "review", "confidence": confidence, "review_id": review.id}

            # Pre-validate metadata before import
            tracks_metadata_raw = await exiftool.get_album_metadata(folder)
            is_valid, issues = import_service.validate_metadata(
                tracks_metadata_raw,
                folder_name=folder.name,
                strict=True
            )

            if not is_valid:
                logger.info(f"Metadata validation failed: {issues}")
                # Move to review with validation failure note
                review_path = Path(settings.music_import) / "review" / folder.name
                if review_path.exists():
                    counter = 1
                    while review_path.exists():
                        review_path = Path(settings.music_import) / "review" / f"{folder.name}_{counter}"
                        counter += 1

                shutil.move(str(folder), str(review_path))

                from app.models.pending_review import PendingReview
                quality_info = None
                if tracks_metadata_raw:
                    first = tracks_metadata_raw[0]
                    quality_info = {
                        "sample_rate": first.get("sample_rate"),
                        "bit_depth": first.get("bit_depth"),
                        "format": first.get("format")
                    }
                file_count = len([
                    f for f in review_path.iterdir()
                    if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
                ])

                review = PendingReview(
                    path=str(review_path),
                    suggested_artist=identification.get("artist"),
                    suggested_album=identification.get("album"),
                    suggested_year=identification.get("year"),
                    beets_confidence=confidence,
                    track_count=file_count,
                    quality_info=quality_info,
                    source="import",
                    source_url="",
                    status="pending",
                    notes=f"Metadata validation failed: {'; '.join(issues)}"
                )
                db.add(review)
                db.commit()

                await broadcast_review_needed(
                    review_id=review.id,
                    path=str(review_path),
                    suggested_artist=identification.get("artist"),
                    suggested_album=identification.get("album"),
                    confidence=confidence
                )

                return {"status": "review", "reason": "validation_failed", "issues": issues, "review_id": review.id}

            # Check duplicates - use artist from metadata if beets didn't identify
            artist = identification.get("artist") or (
                tracks_metadata_raw[0].get("artist") if tracks_metadata_raw else ""
            )
            existing = import_service.find_duplicate(
                artist,
                identification.get("album", "")
            )

            if existing:
                return {"status": "duplicate", "existing_id": existing.id}

            # Import
            library_path = await beets.import_album(folder, move=True)
            tracks_metadata = await exiftool.get_album_metadata(library_path)
            # Merge MusicBrainz data from beets identification
            tracks_metadata = merge_beets_identification(tracks_metadata, identification)

            try:
                album = await import_service.import_album(
                    path=library_path,
                    tracks_metadata=tracks_metadata,
                    source="import",
                    source_url="",
                    confidence=confidence,
                    validate=False  # Already validated above
                )
            except DuplicateContentError as e:
                # Content-based duplicate detected via checksum matching
                logger.info(
                    f"Content duplicate: {e.matching_checksums}/{e.total_tracks} tracks "
                    f"match existing album '{e.existing_album.title}' (ID: {e.existing_album.id})"
                )
                return {
                    "status": "duplicate",
                    "existing_id": e.existing_album.id,
                    "reason": f"content_match ({e.matching_checksums}/{e.total_tracks} tracks)"
                }

            # Fetch artwork if missing
            if not album.artwork_path:
                artwork = await import_service.fetch_artwork_if_missing(album)
                if artwork:
                    album.artwork_path = artwork
                    db.commit()
                    logger.info(f"Added artwork for {album.title}")

            # Trigger Plex scan
            await trigger_plex_scan(str(library_path.parent))

            # Broadcast import complete
            await broadcast_import_complete(
                album_id=album.id,
                album_title=album.title,
                artist_name=album.artist.name,
                source="import"
            )

            # Broadcast library update for UI refresh
            await broadcast_library_update("album", album.id, "created")

            # Auto-heart for users following this artist
            auto_hearted = await import_service.auto_heart_for_followers(album)
            if auto_hearted > 0:
                logger.info(f"Auto-hearted album {album.id} for {auto_hearted} users")

            return {"status": "imported", "album_id": album.id}

        finally:
            db.close()

    try:
        return asyncio.run(run())
    except Exception as e:
        logger.error(f"Import task failed: {e}")
        raise self.retry(exc=e)


@shared_task(name="app.tasks.imports.process_review")
def process_review(review_id: int, action: str, metadata: dict = None):
    """Process a review queue item.

    Args:
        review_id: ID of pending review
        action: approve, reject, or manual
        metadata: Override metadata for manual import
    """
    from app.models.pending_review import PendingReview

    db = SessionLocal()

    try:
        review = db.query(PendingReview).filter(PendingReview.id == review_id).first()

        if not review:
            return {"status": "not_found", "review_id": review_id}

        folder = Path(review.path)

        if not folder.exists():
            review.status = "rejected"
            review.notes = "Folder not found"
            db.commit()
            return {"status": "not_found", "path": review.path}

        if action == "reject":
            # Move to rejected folder
            rejected_path = Path(settings.music_import) / "rejected" / folder.name
            rejected_path.parent.mkdir(parents=True, exist_ok=True)

            import shutil
            shutil.move(str(folder), str(rejected_path))

            review.status = "rejected"
            review.path = str(rejected_path)
            db.commit()

            return {"status": "rejected", "review_id": review_id}

        # Process import (approve or manual)
        library_path = None  # Track for rollback

        async def run():
            nonlocal library_path
            from app.integrations.beets import BeetsClient
            from app.integrations.exiftool import ExifToolClient
            from app.services.import_service import ImportService, DuplicateContentError
            from app.integrations.plex import trigger_plex_scan
            from app.websocket import broadcast_import_complete, broadcast_library_update
            from app.config import settings

            beets = BeetsClient()
            exiftool = ExifToolClient()
            import_service = ImportService(db)

            # Get MusicBrainz identification data before import
            identification = await beets.identify(folder)

            if action == "manual" and metadata:
                # Import with manual metadata
                library_path = await beets.import_with_metadata(
                    folder,
                    artist=metadata.get("artist", "Unknown Artist"),
                    album=metadata.get("album", "Unknown Album"),
                    year=metadata.get("year"),
                    move=True
                )
            else:
                # Use beets suggestion
                library_path = await beets.import_album(folder, move=True)

            tracks_metadata = await exiftool.get_album_metadata(library_path)
            # Merge MusicBrainz data from beets identification
            tracks_metadata = merge_beets_identification(tracks_metadata, identification)

            try:
                album = await import_service.import_album(
                    path=library_path,
                    tracks_metadata=tracks_metadata,
                    source="import",
                    source_url="",
                    confidence=1.0  # Manual review = full confidence
                )
            except DuplicateContentError as e:
                # Content-based duplicate detected via checksum matching
                logger.info(
                    f"Content duplicate: {e.matching_checksums}/{e.total_tracks} tracks "
                    f"match existing album '{e.existing_album.title}' (ID: {e.existing_album.id})"
                )
                review.status = "duplicate"
                review.notes = f"Content duplicate: {e.matching_checksums}/{e.total_tracks} tracks match album ID {e.existing_album.id}"
                db.commit()
                return {
                    "status": "duplicate",
                    "existing_id": e.existing_album.id,
                    "reason": f"content_match ({e.matching_checksums}/{e.total_tracks} tracks)"
                }

            # Fetch artwork if missing
            if not album.artwork_path:
                artwork = await import_service.fetch_artwork_if_missing(album)
                if artwork:
                    album.artwork_path = artwork

            # Update review record
            review.status = "approved"
            db.commit()

            # Trigger Plex scan
            await trigger_plex_scan(str(library_path.parent))

            # Broadcast import complete
            await broadcast_import_complete(
                album_id=album.id,
                album_title=album.title,
                artist_name=album.artist.name,
                source="import"
            )

            # Broadcast library update for UI refresh
            await broadcast_library_update("album", album.id, "created")

            # Auto-heart for users following this artist
            auto_hearted = await import_service.auto_heart_for_followers(album)
            if auto_hearted > 0:
                logger.info(f"Auto-hearted album {album.id} for {auto_hearted} users")

            return {"status": "imported", "album_id": album.id}

        try:
            return asyncio.run(run())
        except Exception as e:
            logger.error(f"Review processing failed: {e}")

            # Mark review as FAILED, not pending - prevents retry with already-moved files
            from datetime import datetime
            review.status = "failed"
            review.error_message = str(e)[:500]  # Truncate long errors
            review.reviewed_at = datetime.utcnow()

            # Try to move files to failed folder for manual recovery
            if library_path and library_path.exists():
                try:
                    from app.config import settings
                    failed_dir = Path(settings.music_import) / "failed"
                    failed_dir.mkdir(parents=True, exist_ok=True)
                    failed_path = failed_dir / library_path.name
                    counter = 1
                    while failed_path.exists():
                        failed_path = failed_dir / f"{library_path.name}_{counter}"
                        counter += 1
                    shutil.move(str(library_path), str(failed_path))
                    review.path = str(failed_path)
                    logger.info(f"Moved failed import to: {failed_path}")
                except Exception as move_error:
                    logger.error(f"Could not move failed files: {move_error}")

            db.commit()
            return {"status": "failed", "error": str(e)}

    finally:
        db.close()
