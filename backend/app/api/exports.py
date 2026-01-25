"""Export API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.export import Export, ExportStatus
from app.schemas.export import ExportCreate, ExportResponse
from app.services.export_service import ExportService
from app.tasks.exports import run_export_task


router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("", response_model=ExportResponse)
async def create_export(
    data: ExportCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create new export job for current user."""
    target_user_id = user.id

    service = ExportService(db)
    export = service.create_export(
        user_id=target_user_id,
        destination=data.destination,
        format=data.format,
        include_artwork=data.include_artwork,
        include_playlist=data.include_playlist
    )

    # Start background task
    task = run_export_task.delay(export.id)
    export.celery_task_id = task.id
    db.commit()
    db.refresh(export)

    return export


@router.get("", response_model=list[ExportResponse])
async def list_exports(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List user's exports."""
    query = db.query(Export).filter(Export.user_id == user.id)

    return query.order_by(Export.created_at.desc()).all()


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get export details."""
    export = db.query(Export).filter(Export.id == export_id).first()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return export


@router.post("/{export_id}/cancel")
async def cancel_export(
    export_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Cancel running export."""
    export = db.query(Export).filter(Export.id == export_id).first()

    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    if export.status not in [ExportStatus.PENDING, ExportStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed export")

    # Cancel Celery task
    if export.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(export.celery_task_id, terminate=True)

    export.status = ExportStatus.CANCELLED
    db.commit()

    return {"status": "cancelled"}
