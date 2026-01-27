"""Library service for browsing master library."""
import shutil
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from app.models.artist import Artist
from app.models.album import Album
from app.models.track import Track
from app.models.user import User
from app.models.user_library import user_albums
from app.services.symlink import SymlinkService

logger = logging.getLogger(__name__)


def smb_safe_rmtree(path: Path, retries: int = 3, delay: float = 0.5) -> None:
    """Delete a directory tree with SMB mount compatibility.

    SMB mounts create .smbdelete* files during deletion that can be temporarily
    locked. This function retries deletion with delays to handle these locks.

    Args:
        path: Directory to delete
        retries: Number of retry attempts (default 3)
        delay: Seconds to wait between retries (default 0.5)

    Raises:
        OSError: If deletion fails after all retries
    """
    last_error = None

    for attempt in range(retries):
        try:
            # First pass: try to remove .smbdelete* files with individual retries
            for smb_file in list(path.rglob(".smbdelete*")):
                for _ in range(3):
                    try:
                        smb_file.unlink()
                        break
                    except OSError:
                        time.sleep(0.1)

            # Now try rmtree with onerror handler
            def onerror(func, filepath, exc_info):
                """Handle errors during rmtree - retry busy files."""
                filepath_str = str(filepath)  # Convert Path to string
                error_str = str(exc_info[1]) if exc_info[1] else ""
                if "Device or resource busy" in error_str or ".smbdelete" in filepath_str:
                    time.sleep(0.2)
                    try:
                        func(filepath)
                    except Exception:
                        pass  # Will be caught by outer retry
                else:
                    raise exc_info[1]

            shutil.rmtree(path, onerror=onerror)
            return  # Success

        except OSError as e:
            last_error = e
            if attempt < retries - 1:
                logger.warning(f"SMB deletion attempt {attempt + 1} failed, retrying in {delay}s: {e}")
                time.sleep(delay)
                delay *= 2  # Exponential backoff

    # All retries failed
    raise last_error


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
        """List albums with optional filters and artist info."""
        query = self.db.query(Album).options(joinedload(Album.artist))

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
        """Get all tracks for an album, ordered by disc and track number.

        Eager loads album and artist for player context.
        """
        return (
            self.db.query(Track)
            .options(joinedload(Track.album).joinedload(Album.artist))
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
                .options(joinedload(Album.artist))
                .filter(Album.title.ilike(pattern))
                .limit(limit)
                .all()
            )

        if search_type in ("all", "track"):
            results["tracks"] = (
                self.db.query(Track)
                .options(joinedload(Track.album).joinedload(Album.artist))
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

        logger.info(f"Starting deletion of album {album_id}: {artist_name} - {album_title}")
        logger.info(f"Album path from database: {album_path}")

        # Step 1: Delete files FIRST (if requested)
        if delete_files and album_path:
            path = Path(album_path)
            logger.info(f"Checking if path exists: {path} -> exists={path.exists()}, is_dir={path.is_dir() if path.exists() else 'N/A'}")

            files_deleted = False
            if path.exists() and path.is_dir():
                try:
                    # Check if directory only contains .smbdelete files (already pending deletion)
                    real_files = [f for f in path.iterdir() if not f.name.startswith('.smbdelete')]
                    if not real_files:
                        logger.info(f"Album directory only contains SMB pending-delete files, skipping file deletion: {path}")
                        files_deleted = True
                    else:
                        # Use SMB-safe deletion with retries
                        smb_safe_rmtree(path)
                        logger.info(f"Deleted album files: {path}")
                    files_deleted = True

                    # Clean up empty artist directory
                    artist_dir = path.parent
                    if artist_dir.exists():
                        # Check if empty (ignore .smbdelete* and .DS_Store)
                        remaining = [f for f in artist_dir.iterdir()
                                     if not f.name.startswith('.smbdelete') and f.name != '.DS_Store']
                        if not remaining:
                            try:
                                smb_safe_rmtree(artist_dir)
                                logger.info(f"Removed empty artist directory: {artist_dir}")
                            except Exception as e:
                                logger.warning(f"Could not remove artist directory: {e}")

                except PermissionError as e:
                    logger.error(f"Permission denied deleting {path}: {e}")
                    return False, f"Permission denied: cannot delete files at {path}"
                except OSError as e:
                    error_str = str(e).lower()
                    # SMB lock issues - log warning but continue with database deletion
                    # "busy" = file locked, "not empty" = .smbdelete files remain
                    if "busy" in error_str or "smbdelete" in error_str or "not empty" in error_str:
                        logger.warning(f"SMB files may be locked or pending deletion, proceeding with database deletion: {e}")
                        files_deleted = True  # Files are marked for deletion by SMB
                    else:
                        logger.error(f"OS error deleting {path}: {e}")
                        return False, f"Failed to delete files: {e}"
                except Exception as e:
                    logger.error(f"Failed to delete album files {path}: {e}")
                    return False, f"Failed to delete files: {e}"
            else:
                logger.warning(f"Album path does not exist or is not a directory: {path}")
                files_deleted = True  # Nothing to delete on disk

        # Step 2: Remove user library symlinks
        if album_path:
            symlink = SymlinkService()
            users = (
                self.db.query(User.username)
                .join(user_albums, User.id == user_albums.c.user_id)
                .filter(user_albums.c.album_id == album_id)
                .all()
            )
            logger.info(f"Removing symlinks for {len(users)} user(s)")
            for (username,) in users:
                try:
                    symlink.remove_album_links(username, album_path)
                    logger.info(f"Removed symlinks for user: {username}")
                except Exception as e:
                    logger.warning(f"Failed to remove symlinks for user {username}: {e}")

        # Step 3: Delete database records only after files are gone
        try:
            # Delete from user_albums first (foreign key constraint)
            deleted_user_albums = self.db.execute(
                user_albums.delete().where(user_albums.c.album_id == album_id)
            )
            logger.info(f"Removed {deleted_user_albums.rowcount} user_albums entries")

            # Delete tracks (foreign key constraint)
            deleted_tracks = self.db.query(Track).filter(Track.album_id == album_id).delete()
            logger.info(f"Deleted {deleted_tracks} tracks from database")

            # Delete album from database
            self.db.delete(album)
            self.db.commit()

            logger.info(f"Successfully deleted album from database: {artist_name} - {album_title}")
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

    def delete_artist(
        self, artist_id: int, delete_files: bool = True
    ) -> tuple[bool, str | None]:
        """Delete an artist and all their albums from database and optionally disk.

        Args:
            artist_id: ID of artist to delete
            delete_files: If True, also delete files from disk (default: True)

        Returns:
            tuple[bool, str | None]: (success, error_message)
        """
        artist = self.get_artist(artist_id)
        if not artist:
            return False, "Artist not found"

        artist_name = artist.name
        artist_path = artist.path

        logger.info(f"Starting deletion of artist {artist_id}: {artist_name}")
        logger.info(f"Artist path from database: {artist_path}")

        # Get all albums for this artist
        albums = self.get_artist_albums(artist_id)
        logger.info(f"Found {len(albums)} albums to delete")

        # Delete each album (this handles files, symlinks, and DB records)
        failed_albums = []
        for album in albums:
            success, error = self.delete_album(album.id, delete_files)
            if not success:
                logger.error(f"Failed to delete album {album.id} ({album.title}) while deleting artist: {error}")
                failed_albums.append((album.id, album.title, error))
                # Continue deleting other albums even if one fails

        if failed_albums:
            logger.warning(f"Failed to delete {len(failed_albums)} album(s)")

        # Delete artist directory if it exists and is empty
        if delete_files and artist_path:
            path = Path(artist_path)
            logger.info(f"Checking artist path: {path} -> exists={path.exists()}")

            if path.exists() and path.is_dir():
                try:
                    # Check if empty (ignore .smbdelete* and .DS_Store)
                    remaining = [f for f in path.iterdir()
                                 if not f.name.startswith('.smbdelete') and f.name != '.DS_Store']
                    if not remaining:
                        smb_safe_rmtree(path)
                        logger.info(f"Deleted artist directory: {path}")
                    else:
                        logger.warning(f"Artist directory not empty, {len(remaining)} items remain: {[str(p) for p in remaining[:5]]}")
                except Exception as e:
                    logger.warning(f"Could not delete artist directory {path}: {e}")

        # Delete artist from database
        try:
            # Delete from user_artists first (foreign key constraint)
            from app.models.user_artists import user_artists
            deleted_user_artists = self.db.execute(
                user_artists.delete().where(user_artists.c.artist_id == artist_id)
            )
            logger.info(f"Removed {deleted_user_artists.rowcount} user_artists entries")

            self.db.delete(artist)
            self.db.commit()
            logger.info(f"Successfully deleted artist from database: {artist_name}")
            return True, None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Database error deleting artist {artist_id}: {e}")
            return False, f"Database error: {e}"
