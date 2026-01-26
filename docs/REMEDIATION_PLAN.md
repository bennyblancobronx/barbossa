# Barbossa Remediation Plan

This document provides step-by-step instructions for fixing the identified issues in the Barbossa music library application. Written for developers who may be less familiar with the codebase.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Issue Overview](#issue-overview)
3. [Phase 1: Fix File Deletion (P0)](#phase-1-fix-file-deletion-p0)
4. [Phase 2: Add Missing Artwork Fetch](#phase-2-add-missing-artwork-fetch)
5. [Phase 3: Add Import Rollback](#phase-3-add-import-rollback)
6. [Phase 4: Fix Review Retry Bug](#phase-4-fix-review-retry-bug)
7. [Phase 5: Add Missing Tests](#phase-5-add-missing-tests)
8. [Testing Your Changes](#testing-your-changes)
9. [Verification Checklist](#verification-checklist)

---

## Prerequisites

Before starting:

1. **Understand the data flow:**
   - Music enters via: Downloads (Qobuz/Lidarr/YouTube), CLI import, or GUI import
   - All paths use `beets` for identification (artist/album metadata)
   - Files are moved to `/music/artists/` (master library)
   - Database records track what exists on disk

2. **Key services to know:**
   - `backend/app/services/library.py` - Album CRUD operations
   - `backend/app/services/download.py` - Download and import flow
   - `backend/app/services/import_service.py` - Database import + artwork
   - `backend/app/tasks/imports.py` - Background import tasks
   - `backend/app/cli/admin.py` - CLI commands
   - `backend/app/api/review.py` - GUI review endpoints

3. **Set up your environment:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Run existing tests to establish baseline:**
   ```bash
   pytest tests/ -v
   ```

---

## Issue Overview

| # | Issue | Severity | File | Problem |
|---|-------|----------|------|---------|
| 1 | Delete reports success when fails | P0 | library.py:187-211 | DB deleted but files may remain |
| 2 | CLI imports have no artwork | P1 | admin.py:303-309 | Missing artwork fetch call |
| 3 | No rollback on import failure | P1 | download.py:285-301 | Files orphaned if DB insert fails |
| 4 | Review retry bug | P1 | imports.py:240-299 | Retry after files already moved |
| 5 | No CLI import tests | P2 | tests/ | Can't verify CLI import works |
| 6 | No GUI review tests | P2 | tests/ | Can't verify review flow works |

---

## Phase 1: Fix File Deletion (P0)

**Problem:** `delete_album()` always returns `True`, even when file deletion fails. This causes the database record to be deleted while files remain on disk.

**File:** `backend/app/services/library.py`

### Step 1.1: Understand the current code

Open `library.py` and find the `delete_album()` method (around line 151). Notice:
- It deletes the database record first (lines 159-177)
- Then tries to delete files (lines 179-209)
- Returns `True` unconditionally (line 211)

### Step 1.2: Change the deletion order

The fix: Delete files FIRST, only delete DB record if files are gone.

Replace the `delete_album()` method with:

```python
async def delete_album(
    self, album_id: int, delete_files: bool = True
) -> tuple[bool, str | None]:
    """
    Delete an album from the library.

    Returns:
        tuple[bool, str | None]: (success, error_message)
        - (True, None) if fully deleted
        - (False, "error reason") if failed
    """
    album = self.db.query(Album).filter(Album.id == album_id).first()
    if not album:
        return False, "Album not found"

    album_path = album.path
    album_title = album.title
    artist_name = album.artist.name if album.artist else "Unknown"

    # Step 1: Delete files FIRST (if requested)
    if delete_files and album_path:
        path = Path(album_path)
        if path.exists() and path.is_dir():
            try:
                # Handle SMB mount artifacts
                for smb_file in path.glob(".smbdelete*"):
                    try:
                        smb_file.unlink()
                    except Exception:
                        pass

                shutil.rmtree(path)
                logger.info(f"Deleted album files: {path}")

                # Clean up empty artist directory
                artist_dir = path.parent
                if artist_dir.exists() and not any(artist_dir.iterdir()):
                    artist_dir.rmdir()
                    logger.info(f"Removed empty artist directory: {artist_dir}")

            except PermissionError as e:
                logger.error(f"Permission denied deleting {path}: {e}")
                return False, f"Permission denied: cannot delete files at {path}"
            except OSError as e:
                logger.error(f"OS error deleting {path}: {e}")
                return False, f"Failed to delete files: {e}"
            except Exception as e:
                logger.error(f"Failed to delete album files {path}: {e}")
                return False, f"Failed to delete files: {e}"

    # Step 2: Delete database records only after files are gone
    try:
        # Delete associated user collection entries
        self.db.query(UserCollectionAlbum).filter(
            UserCollectionAlbum.album_id == album_id
        ).delete()

        # Delete tracks
        self.db.query(Track).filter(Track.album_id == album_id).delete()

        # Delete the album
        self.db.delete(album)
        self.db.commit()

        logger.info(f"Deleted album from database: {artist_name} - {album_title}")
        return True, None

    except Exception as e:
        self.db.rollback()
        logger.error(f"Database error deleting album {album_id}: {e}")
        # Files already deleted - this is bad, log prominently
        if delete_files and album_path:
            logger.critical(
                f"ORPHAN ALERT: Files deleted but DB record remains for album {album_id}"
            )
        return False, f"Database error: {e}"
```

### Step 1.3: Update the API endpoint

**File:** `backend/app/api/albums.py` (or wherever the delete endpoint is)

Find the delete endpoint and update it to handle the new return type:

```python
@router.delete("/{album_id}")
async def delete_album(
    album_id: int,
    delete_files: bool = Query(True, description="Also delete files from disk"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an album from the library."""
    library_service = LibraryService(db)
    success, error = await library_service.delete_album(album_id, delete_files)

    if not success:
        raise HTTPException(status_code=500, detail=error)

    return {"status": "deleted", "album_id": album_id}
```

### Step 1.4: Write a test

**File:** `backend/tests/test_library.py`

Add this test:

```python
@pytest.mark.asyncio
async def test_delete_album_file_failure_does_not_delete_db_record(
    db_session, sample_album
):
    """When file deletion fails, the database record should remain."""
    library_service = LibraryService(db_session)

    # Make the path read-only to simulate deletion failure
    album_path = Path(sample_album.path)
    album_path.chmod(0o444)
    album_path.parent.chmod(0o444)

    try:
        success, error = await library_service.delete_album(
            sample_album.id, delete_files=True
        )

        assert success is False
        assert "Permission denied" in error or "Failed to delete" in error

        # Verify DB record still exists
        album = db_session.query(Album).filter(Album.id == sample_album.id).first()
        assert album is not None
    finally:
        # Restore permissions for cleanup
        album_path.parent.chmod(0o755)
        album_path.chmod(0o755)
```

---

## Phase 2: Add Missing Artwork Fetch

**Problem:** Albums imported via CLI have no artwork because `fetch_artwork_if_missing()` is never called.

**File:** `backend/app/cli/admin.py`

### Step 2.1: Locate the CLI import command

Find the `import` command (around line 215). Scroll to where the import completes successfully (around line 303-309).

### Step 2.2: Add artwork fetch

After the successful import, add artwork fetching:

```python
# Around line 303-309, after successful import
imported = await import_service.import_album(
    path=library_path,
    tracks_metadata=tracks_metadata,
    source="cli",
    source_url="",
    confidence=confidence
)

# ADD THIS: Fetch artwork if missing
if imported and not imported.artwork_path:
    console.print("[dim]Fetching artwork...[/dim]")
    artwork = await import_service.fetch_artwork_if_missing(imported)
    if artwork:
        imported.artwork_path = artwork
        db.commit()
        console.print(f"[green]Added artwork: {artwork}[/green]")
    else:
        console.print("[yellow]No artwork found[/yellow]")

return imported
```

### Step 2.3: Verify the import_service has the method

Check `backend/app/services/import_service.py` has `fetch_artwork_if_missing()`. It should be around line 338. This method:
1. Checks for existing local artwork files
2. Tries beets `fetchart` plugin
3. Falls back to extracting embedded art via ffmpeg

---

## Phase 3: Add Import Rollback

**Problem:** If the database insert fails after beets has moved files, the files are orphaned in the library with no DB record.

**File:** `backend/app/services/download.py`

### Step 3.1: Understand the current flow

Find `_import_album()` (around line 222). The flow is:
1. `beets.import_album(move=True)` - Files are MOVED to library
2. `exiftool.get_album_metadata()` - Get track metadata
3. `import_service.import_album()` - Create DB records
4. `_ensure_artwork()` - Fetch artwork

If step 3 or 4 fails, files are already in the library but not tracked.

### Step 3.2: Add rollback logic

Wrap the post-move operations in a try/except that rolls back the file move:

```python
async def _import_album(
    self,
    path: Path,
    source: str,
    source_url: str = "",
    user_id: int | None = None,
    confidence: float = 1.0
) -> Album:
    """Import an album to the library with rollback on failure."""

    # Move files to library
    library_path = await self.beets.import_album(path, move=True)
    original_path = path  # Keep reference for potential rollback

    try:
        # Get metadata
        tracks_metadata = await self.exiftool.get_album_metadata(library_path)

        # Create database records
        album = await self.import_service.import_album(
            path=library_path,
            tracks_metadata=tracks_metadata,
            source=source,
            source_url=source_url,
            imported_by=user_id,
            confidence=confidence
        )

        # Fetch artwork
        await self._ensure_artwork(album)

        return album

    except Exception as e:
        # ROLLBACK: Move files back to original location
        logger.error(f"Import failed after file move, rolling back: {e}")

        try:
            if library_path.exists():
                # Create original parent if needed
                original_path.parent.mkdir(parents=True, exist_ok=True)

                # Move back
                shutil.move(str(library_path), str(original_path))
                logger.info(f"Rolled back file move: {library_path} -> {original_path}")

                # Clean up empty directories in library
                artist_dir = library_path.parent
                if artist_dir.exists() and not any(artist_dir.iterdir()):
                    artist_dir.rmdir()
        except Exception as rollback_error:
            logger.critical(
                f"CRITICAL: Rollback failed! Orphaned files at {library_path}. "
                f"Rollback error: {rollback_error}"
            )

        raise  # Re-raise the original exception
```

### Step 3.3: Consider the download staging directory

For downloads, the original path is in `/music/downloads/` which gets cleaned up. You may want to move failed imports to a `/music/import/failed/` directory instead:

```python
except Exception as e:
    logger.error(f"Import failed after file move: {e}")

    try:
        if library_path.exists():
            # Move to failed imports folder instead of back to downloads
            failed_dir = Path(settings.IMPORT_PATH) / "failed"
            failed_dir.mkdir(parents=True, exist_ok=True)

            failed_path = failed_dir / library_path.name
            shutil.move(str(library_path), str(failed_path))
            logger.info(f"Moved failed import to: {failed_path}")
    except Exception as rollback_error:
        logger.critical(f"Cleanup failed: {rollback_error}")

    raise
```

---

## Phase 4: Fix Review Retry Bug

**Problem:** When a review import fails after files are moved, the review stays "pending" allowing retry. But the files are already in the library, so retry fails or creates duplicates.

**File:** `backend/app/tasks/imports.py`

### Step 4.1: Understand the current flow

Find `process_review()` (around line 240). The issue:
- Files are moved to library (line 252-263)
- If DB import fails (line 268), exception is caught
- Review status never updated (stays "pending")
- User can retry, but files already exist

### Step 4.2: Add proper error status handling

Update the exception handler to mark the review as failed:

```python
async def run():
    async with get_async_session() as db:
        # ... existing setup code ...

        try:
            # Move files to library
            if action == "manual" and metadata:
                library_path = await beets.import_with_metadata(
                    folder, metadata, move=True
                )
            else:
                library_path = await beets.import_album(folder, move=True)

            # Get metadata and import
            tracks_metadata = await exiftool.get_album_metadata(library_path)
            album = await import_service.import_album(
                path=library_path,
                tracks_metadata=tracks_metadata,
                source="import",
                source_url="",
                confidence=confidence
            )

            # Fetch artwork
            if not album.artwork_path:
                artwork = await import_service.fetch_artwork_if_missing(album)
                if artwork:
                    album.artwork_path = artwork

            # Mark review as approved
            review.status = "approved"
            review.album_id = album.id
            review.processed_at = datetime.utcnow()
            db.commit()

            return {"status": "imported", "album_id": album.id}

        except Exception as e:
            logger.error(f"Review processing failed: {e}")

            # IMPORTANT: Mark review as failed, not pending
            review.status = "failed"
            review.error_message = str(e)[:500]  # Truncate long errors
            review.processed_at = datetime.utcnow()
            db.commit()

            # Try to move files to failed folder for manual recovery
            if 'library_path' in locals() and library_path.exists():
                try:
                    failed_dir = Path(settings.IMPORT_PATH) / "failed"
                    failed_dir.mkdir(parents=True, exist_ok=True)
                    failed_path = failed_dir / library_path.name
                    shutil.move(str(library_path), str(failed_path))
                    logger.info(f"Moved failed import to: {failed_path}")
                except Exception as move_error:
                    logger.error(f"Could not move failed files: {move_error}")

            return {"status": "failed", "error": str(e)}
```

### Step 4.3: Add "failed" status to the Review model

**File:** `backend/app/models/review.py` (or wherever the Review model is)

Ensure the status field can accept "failed":

```python
class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"  # ADD THIS
```

### Step 4.4: Update the API to show failed reviews

**File:** `backend/app/api/review.py`

Add an endpoint or filter to see failed reviews:

```python
@router.get("/failed")
async def list_failed_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    """List reviews that failed during processing."""
    reviews = db.query(Review).filter(Review.status == "failed").all()
    return reviews
```

---

## Phase 5: Add Missing Tests

### 5.1: CLI Import End-to-End Test

**File:** `backend/tests/test_cli_import.py` (new file)

```python
import pytest
from pathlib import Path
from click.testing import CliRunner
from app.cli.admin import app
from app.models import Album

@pytest.fixture
def sample_audio_folder(tmp_path):
    """Create a folder with sample audio files for import."""
    album_dir = tmp_path / "Test Artist" / "Test Album"
    album_dir.mkdir(parents=True)

    # Create dummy audio file (you may need a real small audio file for beets)
    (album_dir / "01 - Track One.flac").write_bytes(b"fake audio content")
    (album_dir / "02 - Track Two.flac").write_bytes(b"fake audio content")

    return album_dir

@pytest.mark.asyncio
async def test_cli_import_creates_album_with_artwork(
    db_session, sample_audio_folder, mocker
):
    """CLI import should create album record and fetch artwork."""
    runner = CliRunner()

    # Mock beets to avoid actual audio processing
    mocker.patch(
        "app.services.beets.BeetsService.import_album",
        return_value=sample_audio_folder
    )
    mocker.patch(
        "app.services.beets.BeetsService.identify",
        return_value={"artist": "Test Artist", "album": "Test Album", "confidence": 0.95}
    )
    mocker.patch(
        "app.services.exiftool.ExifToolService.get_album_metadata",
        return_value=[{"title": "Track One"}, {"title": "Track Two"}]
    )

    # Run the CLI import
    result = runner.invoke(app, ["import", str(sample_audio_folder)])

    assert result.exit_code == 0
    assert "imported" in result.output.lower()

    # Verify album was created
    album = db_session.query(Album).filter(Album.title == "Test Album").first()
    assert album is not None
    assert album.artist.name == "Test Artist"

    # Verify artwork was attempted (may be None if no real artwork)
    # The important thing is that fetch_artwork_if_missing was called

@pytest.mark.asyncio
async def test_cli_import_with_missing_path_fails_gracefully(db_session):
    """CLI import with non-existent path should fail with clear error."""
    runner = CliRunner()

    result = runner.invoke(app, ["import", "/nonexistent/path"])

    assert result.exit_code != 0
    assert "not found" in result.output.lower() or "error" in result.output.lower()
```

### 5.2: GUI Review Approval Test

**File:** `backend/tests/test_review_api.py` (new file)

```python
import pytest
from fastapi.testclient import TestClient
from app.models import Review, Album

@pytest.fixture
def pending_review(db_session, tmp_path):
    """Create a pending review with files."""
    review_folder = tmp_path / "pending" / "test-album-123"
    review_folder.mkdir(parents=True)
    (review_folder / "track.flac").write_bytes(b"audio")

    review = Review(
        folder=str(review_folder),
        suggested_artist="Test Artist",
        suggested_album="Test Album",
        status="pending",
        confidence=0.85
    )
    db_session.add(review)
    db_session.commit()

    return review

@pytest.mark.asyncio
async def test_approve_review_creates_album(
    client: TestClient, db_session, pending_review, auth_headers, mocker
):
    """Approving a review should create an album and update review status."""
    # Mock external services
    mocker.patch("app.services.beets.BeetsService.import_with_metadata")
    mocker.patch("app.services.exiftool.ExifToolService.get_album_metadata", return_value=[])

    response = client.post(
        f"/api/review/{pending_review.id}/approve",
        json={"artist": "Test Artist", "album": "Test Album"},
        headers=auth_headers
    )

    assert response.status_code == 200

    # Verify review status updated
    db_session.refresh(pending_review)
    assert pending_review.status == "approved"

    # Verify album created
    album = db_session.query(Album).filter(Album.title == "Test Album").first()
    assert album is not None

@pytest.mark.asyncio
async def test_approve_review_failure_marks_as_failed(
    client: TestClient, db_session, pending_review, auth_headers, mocker
):
    """If import fails, review should be marked as failed, not pending."""
    # Mock beets to fail
    mocker.patch(
        "app.services.beets.BeetsService.import_with_metadata",
        side_effect=Exception("Beets failed")
    )

    response = client.post(
        f"/api/review/{pending_review.id}/approve",
        json={"artist": "Test Artist", "album": "Test Album"},
        headers=auth_headers
    )

    # Should return error
    assert response.status_code == 500

    # Review should be marked as failed, not pending
    db_session.refresh(pending_review)
    assert pending_review.status == "failed"
    assert "Beets failed" in pending_review.error_message

@pytest.mark.asyncio
async def test_reject_review_deletes_files(
    client: TestClient, db_session, pending_review, auth_headers
):
    """Rejecting a review with delete_files=True should remove files."""
    folder = Path(pending_review.folder)
    assert folder.exists()

    response = client.post(
        f"/api/review/{pending_review.id}/reject",
        json={"delete_files": True},
        headers=auth_headers
    )

    assert response.status_code == 200

    db_session.refresh(pending_review)
    assert pending_review.status == "rejected"
    assert not folder.exists()
```

### 5.3: Download-to-Import Flow Test

**File:** `backend/tests/test_download_import.py` (new file)

```python
import pytest
from pathlib import Path
from app.services.download import DownloadService
from app.models import Album, Download

@pytest.fixture
def download_service(db_session):
    return DownloadService(db_session)

@pytest.mark.asyncio
async def test_download_import_rollback_on_db_failure(
    download_service, db_session, tmp_path, mocker
):
    """If DB import fails after file move, files should be rolled back."""
    # Setup: Create a "downloaded" album
    download_folder = tmp_path / "downloads" / "test-album"
    download_folder.mkdir(parents=True)
    (download_folder / "track.flac").write_bytes(b"audio")

    library_path = tmp_path / "library" / "Test Artist" / "Test Album"

    # Mock beets to "move" files
    async def mock_import(path, move=True):
        library_path.mkdir(parents=True, exist_ok=True)
        for f in path.iterdir():
            (library_path / f.name).write_bytes(f.read_bytes())
        return library_path

    mocker.patch.object(download_service.beets, "import_album", mock_import)
    mocker.patch.object(download_service.exiftool, "get_album_metadata", return_value=[])

    # Make DB import fail
    mocker.patch.object(
        download_service.import_service,
        "import_album",
        side_effect=Exception("DB connection failed")
    )

    # Run import - should fail but rollback files
    with pytest.raises(Exception, match="DB connection failed"):
        await download_service._import_album(
            download_folder, source="test", source_url=""
        )

    # Files should be in failed folder, not library
    assert not library_path.exists()
    failed_dir = Path(download_service.settings.IMPORT_PATH) / "failed"
    assert (failed_dir / "Test Album").exists()
```

---

## Testing Your Changes

### Run All Tests

```bash
cd backend
pytest tests/ -v
```

### Run Specific Test Files

```bash
# Test deletion
pytest tests/test_library.py -v -k "delete"

# Test CLI import
pytest tests/test_cli_import.py -v

# Test review API
pytest tests/test_review_api.py -v

# Test download flow
pytest tests/test_download_import.py -v
```

### Manual Testing Checklist

1. **Deletion:**
   - [ ] Delete an album via API - verify files AND DB record removed
   - [ ] Make a folder read-only, try to delete - verify error returned and DB record remains
   - [ ] Check for orphaned files in `/music/artists/`

2. **CLI Import:**
   - [ ] Run `python -m app.cli.admin import /path/to/album`
   - [ ] Verify album appears in database
   - [ ] Verify artwork was fetched (check `artwork_path` in DB)

3. **Review Flow:**
   - [ ] Create a review (put folder in `/music/import/pending/`)
   - [ ] Approve via GUI - verify album created with artwork
   - [ ] Reject via GUI with delete_files=True - verify files removed
   - [ ] Simulate failure during approve - verify review shows "failed" not "pending"

4. **Download Flow:**
   - [ ] Trigger a download (Qobuz/Lidarr/YouTube)
   - [ ] Verify album imported with artwork
   - [ ] Simulate DB failure - verify files not orphaned in library

---

## Verification Checklist

Before submitting your changes:

- [ ] All existing tests pass
- [ ] New tests added for each fix
- [ ] No orphaned files after failed operations
- [ ] Delete returns proper success/failure status
- [ ] CLI imports have artwork
- [ ] Failed reviews show "failed" status, not "pending"
- [ ] Import rollback moves files to `/failed/` folder
- [ ] Logging is clear for debugging
- [ ] No breaking changes to API contracts

---

## Common Pitfalls

1. **Don't forget database commits:** After changing review status, call `db.commit()`

2. **Handle Path objects vs strings:** Some methods expect `Path`, others `str`. Be consistent.

3. **Test with real audio files:** Beets may behave differently with fake audio content. Use small real audio files for integration tests.

4. **SMB mount artifacts:** The `.smbdelete*` files are real. Don't remove that handling.

5. **Race conditions:** Multiple users could try to delete/import the same album. Consider adding database locks for critical operations.

---

## Getting Help

- Check existing code in similar services for patterns
- The `download.py` service is the most complete implementation
- Look at `import_service.py` for artwork fetching patterns
- Check the Celery task patterns in `tasks/` for async operations
