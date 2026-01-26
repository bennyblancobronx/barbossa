"""Library service for browsing master library."""
import shutil
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.user import User
from app.models.user_library import user_albums
from app.services.symlink import SymlinkService

logger = logging.getLogger(__name__)


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

    def delete_album(
        self, album_id: int, delete_files: bool = True
    ) -> tuple[bool, str | None]:
        """Delete an album from database and optionally from disk.

        Files are deleted FIRST to prevent orphaned files if DB deletion succeeds
        but file deletion fails.

        Args:
            album_id: ID of album to delete
            delete_files: If True, also delete files from disk (default: True)

        Returns:
            tuple[bool, str | None]: (success, error_message)
            - (True, None) if fully deleted
            - (False, "error reason") if failed
        """
        album = self.get_album(album_id)
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
                    # SMB mounts can leave .smbdelete* files that block rmtree
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

        # Step 2: Remove user library symlinks
        if album_path:
            symlink = SymlinkService()
            users = (
                self.db.query(User.username)
                .join(user_albums, User.id == user_albums.c.user_id)
                .filter(user_albums.c.album_id == album_id)
                .all()
            )
            for (username,) in users:
                symlink.remove_album_links(username, album_path)

        # Step 3: Delete database records only after files are gone
        try:
            # Delete tracks first (foreign key constraint)
            self.db.query(Track).filter(Track.album_id == album_id).delete()

            # Delete album from database
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
