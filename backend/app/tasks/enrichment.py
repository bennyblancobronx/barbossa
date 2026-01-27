"""Enrichment tasks for Celery.

Phase 8 of audit-014: Background metadata enrichment.
"""
import asyncio
import logging
from typing import Optional
from celery import shared_task

from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _get_event_loop():
    """Get or create an event loop for async operations in Celery tasks."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


@shared_task(name="app.tasks.enrichment.enrich_album_lyrics")
def enrich_album_lyrics_task(album_id: int) -> dict:
    """Enrich all tracks in an album with lyrics.

    Args:
        album_id: Album ID to enrich

    Returns:
        Dict with enrichment results
    """
    from app.services.enrichment import EnrichmentService

    db = SessionLocal()

    try:
        service = EnrichmentService(db)
        loop = _get_event_loop()
        result = loop.run_until_complete(service.enrich_album_lyrics(album_id))

        logger.info(
            f"Album {album_id} lyrics enrichment: "
            f"{result.enriched}/{result.total} tracks enriched"
        )

        return {
            "album_id": album_id,
            "total": result.total,
            "enriched": result.enriched,
            "failed": result.failed,
            "skipped": result.skipped
        }

    except Exception as e:
        logger.error(f"Album lyrics enrichment failed: {e}")
        return {"error": str(e), "album_id": album_id}

    finally:
        db.close()


@shared_task(name="app.tasks.enrichment.enrich_missing_lyrics")
def enrich_missing_lyrics_task(
    limit: int = 100,
    album_id: Optional[int] = None,
    artist_id: Optional[int] = None
) -> dict:
    """Enrich tracks missing lyrics.

    Args:
        limit: Maximum tracks to process
        album_id: Optional filter by album
        artist_id: Optional filter by artist

    Returns:
        Dict with enrichment results
    """
    from app.services.enrichment import EnrichmentService

    db = SessionLocal()

    try:
        service = EnrichmentService(db)
        loop = _get_event_loop()
        result = loop.run_until_complete(
            service.enrich_missing_lyrics(
                limit=limit,
                album_id=album_id,
                artist_id=artist_id
            )
        )

        logger.info(
            f"Missing lyrics enrichment: "
            f"{result.enriched}/{result.total} tracks enriched"
        )

        return {
            "total": result.total,
            "enriched": result.enriched,
            "failed": result.failed,
            "skipped": result.skipped
        }

    except Exception as e:
        logger.error(f"Missing lyrics enrichment failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.enrichment.enrich_track_lyrics")
def enrich_track_lyrics_task(track_id: int) -> dict:
    """Enrich a single track with lyrics.

    Args:
        track_id: Track ID to enrich

    Returns:
        Dict with enrichment result
    """
    from app.models.track import Track
    from app.services.enrichment import EnrichmentService

    db = SessionLocal()

    try:
        track = db.query(Track).filter(Track.id == track_id).first()
        if not track:
            return {"error": "Track not found", "track_id": track_id}

        service = EnrichmentService(db)
        loop = _get_event_loop()
        result = loop.run_until_complete(service.enrich_track_lyrics(track))

        return {
            "track_id": track_id,
            "success": result.success,
            "message": result.message
        }

    except Exception as e:
        logger.error(f"Track lyrics enrichment failed: {e}")
        return {"error": str(e), "track_id": track_id}

    finally:
        db.close()


@shared_task(name="app.tasks.enrichment.get_enrichment_stats")
def get_enrichment_stats_task() -> dict:
    """Get enrichment statistics.

    Returns:
        Dict with counts of tracks missing various metadata
    """
    from app.services.enrichment import EnrichmentService

    db = SessionLocal()

    try:
        service = EnrichmentService(db)
        return service.get_enrichment_stats()

    except Exception as e:
        logger.error(f"Enrichment stats failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()
