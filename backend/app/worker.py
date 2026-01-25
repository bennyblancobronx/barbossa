"""Celery worker configuration.

Run worker: celery -A app.worker worker -l info -Q downloads,imports,maintenance
Run beat: celery -A app.worker beat -l info
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "barbossa",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.downloads",
        "app.tasks.imports",
        "app.tasks.maintenance"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "app.tasks.downloads.*": {"queue": "downloads"},
        "app.tasks.imports.*": {"queue": "imports"},
        "app.tasks.maintenance.*": {"queue": "maintenance"},
    },

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=4,  # 4 concurrent tasks

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Retry settings
    task_annotations={
        "app.tasks.downloads.download_qobuz_task": {
            "rate_limit": "10/m",  # 10 downloads per minute max
            "max_retries": 3,
            "default_retry_delay": 60,
        },
        "app.tasks.downloads.download_url_task": {
            "rate_limit": "20/m",  # More lenient for URL downloads
            "max_retries": 3,
            "default_retry_delay": 30,
        },
        "app.tasks.imports.process_import": {
            "rate_limit": "5/m",
            "max_retries": 2,
            "default_retry_delay": 300,
        },
    },

    # Beat schedule - periodic tasks
    beat_schedule={
        # Scan import folder every 5 minutes
        "scan-import-folder": {
            "task": "app.tasks.imports.scan_import_folder",
            "schedule": crontab(minute="*/5"),
            "options": {"queue": "imports"}
        },

        # Clean up old downloads every hour
        "cleanup-downloads": {
            "task": "app.tasks.maintenance.cleanup_old_downloads",
            "schedule": crontab(minute=0),
            "options": {"queue": "maintenance"}
        },

        # Verify file integrity daily at 3 AM
        "verify-integrity": {
            "task": "app.tasks.maintenance.verify_integrity",
            "schedule": crontab(hour=3, minute=0),
            "options": {"queue": "maintenance"}
        },

        # Update album stats weekly on Sunday at 4 AM
        "update-album-stats": {
            "task": "app.tasks.maintenance.update_album_stats",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),
            "options": {"queue": "maintenance"}
        },

        # Update library stats daily at 5 AM
        "update-library-stats": {
            "task": "app.tasks.maintenance.update_library_stats",
            "schedule": crontab(hour=5, minute=0),
            "options": {"queue": "maintenance"}
        },

        # Clean up orphan symlinks weekly on Sunday at 4:30 AM
        "cleanup-orphan-symlinks": {
            "task": "app.tasks.maintenance.cleanup_orphan_symlinks",
            "schedule": crontab(day_of_week=0, hour=4, minute=30),
            "options": {"queue": "maintenance"}
        },

        # Clean up empty folders weekly on Sunday at 5 AM
        "cleanup-empty-folders": {
            "task": "app.tasks.maintenance.cleanup_empty_folders",
            "schedule": crontab(day_of_week=0, hour=5, minute=0),
            "options": {"queue": "maintenance"}
        },
    }
)


# Debug task for testing
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "worker": self.request.hostname}
