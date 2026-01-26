"""Download API endpoints."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.download import Download, DownloadStatus, DownloadSource
from app.schemas.download import (
    DownloadCreate,
    DownloadResponse,
    DownloadStatusResponse,
    SearchResult,
    UrlInfo
)
from app.services.download import DownloadService
from app.tasks.downloads import download_qobuz_task, download_url_task
from app.websocket import manager


router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("/search/qobuz", response_model=list[SearchResult])
async def search_qobuz(
    q: str = Query(..., min_length=1, description="Search query"),
    type: str = Query("album", pattern="^(artist|album|track|playlist)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Search Qobuz catalog.

    Returns list of results with id, title, artist, year, quality, url.
    User must select type: artist, album, track, or playlist.
    """
    service = DownloadService(db)
    return await service.search_qobuz(q, type, limit)


@router.get("/url/info", response_model=UrlInfo)
async def get_url_info(
    url: str = Query(..., description="Media URL to inspect"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get metadata from URL without downloading.

    Useful for preview before committing to download.
    """
    service = DownloadService(db)
    return await service.ytdlp.get_info(url)


@router.post("/qobuz", response_model=DownloadResponse)
async def download_from_qobuz(
    data: DownloadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Start Qobuz download.

    Creates download record and starts background task.
    Progress available via WebSocket or polling /downloads/{id}/status.
    """
    # Create download record
    download = Download(
        user_id=user.id,
        source=DownloadSource.QOBUZ.value,
        source_url=data.url,
        search_type=data.search_type,
        status=DownloadStatus.PENDING.value,
        progress=0
    )
    db.add(download)
    db.commit()
    db.refresh(download)

    # Start background task
    task = download_qobuz_task.delay(download.id, data.url, data.quality or 4)

    download.celery_task_id = task.id
    download.started_at = datetime.utcnow()
    db.commit()

    return download


@router.post("/url", response_model=DownloadResponse)
async def download_from_url(
    data: DownloadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Start URL download (YouTube, Bandcamp, Soundcloud).

    Requires confirm_lossy=true for lossy sources.
    """
    # Detect source
    url = data.url.lower()
    if "youtube" in url or "youtu.be" in url:
        source = DownloadSource.YOUTUBE
    elif "bandcamp" in url:
        source = DownloadSource.BANDCAMP
    elif "soundcloud" in url:
        source = DownloadSource.SOUNDCLOUD
    else:
        source = DownloadSource.URL

    # Require confirmation for lossy sources
    lossy_sources = [DownloadSource.YOUTUBE, DownloadSource.SOUNDCLOUD]
    if source in lossy_sources and not data.confirm_lossy:
        raise HTTPException(
            status_code=400,
            detail="Lossy source requires confirm_lossy=true. Content from this source is always lossy quality."
        )

    # Create download record
    download = Download(
        user_id=user.id,
        source=source.value,
        source_url=data.url,
        status=DownloadStatus.PENDING.value,
        progress=0
    )
    db.add(download)
    db.commit()
    db.refresh(download)

    # Start background task
    task = download_url_task.delay(download.id, data.url)

    download.celery_task_id = task.id
    download.started_at = datetime.utcnow()
    db.commit()

    return download


@router.get("", response_model=list[DownloadResponse])
async def list_downloads(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List download history for current user."""
    query = db.query(Download).filter(Download.user_id == user.id)

    if status:
        query = query.filter(Download.status == status)

    return query.order_by(Download.created_at.desc()).limit(limit).all()


@router.get("/queue", response_model=list[DownloadResponse])
async def get_download_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get active download queue.

    Returns pending, in-progress, and pending_review downloads.
    """
    query = db.query(Download).filter(
        Download.status.in_([
            DownloadStatus.PENDING.value,
            DownloadStatus.DOWNLOADING.value,
            DownloadStatus.IMPORTING.value,
            DownloadStatus.PENDING_REVIEW.value
        ]),
        Download.user_id == user.id
    )

    return query.order_by(Download.created_at.asc()).all()


@router.get("/{download_id}", response_model=DownloadResponse)
async def get_download(
    download_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get download details."""
    download = db.query(Download).filter(Download.id == download_id).first()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return download


@router.get("/{download_id}/status", response_model=DownloadStatusResponse)
async def get_download_status(
    download_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get download status for polling.

    Lightweight endpoint for status updates when WebSocket unavailable.
    """
    download = db.query(Download).filter(Download.id == download_id).first()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return download


@router.post("/{download_id}/cancel")
async def cancel_download(
    download_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Cancel pending/active download."""
    download = db.query(Download).filter(Download.id == download_id).first()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    cancellable_statuses = [
        DownloadStatus.PENDING.value,
        DownloadStatus.DOWNLOADING.value
    ]
    if download.status not in cancellable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel download with status: {download.status}"
        )

    # Cancel Celery task
    if download.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(download.celery_task_id, terminate=True)

    download.status = DownloadStatus.CANCELLED.value
    download.completed_at = datetime.utcnow()
    db.commit()

    return {"status": "cancelled", "id": download_id}


@router.delete("/{download_id}")
async def delete_download(
    download_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete download record.

    Only completed, failed, or cancelled downloads can be deleted.
    """
    download = db.query(Download).filter(Download.id == download_id).first()

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    deletable_statuses = [
        DownloadStatus.COMPLETE.value,
        DownloadStatus.DUPLICATE.value,
        DownloadStatus.FAILED.value,
        DownloadStatus.CANCELLED.value
    ]
    if download.status not in deletable_statuses:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete active download. Cancel first."
        )

    db.delete(download)
    db.commit()

    return {"status": "deleted", "id": download_id}


# WebSocket endpoint for real-time updates
@router.websocket("/ws/{download_id}")
async def websocket_download_progress(
    websocket: WebSocket,
    download_id: int
):
    """WebSocket endpoint for download progress updates.

    Connect to receive real-time progress for a specific download.
    """
    await manager.connect(websocket, download_id)
    try:
        while True:
            # Keep connection alive, wait for messages
            data = await websocket.receive_text()
            # Client can send ping, we just acknowledge
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, download_id)


@router.websocket("/ws")
async def websocket_global(websocket: WebSocket):
    """WebSocket endpoint for global updates.

    Connect to receive all download events (progress, complete, error).
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
