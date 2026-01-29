"""Celery tasks for background downloads."""
import asyncio
from typing import Optional
from celery import shared_task
from app.database import SessionLocal
from app.services.download import DownloadService


def _get_event_loop():
    """Get or create event loop for async tasks."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def download_qobuz_task(
    self,
    download_id: int,
    url: str,
    quality: int = 4
) -> dict:
    """Background task for Qobuz download.

    Args:
        download_id: Database download record ID
        url: Qobuz URL
        quality: Quality tier (0-4)

    Returns:
        Dict with status and album_id
    """
    async def progress_callback(percent: int, speed: str, eta: str):
        """Update download progress in database and broadcast via WebSocket."""
        db = SessionLocal()
        user_id = None
        try:
            from app.models.download import Download
            download = db.query(Download).filter(Download.id == download_id).first()
            if download:
                download.progress = percent
                download.speed = speed
                download.eta = eta
                user_id = download.user_id
                db.commit()
        finally:
            db.close()

        # Broadcast via WebSocket if we have user_id
        if user_id:
            try:
                from app.websocket import broadcast_download_progress
                await broadcast_download_progress(
                    download_id=download_id,
                    user_id=user_id,
                    progress=percent,
                    speed=speed,
                    eta=eta
                )
            except Exception:
                pass  # WebSocket not available

    async def run():
        db = SessionLocal()
        try:
            service = DownloadService(db)
            album = await service.download_qobuz(
                download_id,
                url,
                quality,
                progress_callback
            )
            if album is None:
                return {"status": "duplicate"}

            # Broadcast download completion and library update
            from app.models.download import Download
            download = db.query(Download).filter(Download.id == download_id).first()
            user_id = download.user_id if download else None

            if user_id:
                try:
                    from app.websocket import broadcast_download_complete, broadcast_library_update
                    await broadcast_download_complete(
                        download_id=download_id,
                        user_id=user_id,
                        album_id=album.id,
                        album_title=album.title,
                        artist_name=album.artist.name if album.artist else "Unknown"
                    )
                    await broadcast_library_update("album", album.id, "created")
                except Exception:
                    pass  # WebSocket not available

            return {"status": "complete", "album_id": album.id}
        except Exception as e:
            raise e
        finally:
            db.close()

    loop = _get_event_loop()
    try:
        return loop.run_until_complete(run())
    except Exception as e:
        # Don't retry terminal states -- review/duplicate are intentional, not transient failures
        from app.services.download import NeedsReviewError, DuplicateError
        from app.services.import_service import DuplicateContentError
        if isinstance(e, (NeedsReviewError, DuplicateError, DuplicateContentError)):
            return {"status": "review" if isinstance(e, NeedsReviewError) else "duplicate"}

        # Retry on transient failures only
        try:
            self.retry(exc=e, countdown=60)
        except self.MaxRetriesExceededError:
            # Update status to failed
            db = SessionLocal()
            user_id = None
            try:
                from app.models.download import Download, DownloadStatus
                download = db.query(Download).filter(Download.id == download_id).first()
                if download:
                    download.status = DownloadStatus.FAILED.value
                    download.error_message = str(e)
                    user_id = download.user_id
                    db.commit()
            finally:
                db.close()

            # Broadcast failure via WebSocket
            if user_id:
                try:
                    from app.websocket import broadcast_download_error
                    loop = _get_event_loop()
                    loop.run_until_complete(
                        broadcast_download_error(download_id, user_id, str(e))
                    )
                except Exception:
                    pass
            return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def download_url_task(
    self,
    download_id: int,
    url: str
) -> dict:
    """Background task for URL download (YouTube, Bandcamp, etc.).

    Args:
        download_id: Database download record ID
        url: Media URL

    Returns:
        Dict with status and album_id
    """
    async def progress_callback(percent: int, speed: str, eta: str):
        """Update download progress in database and broadcast via WebSocket."""
        db = SessionLocal()
        user_id = None
        try:
            from app.models.download import Download
            download = db.query(Download).filter(Download.id == download_id).first()
            if download:
                download.progress = percent
                download.speed = speed
                download.eta = eta
                user_id = download.user_id
                db.commit()
        finally:
            db.close()

        # Broadcast via WebSocket if we have user_id
        if user_id:
            try:
                from app.websocket import broadcast_download_progress
                await broadcast_download_progress(
                    download_id=download_id,
                    user_id=user_id,
                    progress=percent,
                    speed=speed,
                    eta=eta
                )
            except Exception:
                pass  # WebSocket not available

    async def run():
        db = SessionLocal()
        try:
            service = DownloadService(db)
            album = await service.download_url(
                download_id,
                url,
                progress_callback
            )
            if album is None:
                return {"status": "duplicate"}

            # Broadcast download completion and library update
            from app.models.download import Download
            download = db.query(Download).filter(Download.id == download_id).first()
            user_id = download.user_id if download else None

            if user_id:
                try:
                    from app.websocket import broadcast_download_complete, broadcast_library_update
                    await broadcast_download_complete(
                        download_id=download_id,
                        user_id=user_id,
                        album_id=album.id,
                        album_title=album.title,
                        artist_name=album.artist.name if album.artist else "Unknown"
                    )
                    await broadcast_library_update("album", album.id, "created")
                except Exception:
                    pass  # WebSocket not available

            return {"status": "complete", "album_id": album.id}
        except Exception as e:
            raise e
        finally:
            db.close()

    loop = _get_event_loop()
    try:
        return loop.run_until_complete(run())
    except Exception as e:
        # Don't retry terminal states
        from app.services.download import NeedsReviewError, DuplicateError
        from app.services.import_service import DuplicateContentError
        if isinstance(e, (NeedsReviewError, DuplicateError, DuplicateContentError)):
            return {"status": "review" if isinstance(e, NeedsReviewError) else "duplicate"}

        try:
            self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            db = SessionLocal()
            user_id = None
            try:
                from app.models.download import Download, DownloadStatus
                download = db.query(Download).filter(Download.id == download_id).first()
                if download:
                    download.status = DownloadStatus.FAILED.value
                    download.error_message = str(e)
                    user_id = download.user_id
                    db.commit()
            finally:
                db.close()

            # Broadcast failure via WebSocket
            if user_id:
                try:
                    from app.websocket import broadcast_download_error
                    loop = _get_event_loop()
                    loop.run_until_complete(
                        broadcast_download_error(download_id, user_id, str(e))
                    )
                except Exception:
                    pass
            return {"status": "failed", "error": str(e)}


@shared_task(bind=True, queue='downloads')
def sync_bandcamp_task(self) -> dict:
    """Background task for Bandcamp collection sync.

    Downloads all purchased items from user's Bandcamp collection.

    Returns:
        Dict with status and count of downloaded albums
    """
    async def run():
        from app.integrations.bandcamp import BandcampClient, BandcampError
        from app.services.import_service import ImportService
        from app.integrations.exiftool import ExifToolClient

        db = SessionLocal()
        client = BandcampClient()
        exiftool = ExifToolClient()

        try:
            # Sync collection
            downloaded_paths = await client.sync_collection()

            # Import each album
            import_service = ImportService(db)
            albums_imported = 0

            for path in downloaded_paths:
                if not path.exists():
                    continue

                # Extract metadata
                tracks = await exiftool.get_album_metadata(path)
                if not tracks:
                    continue

                # Try to extract year from folder name as fallback
                if tracks and not tracks[0].get("year"):
                    import re
                    match = re.search(r'\((\d{4})\)', path.name)
                    if match:
                        tracks[0]["year"] = int(match.group(1))

                # Check for duplicates
                first_track = tracks[0]
                existing = import_service.find_duplicate(
                    first_track.get("artist", "Unknown"),
                    first_track.get("album", path.name)
                )

                if existing:
                    continue  # Skip duplicates

                # Import
                await import_service.import_album(
                    path=path,
                    tracks_metadata=tracks,
                    source="bandcamp",
                    source_url="",
                    imported_by=None
                )
                albums_imported += 1

            return {"status": "complete", "albums_imported": albums_imported}

        except BandcampError as e:
            return {"status": "failed", "error": str(e)}
        finally:
            db.close()

    loop = _get_event_loop()
    return loop.run_until_complete(run())
