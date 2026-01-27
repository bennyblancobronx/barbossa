"""Celery background tasks."""
from app.tasks.downloads import download_qobuz_task, download_url_task, sync_bandcamp_task
from app.tasks.exports import run_export_task
from app.tasks.enrichment import (
    enrich_album_lyrics_task,
    enrich_missing_lyrics_task,
    enrich_track_lyrics_task,
    get_enrichment_stats_task,
)

__all__ = [
    "download_qobuz_task",
    "download_url_task",
    "sync_bandcamp_task",
    "run_export_task",
    "enrich_album_lyrics_task",
    "enrich_missing_lyrics_task",
    "enrich_track_lyrics_task",
    "get_enrichment_stats_task",
]
