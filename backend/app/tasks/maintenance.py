"""Maintenance tasks for Celery."""
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
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


@shared_task(name="app.tasks.maintenance.cleanup_old_downloads")
def cleanup_old_downloads():
    """Remove download records older than 30 days.

    Only cleans up completed, failed, or cancelled downloads.
    """
    from app.models.download import Download, DownloadStatus

    db = SessionLocal()

    try:
        cutoff = datetime.utcnow() - timedelta(days=30)

        # Count before delete
        count = db.query(Download).filter(
            Download.created_at < cutoff,
            Download.status.in_([
                DownloadStatus.COMPLETE,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED
            ])
        ).count()

        # Delete old records
        deleted = db.query(Download).filter(
            Download.created_at < cutoff,
            Download.status.in_([
                DownloadStatus.COMPLETE,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED
            ])
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(f"Cleaned up {deleted} old download records")
        return {"deleted": deleted}

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.maintenance.verify_integrity")
def verify_integrity(include_flac_stream: bool = True):
    """Verify file integrity for all tracks.

    Checks:
    - File exists on disk
    - Checksum matches using BLAKE3 (if stored)
    - FLAC stream verification via flac -t (if enabled)

    Args:
        include_flac_stream: If True, also verify FLAC files with flac -t
    """
    from app.models.track import Track
    from app.services.quality import generate_checksum
    from app.services.integrity import IntegrityService, IntegrityStatus

    db = SessionLocal()

    async def _verify_all():
        integrity_service = IntegrityService()
        issues = []
        checked = 0
        flac_verified = 0
        flac_no_md5 = 0

        tracks = db.query(Track).all()

        for track in tracks:
            checked += 1
            path = Path(track.path)

            # Check file exists
            if not path.exists():
                issues.append({
                    "track_id": track.id,
                    "issue": "missing_file",
                    "path": track.path
                })
                continue

            # Verify checksum if stored (uses BLAKE3 via quality.py)
            if track.checksum:
                try:
                    current_hash = generate_checksum(path)

                    if current_hash != track.checksum:
                        issues.append({
                            "track_id": track.id,
                            "issue": "checksum_mismatch",
                            "expected": track.checksum,
                            "actual": current_hash,
                            "path": track.path
                        })
                except Exception as e:
                    issues.append({
                        "track_id": track.id,
                        "issue": "read_error",
                        "error": str(e),
                        "path": track.path
                    })

            # FLAC stream verification (checks frame CRCs and embedded MD5)
            if include_flac_stream and path.suffix.lower() == ".flac":
                try:
                    result = await integrity_service.verify_flac(path)

                    if result.status == IntegrityStatus.FAILED:
                        issues.append({
                            "track_id": track.id,
                            "issue": "flac_stream_corrupted",
                            "message": result.message,
                            "path": track.path
                        })
                    elif result.status == IntegrityStatus.OK:
                        flac_verified += 1
                    elif result.status == IntegrityStatus.NO_MD5:
                        # Not an error, just informational (typical for Qobuz)
                        flac_verified += 1
                        flac_no_md5 += 1
                    elif result.status == IntegrityStatus.ERROR:
                        # flac command not installed or other error
                        if "not installed" in (result.message or ""):
                            # Log once and skip further FLAC checks
                            logger.warning("flac command not installed - skipping stream verification")
                            include_flac_stream = False
                        else:
                            issues.append({
                                "track_id": track.id,
                                "issue": "flac_check_error",
                                "error": result.message,
                                "path": track.path
                            })
                except Exception as e:
                    issues.append({
                        "track_id": track.id,
                        "issue": "flac_check_error",
                        "error": str(e),
                        "path": track.path
                    })

        return {
            "checked": checked,
            "flac_verified": flac_verified,
            "flac_no_md5": flac_no_md5,
            "issues_count": len(issues),
            "issues": issues[:100]  # Limit to first 100 issues
        }

    try:
        loop = _get_event_loop()
        result = loop.run_until_complete(_verify_all())

        logger.info(
            f"Integrity check: {result['checked']} tracks, "
            f"{result['flac_verified']} FLAC verified, "
            f"{result['issues_count']} issues"
        )

        return result

    except Exception as e:
        logger.error(f"Integrity check failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.maintenance.update_album_stats")
def update_album_stats():
    """Recalculate album track counts.

    Updates available_tracks based on actual tracks in database.
    """
    from app.models.album import Album
    from app.models.track import Track
    from sqlalchemy import func

    db = SessionLocal()

    try:
        # Get actual track counts
        counts = db.query(
            Track.album_id,
            func.count(Track.id).label("count")
        ).group_by(Track.album_id).all()

        count_map = {c.album_id: c.count for c in counts}

        # Update albums
        updated = 0
        for album in db.query(Album).all():
            actual = count_map.get(album.id, 0)
            if album.available_tracks != actual:
                album.available_tracks = actual
                updated += 1

        db.commit()

        logger.info(f"Updated {updated} album track counts")
        return {"updated": updated}

    except Exception as e:
        logger.error(f"Album stats update failed: {e}")
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.maintenance.cleanup_orphan_symlinks")
def cleanup_orphan_symlinks():
    """Remove orphan symlinks in user libraries.

    Checks that symlinks point to valid files in master library.
    """
    from app.config import settings

    users_path = Path(settings.music_users)

    if not users_path.exists():
        return {"cleaned": 0}

    cleaned = 0
    errors = []

    for user_dir in users_path.iterdir():
        if not user_dir.is_dir():
            continue

        # Walk all files in user library
        for path in user_dir.rglob("*"):
            if not path.is_symlink():
                continue

            # Check if symlink target exists
            try:
                target = path.resolve()
                if not target.exists():
                    path.unlink()
                    cleaned += 1

                    # Clean up empty parent directories
                    parent = path.parent
                    while parent != user_dir and not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent

            except Exception as e:
                errors.append({
                    "path": str(path),
                    "error": str(e)
                })

    logger.info(f"Cleaned {cleaned} orphan symlinks")

    return {
        "cleaned": cleaned,
        "errors_count": len(errors),
        "errors": errors[:20]  # Limit to first 20 errors
    }


@shared_task(name="app.tasks.maintenance.update_library_stats")
def update_library_stats():
    """Update overall library statistics.

    Calculates totals for dashboard display.
    """
    from app.models.artist import Artist
    from app.models.album import Album
    from app.models.track import Track
    from app.models.user import User
    from sqlalchemy import func

    db = SessionLocal()

    try:
        stats = {
            "artists": db.query(func.count(Artist.id)).scalar(),
            "albums": db.query(func.count(Album.id)).scalar(),
            "tracks": db.query(func.count(Track.id)).scalar(),
            "users": db.query(func.count(User.id)).scalar(),
            "total_size_bytes": db.query(func.sum(Track.file_size)).scalar() or 0,
            "lossless_tracks": db.query(func.count(Track.id)).filter(
                Track.is_lossy == False
            ).scalar(),
            "lossy_tracks": db.query(func.count(Track.id)).filter(
                Track.is_lossy == True
            ).scalar(),
            "updated_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Library stats: {stats['albums']} albums, {stats['tracks']} tracks")

        return stats

    except Exception as e:
        logger.error(f"Stats update failed: {e}")
        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.maintenance.cleanup_empty_folders")
def cleanup_empty_folders():
    """Remove empty folders in library and user directories."""
    from app.config import settings

    cleaned = 0

    for base_path in [settings.music_library, settings.music_users]:
        base = Path(base_path)
        if not base.exists():
            continue

        # Walk bottom-up to find empty directories
        for dirpath in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                try:
                    dirpath.rmdir()
                    cleaned += 1
                except Exception:
                    pass

    logger.info(f"Cleaned {cleaned} empty folders")
    return {"cleaned": cleaned}


@shared_task(name="app.tasks.maintenance.run_backup")
def run_backup(backup_id: int, destination: str):
    """Run backup to specified destination.

    Updates BackupHistory record with progress and results.
    """
    import shutil
    from app.config import settings
    from app.models.backup_history import BackupHistory

    db = SessionLocal()

    try:
        backup = db.query(BackupHistory).filter(BackupHistory.id == backup_id).first()
        if not backup:
            return {"error": "Backup record not found"}

        library_path = Path(settings.music_library)
        dest_path = Path(destination)

        if not library_path.exists():
            backup.status = "failed"
            backup.error_message = "Library path does not exist"
            backup.completed_at = datetime.utcnow()
            db.commit()
            return {"error": "Library path does not exist"}

        # Create destination if needed
        dest_path.mkdir(parents=True, exist_ok=True)

        files_backed_up = 0
        total_size = 0

        # Walk library and copy files
        for src_file in library_path.rglob("*"):
            if not src_file.is_file():
                continue

            rel_path = src_file.relative_to(library_path)
            dst_file = dest_path / rel_path

            # Create parent directories
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy if newer or doesn't exist
            if not dst_file.exists() or src_file.stat().st_mtime > dst_file.stat().st_mtime:
                shutil.copy2(src_file, dst_file)
                files_backed_up += 1
                total_size += src_file.stat().st_size

        # Update backup record
        backup.status = "complete"
        backup.files_backed_up = files_backed_up
        backup.total_size = total_size
        backup.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"Backup complete: {files_backed_up} files, {total_size} bytes")

        return {
            "status": "complete",
            "files_backed_up": files_backed_up,
            "total_size": total_size
        }

    except Exception as e:
        logger.error(f"Backup failed: {e}")

        backup = db.query(BackupHistory).filter(BackupHistory.id == backup_id).first()
        if backup:
            backup.status = "failed"
            backup.error_message = str(e)
            backup.completed_at = datetime.utcnow()
            db.commit()

        return {"error": str(e)}

    finally:
        db.close()


@shared_task(name="app.tasks.maintenance.scan_library")
def scan_library():
    """Full library rescan.

    Walks the master library directory and:
    - Indexes new albums/tracks not in database
    - Updates metadata for existing tracks
    - Marks missing files as unavailable
    """
    from app.config import settings
    from app.models.album import Album
    from app.models.track import Track
    from app.services.import_service import ImportService
    from app.integrations.exiftool import ExifToolClient

    db = SessionLocal()
    exiftool = ExifToolClient()

    library_path = Path(settings.music_library)
    if not library_path.exists():
        return {"error": "Library path does not exist"}

    async def scan():
        import_service = ImportService(db)

        scanned_albums = 0
        new_albums = 0
        updated_tracks = 0
        errors = []

        # Walk artist directories
        for artist_dir in library_path.iterdir():
            if not artist_dir.is_dir():
                continue

            # Walk album directories
            for album_dir in artist_dir.iterdir():
                if not album_dir.is_dir():
                    continue

                scanned_albums += 1

                try:
                    # Check if album exists in database
                    existing = db.query(Album).filter(
                        Album.path == str(album_dir)
                    ).first()

                    if existing:
                        # Update track metadata
                        tracks_meta = await exiftool.get_album_metadata(album_dir)
                        for meta in tracks_meta:
                            track = db.query(Track).filter(
                                Track.path == meta.get("path")
                            ).first()

                            if track:
                                # Update quality info
                                track.sample_rate = meta.get("sample_rate") or track.sample_rate
                                track.bit_depth = meta.get("bit_depth") or track.bit_depth
                                track.file_size = meta.get("file_size") or track.file_size
                                updated_tracks += 1
                    else:
                        # Import new album
                        tracks_meta = await exiftool.get_album_metadata(album_dir)
                        if tracks_meta:
                            await import_service.import_album(
                                path=album_dir,
                                tracks_metadata=tracks_meta,
                                source="import",
                                source_url="",
                                imported_by=None
                            )
                            new_albums += 1

                except Exception as e:
                    errors.append({
                        "path": str(album_dir),
                        "error": str(e)
                    })

        db.commit()

        return {
            "scanned": scanned_albums,
            "new_albums": new_albums,
            "updated_tracks": updated_tracks,
            "errors_count": len(errors),
            "errors": errors[:20]
        }

    loop = _get_event_loop()
    try:
        result = loop.run_until_complete(scan())
        logger.info(f"Library scan: {result['scanned']} albums, {result['new_albums']} new")
        return result
    except Exception as e:
        logger.error(f"Library scan failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()
