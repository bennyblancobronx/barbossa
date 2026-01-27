# Bugfix Spec 011: Library Sync Issues

**Version:** 0.1.115
**Date:** 2026-01-26
**Priority:** High
**Estimated Scope:** 3 issues, multiple files

---

## Overview

Three bugs identified in the library synchronization system:

1. **Artist Auto-Heart** - New albums not added to users who hearted the artist
2. **Master Library Updates** - Frontend may not receive real-time updates
3. **De-Dupe Race Condition** - Duplicate albums can be imported simultaneously

---

## Issue 1: Artist Auto-Heart

### Problem

When a user hearts an artist, only existing albums are added to their library. If new music is later added to the master library for that artist, it does NOT automatically appear in the user's library.

### Current Behavior

File: `backend/app/services/user_library.py:341-362`

```python
def heart_artist(self, user_id: int, artist_id: int, username: str) -> int:
    """Heart all albums by an artist. Returns count of newly hearted albums."""
    albums = self.db.query(Album).filter(Album.artist_id == artist_id).all()
    count = 0
    for album in albums:
        try:
            if self.heart_album(user_id, album.id, username):
                count += 1
        except ValueError:
            pass
    return count
```

This only hearts albums that exist AT THE TIME of the heart action. No persistence of "I want all future albums by this artist."

### Expected Behavior

When a user hearts an artist AND a new album is imported for that artist:
1. System should detect all users who have hearted that artist
2. Automatically add the new album to each user's library
3. Create symlinks for each user
4. Send WebSocket notification to affected users

### Solution

#### Step 1: Create `user_artists` Table

Create new migration: `backend/alembic/versions/011_user_artists.py`

```python
"""Add user_artists table for persistent artist hearts

Revision ID: 011_user_artists
Revises: 010_add_is_admin_user
"""
from alembic import op
import sqlalchemy as sa

revision = '011_user_artists'
down_revision = '010_add_is_admin_user'

def upgrade():
    op.create_table(
        'user_artists',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('artist_id', sa.Integer(), nullable=False),
        sa.Column('auto_add_new', sa.Boolean(), default=True, nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['artist_id'], ['artists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'artist_id')
    )
    op.create_index('ix_user_artists_artist_id', 'user_artists', ['artist_id'])

def downgrade():
    op.drop_table('user_artists')
```

#### Step 2: Create Model

Create file: `backend/app/models/user_artists.py`

```python
"""User artists junction table for persistent artist hearts."""
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from app.database import Base

user_artists = Table(
    "user_artists",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("artist_id", Integer, ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True),
    Column("auto_add_new", Boolean, default=True, nullable=False),
    Column("added_at", DateTime(timezone=True), server_default=func.now()),
)
```

#### Step 3: Update `user_library.py`

Add imports at top:
```python
from app.models.user_artists import user_artists
```

Modify `heart_artist()` method:
```python
def heart_artist(self, user_id: int, artist_id: int, username: str, auto_add_new: bool = True) -> int:
    """Heart all albums by an artist and optionally subscribe to new releases.

    Args:
        user_id: User ID
        artist_id: Artist ID
        username: Username for symlinks
        auto_add_new: If True, auto-add future albums (default True)

    Returns:
        Count of newly hearted albums
    """
    from app.models.artist import Artist

    artist = self.db.query(Artist).filter(Artist.id == artist_id).first()
    if not artist:
        raise ValueError("Artist not found")

    # Add to user_artists table (upsert)
    existing = self.db.execute(
        select(user_artists).where(
            user_artists.c.user_id == user_id,
            user_artists.c.artist_id == artist_id
        )
    ).first()

    if not existing:
        self.db.execute(
            insert(user_artists).values(
                user_id=user_id,
                artist_id=artist_id,
                auto_add_new=auto_add_new
            )
        )
    else:
        # Update auto_add_new setting
        self.db.execute(
            user_artists.update().where(
                user_artists.c.user_id == user_id,
                user_artists.c.artist_id == artist_id
            ).values(auto_add_new=auto_add_new)
        )

    self.db.commit()

    # Heart all existing albums
    albums = self.db.query(Album).filter(Album.artist_id == artist_id).all()
    count = 0
    for album in albums:
        try:
            if self.heart_album(user_id, album.id, username):
                count += 1
        except ValueError:
            pass

    # Log activity
    activity = ActivityService(self.db)
    activity.log(user_id, "heart", "artist", artist_id, {"album_count": count, "auto_add_new": auto_add_new})

    return count
```

Modify `unheart_artist()` method to remove from `user_artists`:
```python
def unheart_artist(self, user_id: int, artist_id: int, username: str) -> int:
    """Unheart all albums by artist and unsubscribe from new releases."""
    # ... existing album unheart logic ...

    # Remove from user_artists table
    self.db.execute(
        delete(user_artists).where(
            user_artists.c.user_id == user_id,
            user_artists.c.artist_id == artist_id
        )
    )
    self.db.commit()

    return count
```

Add new method:
```python
def get_users_following_artist(self, artist_id: int) -> list[tuple[int, str]]:
    """Get all users who have auto_add_new=True for an artist.

    Returns:
        List of (user_id, username) tuples
    """
    result = self.db.execute(
        select(User.id, User.username)
        .join(user_artists, User.id == user_artists.c.user_id)
        .where(
            user_artists.c.artist_id == artist_id,
            user_artists.c.auto_add_new == True
        )
    ).fetchall()
    return [(row[0], row[1]) for row in result]
```

#### Step 4: Hook into Import Pipeline

File: `backend/app/services/import_service.py`

Add method:
```python
async def auto_heart_for_followers(self, album: Album) -> int:
    """Auto-heart album for users following the artist.

    Args:
        album: Newly imported album

    Returns:
        Count of users who received the album
    """
    from app.services.user_library import UserLibraryService

    user_lib = UserLibraryService(self.db)
    followers = user_lib.get_users_following_artist(album.artist_id)

    count = 0
    for user_id, username in followers:
        try:
            if user_lib.heart_album(user_id, album.id, username):
                count += 1
                # Notify user via WebSocket
                await notify_user(user_id, {
                    "title": "New Album Added",
                    "message": f"'{album.title}' by {album.artist.name} added to your library",
                    "album_id": album.id
                })
        except Exception as e:
            logger.warning(f"Failed to auto-heart album {album.id} for user {user_id}: {e}")

    return count
```

#### Step 5: Call Auto-Heart After Import

Files to modify:
- `backend/app/tasks/imports.py` - Line 166 (after `import_service.import_album()`)
- `backend/app/services/download.py` - Line 306 (after `import_service.import_album()`)
- `backend/app/watcher.py` - Line 129 (after `import_service.import_album()`)

Add after each `import_album()` call:
```python
# Auto-heart for users following this artist
auto_hearted = await import_service.auto_heart_for_followers(album)
if auto_hearted > 0:
    logger.info(f"Auto-hearted album {album.id} for {auto_hearted} users")
```

#### Step 6: Update API Endpoint (Optional Enhancement)

File: `backend/app/api/library.py:502-516`

Add optional query param:
```python
@router.post("/me/library/artists/{artist_id}", response_model=MessageResponse)
def heart_artist(
    artist_id: int,
    auto_add_new: bool = Query(True, description="Auto-add future albums"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Heart all albums by an artist (add to user library)."""
    service = UserLibraryService(db)
    try:
        count = service.heart_artist(user.id, artist_id, user.username, auto_add_new)
        # ...
```

---

## Issue 2: Master Library Updates

### Problem

When new music is imported, the `broadcast_library_update()` function exists but is NEVER called. The `import:complete` event is broadcast but frontend may not handle it properly for UI refresh.

### Current Behavior

File: `backend/app/websocket.py:197-210`

```python
async def broadcast_library_update(
    entity_type: str,
    entity_id: int,
    action: str
):
    """Broadcast library change to all users."""
    message = {
        "type": "library:updated",
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    await manager.broadcast_all(message)
```

This function is defined but NEVER called anywhere in the codebase.

### Solution

#### Option A: Use Existing `broadcast_library_update()`

Add calls after imports in these files:

File: `backend/app/tasks/imports.py` - After line 185:
```python
await broadcast_import_complete(...)
await broadcast_library_update("album", album.id, "created")  # ADD THIS
```

File: `backend/app/services/download.py` - After album creation completes
File: `backend/app/watcher.py` - After line 142

#### Option B: Verify Frontend Handles `import:complete`

Check frontend file (likely `frontend/src/hooks/useWebSocket.js` or similar):

```javascript
// Frontend should handle this event:
socket.on('import:complete', (data) => {
    // Refresh library data or add to local state
    queryClient.invalidateQueries(['library', 'albums']);
    queryClient.invalidateQueries(['library', 'artists']);
});
```

### Recommended Approach

Do BOTH:
1. Call `broadcast_library_update()` for granular updates
2. Ensure frontend handles both event types

---

## Issue 3: De-Dupe Race Condition

### Problem

Two simultaneous imports of the same album can both pass the `find_duplicate()` check before either completes, resulting in duplicate entries.

### Current Behavior

File: `backend/app/services/import_service.py:31-56`

```python
def find_duplicate(self, artist: str, album: str) -> Optional[Album]:
    """Check if album already exists."""
    norm_artist = normalize_text(artist)
    norm_album = normalize_text(album)

    # Check import history first
    existing = self.db.query(ImportHistory).filter(
        ImportHistory.artist_normalized == norm_artist,
        ImportHistory.album_normalized == norm_album
    ).first()
    # ...
```

The check is application-level only. No database constraint prevents duplicates.

### Evidence of Missing Constraint

File: `backend/alembic/versions/001_initial_schema.py`

Albums table has NO unique constraint on `(artist_id, normalized_title)`:
```python
op.create_table(
    'albums',
    # ... no UniqueConstraint
)
```

### Solution

#### Step 1: Add Database Constraint

Create migration: `backend/alembic/versions/012_album_unique_constraint.py`

```python
"""Add unique constraint to prevent duplicate albums

Revision ID: 012_album_unique_constraint
Revises: 011_user_artists
"""
from alembic import op
import sqlalchemy as sa

revision = '012_album_unique_constraint'
down_revision = '011_user_artists'

def upgrade():
    # Add unique constraint on artist_id + normalized_title
    op.create_unique_constraint(
        'uq_album_artist_title',
        'albums',
        ['artist_id', 'normalized_title']
    )

def downgrade():
    op.drop_constraint('uq_album_artist_title', 'albums', type_='unique')
```

#### Step 2: Update Album Model

File: `backend/app/models/album.py`

Add at end of class (before `__repr__`):
```python
__table_args__ = (
    sa.UniqueConstraint('artist_id', 'normalized_title', name='uq_album_artist_title'),
)
```

#### Step 3: Handle Constraint Violation in Import

File: `backend/app/services/import_service.py`

Update `import_album()` to catch the constraint violation:

```python
from sqlalchemy.exc import IntegrityError

async def import_album(self, ...) -> Album:
    """Import album and tracks to database."""
    # ... existing code up to self.db.commit() ...

    try:
        self.db.commit()
    except IntegrityError as e:
        self.db.rollback()
        if 'uq_album_artist_title' in str(e):
            # Race condition - album was inserted by another process
            # Fetch the existing album and return it
            existing = self.find_duplicate(
                first_track.get("artist") or "Unknown Artist",
                album_title
            )
            if existing:
                logger.info(f"Duplicate detected via constraint: {existing.id}")
                return existing
        raise

    return album
```

#### Step 4: Add Similar Constraint to ImportHistory (Optional)

If you want belt-and-suspenders protection:

```python
# In migration
op.create_unique_constraint(
    'uq_import_history_album',
    'import_history',
    ['artist_normalized', 'album_normalized', 'album_id']
)
```

---

## Files to Modify Summary

### New Files
- `backend/alembic/versions/011_user_artists.py`
- `backend/alembic/versions/012_album_unique_constraint.py`
- `backend/app/models/user_artists.py`

### Modified Files
- `backend/app/models/album.py` - Add `__table_args__`
- `backend/app/services/user_library.py` - Update heart_artist, add get_users_following_artist
- `backend/app/services/import_service.py` - Add auto_heart_for_followers, handle IntegrityError
- `backend/app/tasks/imports.py` - Call auto_heart and broadcast_library_update
- `backend/app/services/download.py` - Call auto_heart and broadcast_library_update
- `backend/app/watcher.py` - Call auto_heart and broadcast_library_update
- `backend/app/api/library.py` - Add auto_add_new param (optional)

### Frontend (Verify)
- WebSocket handler for `import:complete` and `library:updated` events

---

## Testing Checklist

### Issue 1: Artist Auto-Heart
- [ ] Heart an artist -> verify user_artists row created
- [ ] Import new album for that artist -> verify auto-added to user library
- [ ] Verify symlinks created for auto-added album
- [ ] Verify WebSocket notification sent
- [ ] Unheart artist -> verify user_artists row removed
- [ ] Import album after unheart -> verify NOT auto-added

### Issue 2: Library Updates
- [ ] Import album -> verify `library:updated` WebSocket event sent
- [ ] Frontend UI updates without manual refresh

### Issue 3: De-Dupe
- [ ] Attempt concurrent import of same album -> only one succeeds
- [ ] Verify error handled gracefully (returns existing album)
- [ ] Run: `SELECT artist_id, normalized_title, COUNT(*) FROM albums GROUP BY 1,2 HAVING COUNT(*) > 1` -> should return 0 rows

---

## Migration Steps

1. Stop Barbossa services
2. Run migrations: `alembic upgrade head`
3. Verify tables: `\d user_artists` and check albums constraint
4. Restart services
5. Test each issue

---

## Rollback Plan

If issues arise:
```bash
alembic downgrade 010_add_is_admin_user
```

This will drop the new table and constraint.
