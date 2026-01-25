"""Symlink service for managing user library file links."""
import os
import shutil
from pathlib import Path
from app.config import settings


class SymlinkService:
    """Service for creating/removing symlinks in user libraries."""

    def __init__(self):
        self.library_path = Path(settings.music_library)
        self.users_path = Path(settings.music_users)

    def create_album_links(self, username: str, album_path: str) -> None:
        """Create symlinks (or hardlinks) for album in user's library."""
        source = Path(album_path)
        if not source.exists():
            return

        try:
            relative = source.relative_to(self.library_path)
        except ValueError:
            # Path is not under library, use absolute
            relative = Path(source.name)

        dest = self.users_path / username / relative

        # Create parent directories
        dest.mkdir(parents=True, exist_ok=True)

        # Link each file in the album
        for file in source.iterdir():
            if file.is_file():
                link_path = dest / file.name
                if link_path.exists():
                    continue
                self._create_link(file, link_path)

    def remove_album_links(self, username: str, album_path: str) -> None:
        """Remove album links from user's library."""
        source = Path(album_path)

        try:
            relative = source.relative_to(self.library_path)
        except ValueError:
            relative = Path(source.name)

        dest = self.users_path / username / relative

        if dest.exists():
            shutil.rmtree(dest)
            self._cleanup_empty_parents(dest.parent, username)

    def create_track_link(self, username: str, track_path: str) -> None:
        """Create a symlink for a single track."""
        source = Path(track_path)
        if not source.exists():
            return

        try:
            relative = source.relative_to(self.library_path)
        except ValueError:
            relative = source.parent.name / source.name

        dest = self.users_path / username / relative

        # Create parent directories
        dest.parent.mkdir(parents=True, exist_ok=True)

        if not dest.exists():
            self._create_link(source, dest)

    def remove_track_link(self, username: str, track_path: str) -> None:
        """Remove a single track link."""
        source = Path(track_path)

        try:
            relative = source.relative_to(self.library_path)
        except ValueError:
            relative = source.parent.name / source.name

        dest = self.users_path / username / relative

        if dest.exists() or dest.is_symlink():
            dest.unlink()
            self._cleanup_empty_parents(dest.parent, username)

    def _create_link(self, source: Path, dest: Path) -> None:
        """Create hardlink if possible, fallback to symlink."""
        try:
            os.link(source, dest)  # Hardlink
        except OSError:
            os.symlink(source, dest)  # Symlink fallback

    def _cleanup_empty_parents(self, path: Path, username: str) -> None:
        """Remove empty parent directories up to user root."""
        user_root = self.users_path / username

        while path != user_root and path.exists():
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    path = path.parent
                else:
                    break
            except OSError:
                break
