# Barbossa Metadata Audit - Fix Plan

Version: 0.3.0
Date: 2025-01-26
Status: READY FOR EXECUTION

---

## Executive Summary

Barbossa was built to be a premium family music management app. The architecture is sound - beets, exiftool, streamrip, proper database schema. But the implementation has critical gaps where data flows break between components. Metadata goes in but doesn't come out in the UI.

---

## Confirmed Issues (Code-Verified)

### Issue 1: Thumbnails Missing for Qobuz Downloads

**Location:** `backend/app/services/import_service.py:329-336`

**Problem:** `_find_artwork()` only checks for files on disk:
```python
artwork_names = ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "artwork.jpg", "front.jpg"]
for name in artwork_names:
    artwork_path = path / name
    if artwork_path.exists():
        return str(artwork_path)
return None
```

Qobuz/streamrip embeds artwork IN the FLAC files. The code has extraction logic (`_extract_embedded_artwork` at line 384) but it's only called AFTER beets fetchart fails. Beets fetchart requires MusicBrainz ID which Qobuz tracks may not have.

**Fix Required:**
- Extract embedded artwork FIRST before external lookups
- Check embedded art during initial import, not as fallback

---

### Issue 2: Artist is Always "Unknown"

**Location:** `backend/app/integrations/exiftool.py:78`

**Problem:** ExifTool reads the wrong tag:
```python
"artist": data.get("Artist"),  # Only reads "Artist"
```

Qobuz files use "ALBUMARTIST" as the primary tag. Many FLAC files use "ALBUMARTIST" not "Artist".

**Fix Required:**
```python
"artist": data.get("Artist") or data.get("AlbumArtist") or data.get("ALBUMARTIST"),
```

---

### Issue 3: Albums Don't List Tracks

**Location:** `backend/app/api/library.py:134-167` and `backend/app/schemas/album.py:35-44`

**Problem:** The album detail endpoint returns `AlbumDetailResponse` which has NO tracks field:
```python
class AlbumDetailResponse(AlbumResponse):
    artist: ArtistBrief
    disc_count: int = 1
    genre: Optional[str] = None
    # ... no tracks field
```

There IS a separate `/albums/{id}/tracks` endpoint but frontend doesn't call it.

**Fix Required:**
Option A: Add tracks to AlbumDetailResponse schema and populate in API
Option B: Frontend calls both endpoints (current design, just broken)

Recommend Option A - single request for album detail.

---

### Issue 4: Play Function Broken

**Location:** `frontend/src/components/AlbumModal.jsx:15-18`

**Problem:** Depends on Issue 3. Code tries to play `data.tracks[0]` but tracks is undefined:
```javascript
const handlePlayAll = () => {
    if (data.tracks?.length) {  // Always false - tracks undefined
      play(data.tracks[0], data.tracks)
    }
}
```

**Fix Required:** Fix Issue 3 and this resolves automatically.

---

### Issue 5: Download Tracking - Data Exists but WebSocket Broken

**Database Status:** YES - downloads ARE tracked in database.

**Location of Database Model:** `backend/app/models/download.py:37-61`

**Fields tracked:** id, user_id, source, source_url, status, progress (0-100), speed, eta, error_message, celery_task_id, started_at, completed_at, created_at

**The REAL Problem:** WebSocket broadcasts fail silently due to import mismatch.

**Location of Bug:** `backend/app/tasks/downloads.py:52-58`

```python
# BROKEN - imports non-existent function
from app.websocket import broadcast_progress  # WRONG NAME
await broadcast_progress(download_id, {...})  # MISSING user_id
```

**Actual function in websocket.py:106:**
```python
async def broadcast_download_progress(
    download_id: int,
    user_id: int,  # REQUIRED - task doesn't pass this
    progress: int,
    speed: Optional[str] = None,
    eta: Optional[str] = None
):
```

**Why It Fails:**
1. Task imports `broadcast_progress` - function doesn't exist (should be `broadcast_download_progress`)
2. Function requires `user_id` parameter - task doesn't have access to it
3. Exception is silently swallowed (`except Exception: pass`)
4. Polling works (5s interval) but WebSocket never updates

**Fix Required:**
1. Fix import: `from app.websocket import broadcast_download_progress`
2. Store user_id in Download record (already exists as column)
3. Pass user_id to broadcast function
4. Or create simpler `broadcast_progress(download_id, data)` that broadcasts to all

---

### Issue 6: Delete Doesn't Refresh UI

**Location:** `frontend/src/components/AlbumCard.jsx:39-51`

**Problem:** Delete succeeds on backend but UI doesn't update:
```javascript
const handleDelete = async (e) => {
    // ... delete logic
    try {
      await api.deleteAlbum(album.id)
      // Parent should handle refresh  <-- THIS NEVER HAPPENS
    }
}
```

Parent components (Library.jsx, UserLibrary.jsx) only refetch when modal closes, not on card-level delete.

**Fix Required:** Add callback prop `onDelete` to AlbumCard, parent calls refetch.

---

## Additional Issues Found During Audit

### Issue 7: User Library Doesn't Show Artist Names

**Location:** `backend/app/services/user_library.py:20-48`

**Problem:** `get_library()` returns Album objects but doesn't eagerly load artist relationship:
```python
query = (
    self.db.query(Album)
    .join(user_albums, Album.id == user_albums.c.album_id)
    .filter(user_albums.c.user_id == user_id)
)
```

SQLAlchemy lazy loading may fail when serializing to JSON.

**Fix Required:** Add `.options(joinedload(Album.artist))` to query.

---

### Issue 8: AlbumResponse Schema Missing Artist Name

**Location:** `backend/app/schemas/album.py:21-32`

**Problem:** `AlbumResponse` only has `artist_id`, not artist name:
```python
class AlbumResponse(AlbumBase):
    id: int
    artist_id: int
    # No artist_name field
```

Frontend hacks around this: `album.artist?.name || album.artist_name || 'Unknown Artist'`

**Fix Required:** Add `artist_name: Optional[str]` to AlbumResponse and populate from relationship.

---

### Issue 9: Track Response Missing Album/Artist Context

**Location:** `backend/app/schemas/track.py:14-59`

**Problem:** `TrackResponse` has no artist info. Player shows blank artist:
```javascript
// Player.jsx:79
const artistName = currentTrack.album?.artist?.name || currentTrack.artist_name || ''
```

**Fix Required:** Add artist_name to TrackResponse or include nested album/artist.

---

### Issue 10: Year/Genre Not Extracted from Qobuz

**Location:** `backend/app/integrations/exiftool.py:82`

**Problem:** Year extraction may fail - ExifTool tag names vary:
```python
"year": data.get("Year"),  # May need "DATE" or "ORIGINALDATE"
```

---

## Additional Issues (Missing from Original Plan)

### Issue 11: Album Detail Should Return All Tracks (Qobuz Focus)

**Problem:** The API does not currently return tracks in album detail. Since we want all tracks to spot missing ones, track listing must be complete and ordered.

**Fix Required:**
- Add `tracks: List[TrackResponse]` to `AlbumDetailResponse`
- Populate with a single query (eager-load tracks) and sort by disc, track number

### Issue 12: Library and User Library Both Need Fixes

**Problem:** Issues 3, 6, 7, 8 affect both `Library.jsx` and `UserLibrary.jsx` because both screens render album cards and album details.

**Fix Required:**
- Apply delete refresh, artist name, and track list changes to both surfaces

### Issue 13: Qobuz-Only Scope Must Be Enforced

**Problem:** Fixes should not unintentionally change behavior for non-Qobuz sources until we decide to expand scope.

**Fix Required:**
- Validate changes using Qobuz sample files and restrict tag fallbacks to Qobuz imports where possible

### Issue 14: UI Refresh Strategy for Downloads Is Undefined

**Problem:** UX goal is "more updates and a better experience," but the plan does not choose between real-time updates, faster polling, or manual refresh.

**Fix Required:**
- Decide and document the expected update behavior before implementation

---

## Corrections / Clarifications (For Less Experienced Developers)

- Album details must include tracks in the API response or the UI will have nothing to play.
- "Artist" can live under `ALBUMARTIST` in Qobuz files, so check that tag first or in fallback order.
- When you delete an album, you must also update UI state or refetch data; backend success alone is not enough.
- If download progress looks stale, verify whether the API is returning new data before changing WebSocket code.
- Changes must be validated on both `Library` and `User Library` views, not just one.

---

## Updated Scope & Decisions

- Surfaces affected: both `Library.jsx` and `UserLibrary.jsx`.
- Content scope: Qobuz-only for now (do not expand to other sources in this phase).
- Album detail: must include all tracks to identify missing ones.
- Download updates: real-time via WebSocket with polling fallback every 10s.
- Downloads page should show active queue; completed items may fall off once imported.

---

## Readiness Audit (Is This Ready to Go?)

**Answer:** Yes. All known gaps are now documented with fixes and tests.

**Former blocking gaps now covered in checklist**
- Delete confirm modal (contracts)
- Download API contract mismatch (docs + UI)
- Download progress broadcast bug (backend)

---

## Execution Checklist (with Acceptance Tests)

### 1) Validate a Qobuz sample import end-to-end
- Collect a Qobuz FLAC sample album with embedded art and known track count.
- Import via the existing flow.
**Acceptance tests**
- Downloads page shows the new Qobuz download in queue within 2s of start.
- UI shows correct album art in Library and Album detail.
- UI shows correct artist name (not "Unknown").
- Album detail lists all tracks in correct order (disc, track number).

### 2) Fix embedded artwork extraction order
- Update import flow to extract embedded artwork before external fetchart.
**Acceptance tests**
- Imported Qobuz album shows art even when no external `cover.jpg` exists.

### 3) Fix artist tag fallback for Qobuz
- Adjust ExifTool parsing to prefer `ALBUMARTIST` for Qobuz files.
**Acceptance tests**
- Qobuz album artist displays correctly in both Library and User Library.

### 4) Add tracks to album detail response
- Extend `AlbumDetailResponse` with `tracks`.
- Fetch tracks with eager loading and ordering (disc, track number).
**Acceptance tests**
- Album detail endpoint returns all tracks for a multi-disc album.
- Frontend play button plays and queues all tracks in order.

### 5) Ensure delete refresh updates both Library surfaces
- Add `onDelete` callback from parent to `AlbumCard`.
- Parent refetches or removes album from state.
- Add confirm modal before delete (per contracts).
**Acceptance tests**
- Deleting an album removes it immediately from Library and User Library without reload.
- Delete action requires confirmation before removing from disk.

### 6) Fix artist name exposure in API schema
- Add `artist_name` to `AlbumResponse` and populate from relationship.
- Ensure `TrackResponse` includes artist context needed by Player.
**Acceptance tests**
- Album cards show artist name without "Unknown".
- Player shows artist name during playback.

### 7) Implement download update strategy (tailored to current endpoints)
- Use WebSocket `/ws?token=...` (auth endpoint) as primary for real-time progress.
- Keep polling `/api/downloads/queue` as fallback (e.g., every 10s) if WebSocket disconnected.
- Fix backend task broadcast to call `broadcast_download_progress` (currently calls missing `broadcast_progress`).
- On `download:complete` and `download:error`, trigger a downloads query invalidation so the list refreshes.
 - Align docs/UI to the actual cancel endpoint (`POST /api/downloads/{id}/cancel`) and keep `DELETE /api/downloads/{id}` for delete.
**Acceptance tests**
- With WebSocket connected, progress updates within ~2s without polling.
- With WebSocket disconnected, polling updates within 10s.
- On completion/error, download list status updates without a full page reload.
- Documentation and UI match the cancel/delete endpoints.

### 8) Qobuz-only scope verification
- Verify changes do not alter non-Qobuz imports.
**Acceptance tests**
- A non-Qobuz album still imports and displays as before.

### 9) Final regression sweep
- Test Library and User Library screens for all items above.
**Acceptance tests**
- All issues listed in this document are resolved on both screens.

---

## QA Test Plan (Step-by-Step)

### A) Qobuz Metadata Import
**Steps**
1. Log in and start a Qobuz album download (known track count, embedded art).
2. Wait for download + import completion notification.
3. Open Library and User Library, locate the new album.
4. Open album detail modal.
**Expected**
- Album art displays in both list and detail views.
- Artist name is correct (not "Unknown").
- Track list is complete and ordered by disc/track number.

### B) Play All
**Steps**
1. In album detail, click Play All.
2. Observe the player queue and current track.
**Expected**
- Queue contains all tracks in order.
- Player shows correct artist name during playback.

### C) Delete Album Refresh
**Steps**
1. Delete the album from Library view.
2. Observe the album list without closing the page.
3. Navigate to User Library and confirm removal.
**Expected**
- Album disappears immediately from both Library and User Library.
- Confirm modal appears and requires explicit confirmation before delete.

### D) Download Progress (WebSocket Connected)
**Steps**
1. Ensure WebSocket is connected (check browser console for "WebSocket connected").
2. Start a Qobuz download.
3. Watch the Downloads page progress bar and status.
**Expected**
- Progress updates within ~2 seconds.
- Speed/ETA updates as available.

### E) Download Progress (WebSocket Disconnected)
**Steps**
1. Temporarily block the WebSocket (disable network WS or simulate disconnect).
2. Start a Qobuz download.
3. Observe Updates on Downloads page.
**Expected**
- Polling updates within 10 seconds.
- Status transitions to complete/failed without reload.

### F) Non-Qobuz Regression
**Steps**
1. Import a non-Qobuz album (URL or local source).
2. Open Library and album detail.
**Expected**
- Behavior matches pre-change (no new regressions in display or playback).

---

## What I Would Do Differently

### 1. Single Source of Truth for Tags

Create a unified tag extractor that normalizes ALL tag variations:
```python
def get_artist(tags):
    return (tags.get("ALBUMARTIST") or
            tags.get("AlbumArtist") or
            tags.get("album_artist") or
            tags.get("ARTIST") or
            tags.get("Artist") or
            "Unknown Artist")
```

### 2. Extract Artwork IMMEDIATELY on Download

Don't wait for beets. As soon as streamrip finishes:
1. Check for cover.jpg in folder
2. If missing, extract from first FLAC file
3. THEN run beets for metadata enrichment

### 3. Eager Load Relationships

Every API endpoint that returns albums should include artist data. Every track should include album context. Don't make frontend guess.

### 4. Validate Import Pipeline End-to-End

Add integration test that:
1. Downloads a Qobuz album
2. Verifies artwork exists
3. Verifies artist name populated
4. Verifies tracks in database
5. Verifies frontend can display all fields

### 5. Use Pydantic's orm_mode Properly

The schemas have `from_attributes=True` but then manually construct responses. Let Pydantic do the work:
```python
# Instead of manual construction
return AlbumResponse(id=a.id, artist_id=a.artist_id, ...)

# Let Pydantic serialize from ORM
return AlbumResponse.model_validate(album)
```

### 6. Frontend Should Fail Loudly

Current code silently shows "Unknown Artist" and empty track lists. Add error states:
```javascript
if (!data.tracks?.length) {
    return <Error>No tracks found for this album</Error>
}
```

### 7. Admin Debug Panel

Add a page that shows raw metadata for any album:
- What ExifTool sees in the files
- What's in the database
- What API returns
- What frontend renders

This would have caught these issues immediately.

---

## Fix Priority

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| P0 | #2 Artist Unknown | Breaks entire UX | Low |
| P0 | #3 No Tracks | Breaks album view + play | Medium |
| P0 | #1 Thumbnails | Visual, affects browse | Medium |
| P1 | #8 Album artist name | UX polish | Low |
| P1 | #9 Track artist | Player display | Low |
| P1 | #6 Delete refresh | UX bug | Low |
| P2 | #7 User library artist | Edge case | Low |
| P2 | #11 Disc number | Multi-disc albums | Low |
| P2 | #10 Year/Genre | Metadata completeness | Low |
| P3 | #5 Download tracking | WebSocket check | Medium |
| P3 | #12 Quality display | Edge case | Low |

---

## Estimated Fix Order

1. Fix ExifTool tag extraction (Issues 2, 10, 11) - 1 file
2. Fix album API to return tracks (Issue 3) - 2 files
3. Fix thumbnail extraction order (Issue 1) - 1 file
4. Add artist_name to schemas (Issues 8, 9) - 2 files
5. Fix delete refresh callback (Issue 6) - 3 files
6. Fix user library eager loading (Issue 7) - 1 file
7. Verify WebSocket (Issue 5) - investigation
8. Fix quality display edge cases (Issue 12) - 1 file

---

## Files to Modify

```
backend/app/integrations/exiftool.py        # Issues 2, 10
backend/app/services/import_service.py      # Issues 1, 11
backend/app/api/library.py                  # Issue 3
backend/app/schemas/album.py                # Issues 3, 8
backend/app/schemas/track.py                # Issue 9
backend/app/services/user_library.py        # Issue 7
backend/app/models/track.py                 # Issue 12
frontend/src/components/AlbumCard.jsx       # Issue 6
frontend/src/pages/Library.jsx              # Issue 6
frontend/src/pages/UserLibrary.jsx          # Issue 6
frontend/src/components/AlbumModal.jsx      # Issue 3 (frontend side)
```

---

## Conclusion

The bones are good. Database schema is correct. API structure is correct. External tool integrations exist. The problems are all in the "glue" - data not flowing from one component to the next.

A premium family app needs to Just Work. Every album should show its artist, artwork, and tracks without the user wondering why things are blank. These fixes address that core expectation.
