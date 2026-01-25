"""Beets integration for auto-tagging."""
import asyncio
import re
import shutil
from pathlib import Path
from typing import Optional
from app.config import settings


class BeetsError(Exception):
    """Beets operation failed."""
    pass


class BeetsClient:
    """Wrapper for beets CLI.

    Beets handles:
    - Metadata lookup (MusicBrainz)
    - File renaming (Plex-compatible)
    - Artwork fetching
    - Lyrics embedding
    """

    def __init__(self):
        self.config_path = Path("/config/beets.yaml")
        self._library_path = None

    @property
    def library_path(self) -> Path:
        """Get library path from settings."""
        if self._library_path is None:
            self._library_path = Path(settings.music_library)
        return self._library_path

    async def identify(self, path: Path) -> dict:
        """Identify album metadata without importing.

        Args:
            path: Path to album folder

        Returns:
            Dict with artist, album, year, tracks, confidence
        """
        cmd = [
            "beet", "import",
            "--pretend",  # Don't actually import
            str(path)
        ]

        if self.config_path.exists():
            cmd.insert(1, "-c")
            cmd.insert(2, str(self.config_path))

        result = await self._run_command(cmd, allow_failure=True)
        return self._parse_identification(result)

    async def import_album(
        self,
        path: Path,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        move: bool = True,
        quiet: bool = True
    ) -> Path:
        """Import and tag album.

        Args:
            path: Path to album folder
            artist: Override artist name
            album: Override album name
            move: Move files to library (vs copy)
            quiet: Don't prompt for confirmation

        Returns:
            Path to imported album in library
        """
        cmd = ["beet", "import"]

        if self.config_path.exists():
            cmd.extend(["-c", str(self.config_path)])

        if quiet:
            cmd.append("--quiet")

        if move:
            cmd.append("--move")
        else:
            cmd.append("--copy")

        # Note: beet import doesn't support --set the same way
        # We'll use the path structure or update after import

        cmd.append(str(path))

        await self._run_command(cmd, allow_failure=True)

        # Find imported album path
        return await self._find_imported_path(
            artist or self._extract_artist_from_path(path),
            album or path.name
        )

    async def import_with_metadata(
        self,
        path: Path,
        artist: str,
        album: str,
        year: Optional[int] = None,
        move: bool = True
    ) -> Path:
        """Import with explicit metadata (for unidentified albums).

        Args:
            path: Path to album folder
            artist: Artist name
            album: Album name
            year: Release year
            move: Move files to library

        Returns:
            Path to imported album in library
        """
        # Create target directory
        year_str = f" ({year})" if year else ""
        target_dir = self.library_path / artist / f"{album}{year_str}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Move or copy files
        for file in path.iterdir():
            dest = target_dir / file.name
            if move:
                shutil.move(str(file), str(dest))
            else:
                shutil.copy2(str(file), str(dest))

        # Run beet import on the new location to fix tags
        cmd = ["beet", "import", "--quiet"]
        if self.config_path.exists():
            cmd.extend(["-c", str(self.config_path)])
        cmd.append(str(target_dir))

        await self._run_command(cmd, allow_failure=True)

        return target_dir

    async def update_tags(self, path: Path) -> None:
        """Update tags on existing files.

        Args:
            path: Path to album or file
        """
        cmd = ["beet", "modify", "-y", f"path:{path}"]
        if self.config_path.exists():
            cmd.insert(1, "-c")
            cmd.insert(2, str(self.config_path))

        await self._run_command(cmd, allow_failure=True)

    async def fetch_artwork(self, path: Path) -> Optional[Path]:
        """Fetch artwork for album.

        Args:
            path: Path to album folder

        Returns:
            Path to artwork file or None
        """
        cmd = ["beet", "fetchart", "-y", f"path:{path}"]
        if self.config_path.exists():
            cmd.insert(1, "-c")
            cmd.insert(2, str(self.config_path))

        await self._run_command(cmd, allow_failure=True)

        # Check if artwork was saved
        for name in ["cover.jpg", "cover.png", "folder.jpg"]:
            artwork = path / name
            if artwork.exists():
                return artwork

        return None

    async def _run_command(self, cmd: list[str], allow_failure: bool = False) -> str:
        """Run beets command."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0 and not allow_failure:
            raise BeetsError(stderr.decode() or stdout.decode())

        # Return combined output for parsing
        return stdout.decode() + stderr.decode()

    def _parse_identification(self, output: str) -> dict:
        """Parse beets identification output."""
        confidence = 0.0
        artist = None
        album = None
        year = None
        tracks = []

        for line in output.split("\n"):
            line = line.strip()

            # Match confidence: "Similarity: 95.5%" or "(Similarity: 95.5%)"
            if "Similarity:" in line:
                match = re.search(r"(\d+\.?\d*)%", line)
                if match:
                    confidence = float(match.group(1)) / 100

            # Match album info: "Artist - Album (Year)"
            match = re.match(r"^(.+?)\s+-\s+(.+?)(?:\s+\((\d{4})\))?$", line)
            if match and not artist:
                artist = match.group(1).strip()
                album = match.group(2).strip()
                if match.group(3):
                    year = int(match.group(3))

            # Match explicit labels
            if line.startswith("Album:"):
                album = line.split(":", 1)[1].strip()
            if line.startswith("Artist:"):
                artist = line.split(":", 1)[1].strip()
            if line.startswith("Year:"):
                try:
                    year = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        return {
            "artist": artist,
            "album": album,
            "year": year,
            "confidence": confidence,
            "tracks": tracks
        }

    async def _find_imported_path(self, artist: str, album: str) -> Path:
        """Find imported album path in library."""
        # Beets organizes as: /library/Artist/Album (Year)/
        # Try exact match first
        for artist_dir in self.library_path.iterdir():
            if not artist_dir.is_dir():
                continue

            # Case-insensitive artist match
            if artist_dir.name.lower() == artist.lower() or \
               artist.lower() in artist_dir.name.lower():

                for album_dir in artist_dir.iterdir():
                    if album_dir.is_dir() and album.lower() in album_dir.name.lower():
                        return album_dir

        # If not found, return expected path (might exist)
        expected = self.library_path / artist / album
        if expected.exists():
            return expected

        raise BeetsError(f"Could not find imported album: {artist} - {album}")

    def _extract_artist_from_path(self, path: Path) -> str:
        """Extract artist name from download path structure."""
        # Typically: /downloads/Artist/Album or /downloads/Artist - Album
        name = path.name
        if " - " in name:
            return name.split(" - ")[0]
        return path.parent.name if path.parent.name != "downloads" else name
