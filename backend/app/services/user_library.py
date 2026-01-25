"""User library service for managing hearted albums/tracks."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import insert, delete, select
from app.models.user import User
from app.models.album import Album
from app.models.track import Track
from app.models.user_library import user_albums, user_tracks
from app.services.symlink import SymlinkService
from app.services.activity import ActivityService


class UserLibraryService:
    """Service for managing user's personal library (hearts)."""

    def __init__(self, db: Session):
        self.db = db
        self.symlink = SymlinkService()

    def get_library(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get user's hearted albums."""
        query = (
            self.db.query(Album)
            .join(user_albums, Album.id == user_albums.c.album_id)
            .filter(user_albums.c.user_id == user_id)
            .order_by(user_albums.c.added_at.desc())
        )

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        pages = (total + limit - 1) // limit

        # Mark all as hearted
        for album in items:
            album.is_hearted = True

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    def heart_album(self, user_id: int, album_id: int, username: str) -> bool:
        """Heart an album - add to user library and create symlinks."""
        # Check if already hearted
        existing = self.db.execute(
            select(user_albums).where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        ).first()

        if existing:
            return False  # Already hearted

        # Get album for path
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            raise ValueError("Album not found")

        # Add to database
        self.db.execute(
            insert(user_albums).values(user_id=user_id, album_id=album_id)
        )
        self.db.commit()

        # Create symlinks
        if album.path:
            self.symlink.create_album_links(username, album.path)

        # Log activity
        activity = ActivityService(self.db)
        activity.log(user_id, "heart", "album", album_id)

        return True

    def unheart_album(self, user_id: int, album_id: int, username: str) -> bool:
        """Unheart an album - remove from user library and delete symlinks."""
        # Get album for path
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            return False

        # Check if hearted
        existing = self.db.execute(
            select(user_albums).where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        ).first()

        if not existing:
            return False  # Not hearted

        # Remove from database
        self.db.execute(
            delete(user_albums).where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        )
        self.db.commit()

        # Remove symlinks
        if album.path:
            self.symlink.remove_album_links(username, album.path)

        # Log activity
        activity = ActivityService(self.db)
        activity.log(user_id, "unheart", "album", album_id)

        return True

    def is_album_hearted(self, user_id: int, album_id: int) -> bool:
        """Check if user has hearted an album."""
        result = self.db.execute(
            select(user_albums).where(
                user_albums.c.user_id == user_id,
                user_albums.c.album_id == album_id
            )
        ).first()
        return result is not None

    def heart_track(self, user_id: int, track_id: int, username: str) -> bool:
        """Heart an individual track."""
        # Check if already hearted
        existing = self.db.execute(
            select(user_tracks).where(
                user_tracks.c.user_id == user_id,
                user_tracks.c.track_id == track_id
            )
        ).first()

        if existing:
            return False  # Already hearted

        # Get track for path
        track = self.db.query(Track).filter(Track.id == track_id).first()
        if not track:
            raise ValueError("Track not found")

        # Add to database
        self.db.execute(
            insert(user_tracks).values(user_id=user_id, track_id=track_id)
        )
        self.db.commit()

        # Create symlink for individual track
        if track.path:
            self.symlink.create_track_link(username, track.path)

        # Log activity
        activity = ActivityService(self.db)
        activity.log(user_id, "heart", "track", track_id)

        return True

    def unheart_track(self, user_id: int, track_id: int, username: str) -> bool:
        """Unheart an individual track."""
        track = self.db.query(Track).filter(Track.id == track_id).first()
        if not track:
            return False

        existing = self.db.execute(
            select(user_tracks).where(
                user_tracks.c.user_id == user_id,
                user_tracks.c.track_id == track_id
            )
        ).first()

        if not existing:
            return False

        self.db.execute(
            delete(user_tracks).where(
                user_tracks.c.user_id == user_id,
                user_tracks.c.track_id == track_id
            )
        )
        self.db.commit()

        if track.path:
            self.symlink.remove_track_link(username, track.path)

        activity = ActivityService(self.db)
        activity.log(user_id, "unheart", "track", track_id)

        return True

    def is_track_hearted(self, user_id: int, track_id: int) -> bool:
        """Check if user has hearted a track."""
        result = self.db.execute(
            select(user_tracks).where(
                user_tracks.c.user_id == user_id,
                user_tracks.c.track_id == track_id
            )
        ).first()
        return result is not None

    def get_hearted_album_ids(self, user_id: int) -> set:
        """Get set of album IDs hearted by user."""
        result = self.db.execute(
            select(user_albums.c.album_id).where(user_albums.c.user_id == user_id)
        ).fetchall()
        return {row[0] for row in result}

    def get_hearted_track_ids(self, user_id: int) -> set:
        """Get set of track IDs hearted by user."""
        result = self.db.execute(
            select(user_tracks.c.track_id).where(user_tracks.c.user_id == user_id)
        ).fetchall()
        return {row[0] for row in result}
