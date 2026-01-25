"""Pending review API endpoints."""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import shutil

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.pending_review import PendingReview, PendingReviewStatus
from app.schemas.review import ReviewResponse, ApproveRequest, RejectRequest
from app.services.import_service import ImportService
from app.integrations.beets import BeetsClient
from app.integrations.exiftool import ExifToolClient


router = APIRouter(prefix="/import/review", tags=["review"])


@router.get("", response_model=list[ReviewResponse])
async def list_pending_review(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List items pending review."""
    query = db.query(PendingReview).order_by(PendingReview.created_at.desc())

    if status:
        query = query.filter(PendingReview.status == status)
    else:
        query = query.filter(PendingReview.status == PendingReviewStatus.PENDING)

    return query.all()


@router.get("/{review_id}", response_model=ReviewResponse)
async def get_review_item(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get single review item with details."""
    review = db.query(PendingReview).filter(PendingReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    return review


@router.post("/{review_id}/approve")
async def approve_import(
    review_id: int,
    data: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve and import pending item.

    Can override artist/album/year if auto-detection was wrong.
    """
    review = db.query(PendingReview).filter(PendingReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if review.status != PendingReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Item already processed")

    try:
        beets = BeetsClient()
        exiftool = ExifToolClient()
        import_service = ImportService(db)

        folder = Path(review.path)
        if not folder.exists():
            raise HTTPException(status_code=404, detail="Source folder not found")

        # Import with overrides
        library_path = await beets.import_album(
            folder,
            artist=data.artist or review.suggested_artist,
            album=data.album or review.suggested_album,
            move=True
        )

        # Extract metadata
        tracks_metadata = await exiftool.get_album_metadata(library_path)

        # Import to database
        album = await import_service.import_album(
            path=library_path,
            tracks_metadata=tracks_metadata,
            source="import",
            source_url="",
            imported_by=current_user.id,
            confidence=1.0
        )

        # Update review status
        review.status = PendingReviewStatus.APPROVED
        review.reviewed_by = current_user.id
        review.reviewed_at = datetime.utcnow()
        db.commit()

        return {"status": "approved", "album_id": album.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{review_id}/reject")
async def reject_import(
    review_id: int,
    data: RejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject and optionally delete pending item."""
    review = db.query(PendingReview).filter(PendingReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if review.status != PendingReviewStatus.PENDING:
        raise HTTPException(status_code=400, detail="Item already processed")

    # Optionally delete files
    if data.delete_files:
        folder = Path(review.path)
        if folder.exists():
            shutil.rmtree(folder)

    review.status = PendingReviewStatus.REJECTED
    review.reviewed_by = current_user.id
    review.reviewed_at = datetime.utcnow()
    review.notes = data.reason
    db.commit()

    return {"status": "rejected"}
