"""Export Celery tasks."""
import asyncio
from app.worker import celery_app
from app.database import SessionLocal
from app.services.export_service import ExportService


@celery_app.task(bind=True, queue='exports')
def run_export_task(self, export_id: int):
    """Run export job in background.

    Args:
        export_id: Export job ID
    """
    db = SessionLocal()
    try:
        service = ExportService(db)

        # Run async export in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.run_export(export_id))
        finally:
            loop.close()

        return {"status": "complete", "export_id": export_id}

    except Exception as e:
        # Update export status on failure
        from app.models.export import Export, ExportStatus
        export = db.query(Export).filter(Export.id == export_id).first()
        if export:
            export.status = ExportStatus.FAILED
            export.error_message = str(e)
            db.commit()
        raise

    finally:
        db.close()
