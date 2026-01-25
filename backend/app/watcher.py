"""Watch folder service for automatic imports.

Run as standalone process: python -m app.watcher
"""
import asyncio
import logging
import shutil
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, DirCreatedEvent

from app.config import settings
from app.database import SessionLocal
from app.services.import_service import ImportService
from app.integrations.beets import BeetsClient
from app.integrations.exiftool import ExifToolClient
from app.integrations.plex import trigger_plex_scan
from app.websocket import broadcast_import_complete, broadcast_review_needed

logger = logging.getLogger(__name__)

# Audio file extensions
AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac"}


class ImportWatcher(FileSystemEventHandler):
    """Watches import folder for new albums."""

    def __init__(self):
        self.pending_path = Path(settings.music_import) / "pending"
        self.review_path = Path(settings.music_import) / "review"
        self.processing = set()  # Paths currently being processed
        self.debounce_seconds = 30  # Wait for folder to be complete
        self.auto_import_confidence = 0.85  # Minimum confidence for auto-import

        # Create directories if needed
        self.pending_path.mkdir(parents=True, exist_ok=True)
        self.review_path.mkdir(parents=True, exist_ok=True)

    def on_created(self, event):
        """Handle new file/folder creation."""
        if isinstance(event, DirCreatedEvent):
            # New folder - potential album
            # Schedule async processing
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda: asyncio.create_task(self._process_folder(event.src_path))
            )

    async def _process_folder(self, path: str):
        """Process new folder after debounce."""
        folder = Path(path)

        # Skip if already processing
        if str(folder) in self.processing:
            return

        self.processing.add(str(folder))

        try:
            # Wait for folder to stabilize (files still copying)
            await asyncio.sleep(self.debounce_seconds)

            # Check if it has audio files
            audio_files = [
                f for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
            ]

            if not audio_files:
                logger.debug(f"No audio files in {folder}, skipping")
                return

            logger.info(f"Processing new album folder: {folder}")

            # Process import
            await self._import_album(folder)

        except Exception as e:
            logger.error(f"Error processing {folder}: {e}")
        finally:
            self.processing.discard(str(folder))

    async def _import_album(self, folder: Path):
        """Attempt to import album automatically."""
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

            # High confidence - auto import
            if confidence >= self.auto_import_confidence:
                # Check for duplicates
                existing = import_service.find_duplicate(
                    identification.get("artist", ""),
                    identification.get("album", "")
                )

                if existing:
                    logger.info(f"Duplicate found: album ID {existing.id}")
                    await self._move_to_review(
                        folder,
                        identification,
                        f"Duplicate of album ID {existing.id}"
                    )
                    return

                # Import
                library_path = await beets.import_album(folder, move=True)
                tracks_metadata = await exiftool.get_album_metadata(library_path)

                album = await import_service.import_album(
                    path=library_path,
                    tracks_metadata=tracks_metadata,
                    source="import",
                    source_url="",
                    confidence=confidence
                )

                logger.info(f"Imported album ID {album.id}: {album.title}")

                # Trigger Plex scan
                await trigger_plex_scan(str(library_path.parent))

                # Broadcast completion
                await broadcast_import_complete(
                    album_id=album.id,
                    album_title=album.title,
                    artist_name=album.artist.name,
                    source="import"
                )

            else:
                # Low confidence - move to review
                logger.info(f"Low confidence ({confidence:.0%}), moving to review")
                await self._move_to_review(folder, identification)

        except Exception as e:
            logger.error(f"Import error for {folder}: {e}")
            # Move to review on error
            await self._move_to_review(
                folder,
                {"confidence": 0},
                f"Import error: {str(e)}"
            )
        finally:
            db.close()

    async def _move_to_review(
        self,
        folder: Path,
        identification: dict,
        note: str = ""
    ):
        """Move folder to review queue."""
        from app.models.pending_review import PendingReview

        # Generate unique name if needed
        review_dest = self.review_path / folder.name
        if review_dest.exists():
            counter = 1
            while review_dest.exists():
                review_dest = self.review_path / f"{folder.name}_{counter}"
                counter += 1

        shutil.move(str(folder), str(review_dest))

        # Count audio files
        file_count = len([
            f for f in review_dest.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
        ])

        db = SessionLocal()
        try:
            review = PendingReview(
                path=str(review_dest),
                suggested_artist=identification.get("artist"),
                suggested_album=identification.get("album"),
                beets_confidence=identification.get("confidence", 0),
                track_count=file_count,
                notes=note,
                status="pending"
            )
            db.add(review)
            db.commit()
            db.refresh(review)

            logger.info(f"Added to review queue: ID {review.id}")

            # Broadcast to admins
            await broadcast_review_needed(
                review_id=review.id,
                path=str(review_dest),
                suggested_artist=identification.get("artist"),
                suggested_album=identification.get("album"),
                confidence=identification.get("confidence", 0)
            )

        finally:
            db.close()


def start_watcher() -> Observer:
    """Start the watch folder observer."""
    event_handler = ImportWatcher()
    observer = Observer()

    watch_path = event_handler.pending_path
    logger.info(f"Starting watcher on {watch_path}")

    observer.schedule(event_handler, str(watch_path), recursive=False)
    observer.start()

    return observer


async def run_watcher():
    """Run watcher in async context."""
    observer = start_watcher()

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        observer.stop()
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    observer = start_watcher()

    try:
        # Keep running
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down watcher...")
        observer.stop()

    observer.join()
    logger.info("Watcher stopped")
