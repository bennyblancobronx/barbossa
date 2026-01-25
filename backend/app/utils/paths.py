"""Path manipulation utilities."""
from pathlib import Path
from typing import Optional
from app.config import settings


def resolve_path(path: str) -> Path:
    """Resolve a path, expanding user and making absolute."""
    return Path(path).expanduser().resolve()


def relative_to_library(path: Path) -> Optional[Path]:
    """Get path relative to music library, or None if not under library."""
    library = Path(settings.music_library)
    try:
        return path.relative_to(library)
    except ValueError:
        return None


def get_user_library_path(username: str) -> Path:
    """Get the user's library root path."""
    return Path(settings.music_users) / username


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path
