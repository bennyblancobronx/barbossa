"""Library service for browsing master library."""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track


class LibraryService:
    """Service for browsing the master music library."""

    def __init__(self, db: Session):
        self.db = db

    def list_artists(
        self,
        letter: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List all artists, optionally filtered by starting letter."""
        query = self.db.query(Artist).order_by(Artist.sort_name)

        if letter:
            if letter == "#":
                # Non-alphabetic starting character
                query = query.filter(~Artist.sort_name.regexp_match("^[A-Za-z]"))
            else:
                query = query.filter(Artist.sort_name.ilike(f"{letter}%"))

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        pages = (total + limit - 1) // limit

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    def get_artist(self, artist_id: int) -> Optional[Artist]:
        """Get a single artist by ID."""
        return self.db.query(Artist).filter(Artist.id == artist_id).first()

    def get_artist_albums(self, artist_id: int) -> List[Album]:
        """Get all albums for an artist, ordered by year descending."""
        return (
            self.db.query(Album)
            .filter(Album.artist_id == artist_id)
            .order_by(Album.year.desc())
            .all()
        )

    def list_albums(
        self,
        artist_id: Optional[int] = None,
        letter: Optional[str] = None,
        page: int = 1,
        limit: int = 50
    ) -> Dict[str, Any]:
        """List albums with optional filters."""
        query = self.db.query(Album)

        if artist_id:
            query = query.filter(Album.artist_id == artist_id)

        if letter:
            if letter == "#":
                query = query.filter(~Album.title.regexp_match("^[A-Za-z]"))
            else:
                query = query.filter(Album.title.ilike(f"{letter}%"))

        query = query.order_by(Album.title)

        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        pages = (total + limit - 1) // limit

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages,
        }

    def get_album(self, album_id: int) -> Optional[Album]:
        """Get a single album by ID."""
        return self.db.query(Album).filter(Album.id == album_id).first()

    def get_album_tracks(self, album_id: int) -> List[Track]:
        """Get all tracks for an album, ordered by disc and track number."""
        return (
            self.db.query(Track)
            .filter(Track.album_id == album_id)
            .order_by(Track.disc_number, Track.track_number)
            .all()
        )

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a single track by ID."""
        return self.db.query(Track).filter(Track.id == track_id).first()

    def search(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 20
    ) -> Dict[str, List]:
        """Search library by query string."""
        results = {"artists": [], "albums": [], "tracks": []}
        pattern = f"%{query}%"

        if search_type in ("all", "artist"):
            results["artists"] = (
                self.db.query(Artist)
                .filter(Artist.name.ilike(pattern))
                .limit(limit)
                .all()
            )

        if search_type in ("all", "album"):
            results["albums"] = (
                self.db.query(Album)
                .filter(Album.title.ilike(pattern))
                .limit(limit)
                .all()
            )

        if search_type in ("all", "track"):
            results["tracks"] = (
                self.db.query(Track)
                .filter(Track.title.ilike(pattern))
                .limit(limit)
                .all()
            )

        return results

    def delete_album(self, album_id: int) -> bool:
        """Delete an album from the database (not from disk)."""
        album = self.get_album(album_id)
        if not album:
            return False

        self.db.delete(album)
        self.db.commit()
        return True
