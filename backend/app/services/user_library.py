"""User library service for managing hearted albums/tracks."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
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
        """Get user's hearted albums with artist info."""
        query = (
            self.db.query(Album)
            .options(joinedload(Album.artist))
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
        """Check if user has hearted a track.

        Returns True if track is either:
        1. Individually hearted (in user_tracks)
        2. From a hearted album (album in user_albums)
        """
        # Check if individually hearted
        individual = self.db.execute(
            select(user_tracks).where(
                user_tracks.c.user_id == user_id,
                user_tracks.c.track_id == track_id
            )
        ).first()
        if individual:
            return True

        # Check if track's album is hearted
        track = self.db.query(Track).filter(Track.id == track_id).first()
        if track:
            album_hearted = self.db.execute(
                select(user_albums).where(
                    user_albums.c.user_id == user_id,
                    user_albums.c.album_id == track.album_id
                )
            ).first()
            if album_hearted:
                return True

        return False

    def get_hearted_album_ids(self, user_id: int) -> set:
        """Get set of album IDs hearted by user."""
        result = self.db.execute(
            select(user_albums.c.album_id).where(user_albums.c.user_id == user_id)
        ).fetchall()
        return {row[0] for row in result}

    def get_hearted_track_ids(self, user_id: int) -> set:
        """Get set of track IDs hearted by user.

        Returns track IDs that are either:
        1. Individually hearted (in user_tracks)
        2. From a hearted album (album in user_albums)
        """
        from sqlalchemy import union

        # Individually hearted tracks
        individual = select(user_tracks.c.track_id).where(
            user_tracks.c.user_id == user_id
        )

        # Tracks from hearted albums
        from_albums = (
            select(Track.id)
            .join(user_albums, Track.album_id == user_albums.c.album_id)
            .where(user_albums.c.user_id == user_id)
        )

        # Combine both
        combined = union(individual, from_albums)
        result = self.db.execute(combined).fetchall()
        return {row[0] for row in result}

    def heart_artist(self, user_id: int, artist_id: int, username: str) -> int:
        """Heart all albums by an artist. Returns count of newly hearted albums."""
        from app.models.artist import Artist

        artist = self.db.query(Artist).filter(Artist.id == artist_id).first()
        if not artist:
            raise ValueError("Artist not found")

        albums = self.db.query(Album).filter(Album.artist_id == artist_id).all()
        count = 0
        for album in albums:
            try:
                if self.heart_album(user_id, album.id, username):
                    count += 1
            except ValueError:
                pass  # Album might not exist

        # Log activity for artist
        activity = ActivityService(self.db)
        activity.log(user_id, "heart", "artist", artist_id, {"album_count": count})

        return count

    def unheart_artist(self, user_id: int, artist_id: int, username: str) -> int:
        """Unheart all albums by an artist. Returns count of unhearted albums."""
        from app.models.artist import Artist

        artist = self.db.query(Artist).filter(Artist.id == artist_id).first()
        if not artist:
            raise ValueError("Artist not found")

        albums = self.db.query(Album).filter(Album.artist_id == artist_id).all()
        count = 0
        for album in albums:
            if self.unheart_album(user_id, album.id, username):
                count += 1

        # Log activity for artist
        activity = ActivityService(self.db)
        activity.log(user_id, "unheart", "artist", artist_id, {"album_count": count})

        return count

    def is_artist_hearted(self, user_id: int, artist_id: int) -> bool:
        """Check if user has hearted at least one album by the artist."""
        result = self.db.execute(
            select(user_albums.c.album_id)
            .join(Album, Album.id == user_albums.c.album_id)
            .where(
                user_albums.c.user_id == user_id,
                Album.artist_id == artist_id
            )
        ).first()
        return result is not None

    def get_hearted_artist_ids(self, user_id: int) -> set:
        """Get set of artist IDs where user has hearted at least one album."""
        result = self.db.execute(
            select(Album.artist_id)
            .distinct()
            .join(user_albums, Album.id == user_albums.c.album_id)
            .where(user_albums.c.user_id == user_id)
        ).fetchall()
        return {row[0] for row in result}

    def get_library_tracks(
        self,
        user_id: int,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get user's hearted tracks with album/artist info.

        Returns tracks that are either:
        1. Individually hearted (in user_tracks)
        2. From a hearted album (album in user_albums)
        """
        from sqlalchemy import or_, exists

        # Subquery: track is individually hearted
        individually_hearted = exists(
            select(user_tracks.c.track_id).where(
                user_tracks.c.track_id == Track.id,
                user_tracks.c.user_id == user_id
            )
        )

        # Subquery: track's album is hearted
        album_hearted = exists(
            select(user_albums.c.album_id).where(
                user_albums.c.album_id == Track.album_id,
                user_albums.c.user_id == user_id
            )
        )

        query = (
            self.db.query(Track)
            .options(joinedload(Track.album).joinedload(Album.artist))
            .filter(or_(individually_hearted, album_hearted))
            .order_by(Track.album_id, Track.disc_number, Track.track_number)
        )

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        pages = (total + limit - 1) // limit

        # Mark all as hearted
        for track in items:
            track.is_hearted = True

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }
