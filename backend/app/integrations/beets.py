"""Beets integration for auto-tagging.

Uses beets Python API when available, falls back to CLI.
"""
import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)


class BeetsError(Exception):
    """Beets operation failed."""
    pass


class BeetsClient:
    """Wrapper for beets - uses Python API when available, CLI fallback.

    Beets handles:
    - Metadata lookup (MusicBrainz)
    - File renaming (Plex-compatible)
    - Artwork fetching
    - Lyrics embedding
    """

    def __init__(self):
        self.config_path = Path("/config/beets.yaml")
        self._library_path = None
        self._use_api = self._check_beets_api()

    def _check_beets_api(self) -> bool:
        """Check if beets Python API is available."""
        try:
            import beets
            from beets import config as beets_config
            from beets.autotag import mb
            if self.config_path.exists():
                beets_config.read(str(self.config_path))
            else:
                return False
            return True
        except ImportError:
            logger.info("Beets Python API not available, using CLI fallback")
            return False

    @property
    def library_path(self) -> Path:
        """Get library path from settings."""
        if self._library_path is None:
            self._library_path = Path(settings.music_library)
        return self._library_path

    async def identify(self, path: Path) -> Dict[str, Any]:
        """Identify album metadata.

        Args:
            path: Path to album folder

        Returns:
            Dict with artist, album, year, tracks, confidence
        """
        if self._use_api:
            return await self._identify_api(path)
        return await self._identify_cli(path)

    async def _identify_api(self, path: Path) -> Dict[str, Any]:
        """Identify using beets Python API.

        Returns comprehensive metadata including MusicBrainz IDs for:
        - Album (release ID, release group ID)
        - Artist (artist ID)
        - Tracks (recording ID, track ID, ISRC)
        - Label and catalog number
        """
        try:
            from beets import autotag
            from beets.autotag import mb
            from beets.util import displayable_path
            import mediafile

            # Get audio files
            audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
            audio_files = sorted([
                f for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in audio_extensions
            ])

            if not audio_files:
                return self._parse_folder_name(path.name)

            # Read metadata from first track
            try:
                mf = mediafile.MediaFile(str(audio_files[0]))
                local_artist = mf.artist or mf.albumartist or ""
                local_album = mf.album or ""
                local_year = mf.year
            except Exception as e:
                logger.warning(f"Failed to read metadata: {e}")
                local_artist = ""
                local_album = ""
                local_year = None

            # Try MusicBrainz lookup
            if local_artist and local_album:
                try:
                    # Search MusicBrainz
                    candidates = mb.match_album(local_artist, local_album)
                    candidates_list = list(candidates)

                    if candidates_list:
                        best = candidates_list[0]
                        info = best.info
                        # Calculate confidence from distance (lower = better match)
                        confidence = max(0, 1.0 - (best.distance / 0.5))

                        # Extract track-level MusicBrainz data
                        track_data = []
                        if hasattr(best, 'mapping') and best.mapping:
                            for item, track_info in best.mapping.items():
                                track_data.append({
                                    "title": track_info.title if hasattr(track_info, 'title') else None,
                                    "musicbrainz_track_id": getattr(track_info, 'track_id', None),
                                    "musicbrainz_recording_id": getattr(track_info, 'recording_id', None),
                                    "isrc": getattr(track_info, 'isrc', None),
                                    "track_number": getattr(track_info, 'index', None),
                                    "disc_number": getattr(track_info, 'medium', 1),
                                    "length": getattr(track_info, 'length', None),
                                })

                        return {
                            # Core identification
                            "artist": info.artist or local_artist,
                            "album": info.album or local_album,
                            "year": info.year or local_year,
                            "confidence": confidence,
                            "tracks": len(audio_files),

                            # MusicBrainz IDs (album/release level)
                            "musicbrainz_album_id": getattr(info, 'album_id', None),
                            "musicbrainz_artist_id": getattr(info, 'artist_id', None),
                            "musicbrainz_release_group_id": getattr(info, 'releasegroup_id', None),

                            # Additional metadata from MusicBrainz
                            "label": getattr(info, 'label', None),
                            "catalog_number": getattr(info, 'catalognum', None),
                            "country": getattr(info, 'country', None),
                            "release_type": getattr(info, 'albumtype', None),
                            "media": getattr(info, 'media', None),
                            "disctotal": getattr(info, 'mediums', None),

                            # Track-level MusicBrainz data
                            "track_data": track_data if track_data else None,

                            # Legacy field for backwards compatibility
                            "musicbrainz_id": getattr(info, 'album_id', None),
                        }
                except Exception as e:
                    logger.warning(f"MusicBrainz lookup failed: {e}")

            # Return local metadata with partial confidence
            if local_artist or local_album:
                return {
                    "artist": local_artist or None,
                    "album": local_album or path.name,
                    "year": local_year,
                    "confidence": 0.6 if local_artist and local_album else 0.4,
                    "tracks": len(audio_files),
                    "musicbrainz_album_id": None,
                    "musicbrainz_artist_id": None,
                    "label": None,
                    "catalog_number": None,
                    "track_data": None,
                }

            # Fall back to folder name parsing
            folder_info = self._parse_folder_name(path.name)
            folder_info["tracks"] = len(audio_files)
            folder_info["musicbrainz_album_id"] = None
            folder_info["musicbrainz_artist_id"] = None
            folder_info["label"] = None
            folder_info["catalog_number"] = None
            folder_info["track_data"] = None
            return folder_info

        except Exception as e:
            logger.error(f"Beets API identify failed: {e}")
            return await self._identify_cli(path)

    async def _identify_cli(self, path: Path) -> Dict[str, Any]:
        """Identify using beets CLI (fallback).

        Note: CLI fallback cannot extract MusicBrainz IDs as reliably as
        the API. Fields are set to None for consistency.
        """
        cmd = [
            "beet", "import",
            "--pretend",
            str(path)
        ]

        if self.config_path.exists():
            cmd.insert(1, "-c")
            cmd.insert(2, str(self.config_path))

        result = await self._run_command(cmd, allow_failure=True)
        identification = self._parse_identification(result)

        # If beets didn't identify, try parsing folder name
        if not identification.get("artist") or identification.get("confidence", 0) == 0:
            folder_info = self._parse_folder_name(path.name)
            if folder_info.get("artist"):
                identification["artist"] = identification.get("artist") or folder_info.get("artist")
                identification["album"] = identification.get("album") or folder_info.get("album")
                identification["year"] = identification.get("year") or folder_info.get("year")
                if identification["confidence"] == 0:
                    identification["confidence"] = 0.5

        # Ensure consistent fields for CLI fallback
        identification.setdefault("musicbrainz_album_id", None)
        identification.setdefault("musicbrainz_artist_id", None)
        identification.setdefault("musicbrainz_release_group_id", None)
        identification.setdefault("label", None)
        identification.setdefault("catalog_number", None)
        identification.setdefault("country", None)
        identification.setdefault("release_type", None)
        identification.setdefault("track_data", None)

        return identification

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
        # Build command with -c BEFORE subcommand (beet -c config import ...)
        cmd = ["beet"]

        if self.config_path.exists():
            cmd.extend(["-c", str(self.config_path)])

        cmd.append("import")

        if quiet:
            cmd.append("--quiet")

        if move:
            cmd.append("--move")
        else:
            cmd.append("--copy")

        cmd.append(str(path))

        # Capture track filenames BEFORE beets moves them (--move empties source dir)
        audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac"}
        source_track_names = [
            f.name for f in path.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ] if path.exists() else []

        await self._run_command(cmd, allow_failure=True)

        try:
            # Parse artist/album from streamrip folder format if not provided
            if not artist or not album:
                parsed = self._parse_folder_name(path.name)
                artist = artist or parsed.get("artist") or self._extract_artist_from_path(path)
                album = album or parsed.get("album") or path.name

            return await self._find_imported_path(artist, album)
        except BeetsError:
            # Source path is empty after --move, so use pre-captured filenames
            fallback = self._find_by_track_name_in_library(source_track_names)
            if fallback:
                return fallback
            raise

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
            if file.is_file():
                dest = target_dir / file.name
                if move:
                    shutil.move(str(file), str(dest))
                else:
                    shutil.copy2(str(file), str(dest))

        # Tag files with provided metadata
        if self._use_api:
            await self._tag_files_api(target_dir, artist, album, year)
        else:
            # Run beet import on the new location to fix tags
            # Note: -c must come BEFORE subcommand
            cmd = ["beet"]
            if self.config_path.exists():
                cmd.extend(["-c", str(self.config_path)])
            cmd.extend(["import", "--quiet", str(target_dir)])
            await self._run_command(cmd, allow_failure=True)

        # Clean up empty source directory
        if move and path.exists() and not any(path.iterdir()):
            path.rmdir()

        return target_dir

    async def _tag_files_api(self, path: Path, artist: str, album: str, year: Optional[int]) -> None:
        """Tag files using mediafile library."""
        try:
            import mediafile

            audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff"}
            audio_files = sorted([
                f for f in path.iterdir()
                if f.is_file() and f.suffix.lower() in audio_extensions
            ])

            for i, audio_file in enumerate(audio_files, 1):
                try:
                    mf = mediafile.MediaFile(str(audio_file))
                    mf.artist = artist
                    mf.albumartist = artist
                    mf.album = album
                    if year:
                        mf.year = year
                    if not mf.track:
                        mf.track = i
                    mf.save()
                except Exception as e:
                    logger.warning(f"Failed to tag {audio_file.name}: {e}")

        except ImportError:
            logger.warning("mediafile not available for tagging")

    async def update_tags(self, path: Path) -> None:
        """Update tags on existing files."""
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
        # Try beets fetchart plugin
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

        # Try Cover Art Archive directly if beets failed
        artwork_path = await self._fetch_coverart_archive(path)
        if artwork_path:
            return artwork_path

        return None

    async def _fetch_coverart_archive(self, path: Path) -> Optional[Path]:
        """Fetch artwork from Cover Art Archive."""
        try:
            import aiohttp
            import mediafile

            # Get MusicBrainz release ID from files
            audio_extensions = {".flac", ".mp3", ".m4a"}
            audio_files = [f for f in path.iterdir() if f.suffix.lower() in audio_extensions]

            if not audio_files:
                return None

            mf = mediafile.MediaFile(str(audio_files[0]))
            mb_albumid = mf.mb_albumid

            if not mb_albumid:
                return None

            # Fetch from Cover Art Archive
            url = f"https://coverartarchive.org/release/{mb_albumid}/front-500"

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        cover_path = path / "cover.jpg"
                        with open(cover_path, "wb") as f:
                            f.write(await response.read())
                        return cover_path

        except Exception as e:
            logger.debug(f"Cover Art Archive fetch failed: {e}")

        return None

    async def _run_command(self, cmd: List[str], allow_failure: bool = False) -> str:
        """Run beets command."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0 and not allow_failure:
            raise BeetsError(stderr.decode() or stdout.decode())

        return stdout.decode() + stderr.decode()

    def _parse_identification(self, output: str) -> Dict[str, Any]:
        """Parse beets identification output."""
        confidence = 0.0
        artist = None
        album = None
        year = None
        tracks = []

        # Error/warning indicators to skip
        skip_indicators = [
            "No files imported",
            "Error",
            "Warning",
            "Traceback",
            "Exception",
            "/music/",  # Skip lines containing paths
            "/config/",
        ]

        for line in output.split("\n"):
            line = line.strip()

            # Skip empty lines and error messages
            if not line or any(skip in line for skip in skip_indicators):
                continue

            # Match confidence: "Similarity: 95.5%" or "(Similarity: 95.5%)"
            if "Similarity:" in line:
                match = re.search(r"(\d+\.?\d*)%", line)
                if match:
                    confidence = float(match.group(1)) / 100

            # Match album info: "Artist - Album (Year)"
            # Only match if it doesn't look like a path or error
            match = re.match(r"^(.+?)\s+-\s+(.+?)(?:\s+\((\d{4})\))?$", line)
            if match and not artist:
                potential_artist = match.group(1).strip()
                # Additional validation - skip if looks like error/path
                if not potential_artist.startswith(("/", "No ", "Error")):
                    artist = potential_artist
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

    def _normalize_for_match(self, text: str) -> str:
        """Normalize text for fuzzy path matching.

        Beets replaces special characters with underscores and collapses
        whitespace. This normalizes both sides so 'i am  i was' matches
        'i am _ i was'.
        """
        import re
        text = text.lower()
        # Replace common beets substitution characters with space
        text = text.replace("_", " ")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def _find_imported_path(self, artist: str, album: str) -> Path:
        """Find imported album path in library."""
        norm_artist = self._normalize_for_match(artist)
        norm_album = self._normalize_for_match(album)

        # Beets organizes as: /library/Artist/Album (Year)/
        for artist_dir in self.library_path.iterdir():
            if not artist_dir.is_dir():
                continue

            # Case-insensitive artist match (normalized for beets char replacements)
            dir_norm = self._normalize_for_match(artist_dir.name)
            if dir_norm == norm_artist or norm_artist in dir_norm:

                for album_dir in artist_dir.iterdir():
                    if album_dir.is_dir() and norm_album in self._normalize_for_match(album_dir.name):
                        return album_dir

        # Fallback: Check Compilations/ folder (beets comp: path rule)
        comp_dir = self.library_path / "Compilations"
        if comp_dir.exists():
            for album_dir in comp_dir.iterdir():
                if album_dir.is_dir() and norm_album in self._normalize_for_match(album_dir.name):
                    return album_dir

        # If not found, return expected path
        expected = self.library_path / artist / album
        if expected.exists():
            return expected

        raise BeetsError(f"Could not find imported album: {artist} - {album}")

    def _find_by_track_filename(self, source_path: Path) -> Optional[Path]:
        """Find imported album by matching a track filename in library."""
        if not source_path.exists():
            return None

        audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac"}
        source_files = [
            f for f in source_path.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ]
        if not source_files:
            return None

        target_name = source_files[0].name

        for artist_dir in self.library_path.iterdir():
            if not artist_dir.is_dir():
                continue
            for album_dir in artist_dir.iterdir():
                if not album_dir.is_dir():
                    continue
                candidate = album_dir / target_name
                if candidate.exists():
                    return album_dir

        return None

    def _find_by_track_name_in_library(self, track_names: list[str]) -> Optional[Path]:
        """Find imported album by matching pre-captured track filenames in library.

        Unlike _find_by_track_filename, this works after beets --move has
        emptied the source directory, because filenames were captured beforehand.
        """
        if not track_names:
            return None

        target_name = track_names[0]

        for artist_dir in self.library_path.iterdir():
            if not artist_dir.is_dir():
                continue
            for album_dir in artist_dir.iterdir():
                if not album_dir.is_dir():
                    continue
                candidate = album_dir / target_name
                if candidate.exists():
                    return album_dir

        return None

    def _parse_folder_name(self, name: str) -> Dict[str, Any]:
        """Parse folder name in streamrip format.

        Format: "Artist - Album (Year) [Format] [Quality]"
        Example: "Joni Mitchell - Blue (1971) [FLAC] [24B-192kHz]"
        """
        result = {
            "artist": None,
            "album": None,
            "year": None,
            "confidence": 0.5,
            "tracks": 0,
            # MusicBrainz fields (None for folder name parsing)
            "musicbrainz_album_id": None,
            "musicbrainz_artist_id": None,
            "musicbrainz_release_group_id": None,
            "label": None,
            "catalog_number": None,
            "country": None,
            "release_type": None,
            "track_data": None,
        }

        # Remove format/quality brackets from end
        clean_name = re.sub(r'\s*\[.*?\]\s*$', '', name)
        clean_name = re.sub(r'\s*\[.*?\]\s*$', '', clean_name)

        # Extract year if present
        year_match = re.search(r'\((\d{4})\)\s*$', clean_name)
        if year_match:
            result["year"] = int(year_match.group(1))
            clean_name = clean_name[:year_match.start()].strip()

        # Split artist - album
        if " - " in clean_name:
            parts = clean_name.split(" - ", 1)
            result["artist"] = parts[0].strip()
            result["album"] = parts[1].strip()
        else:
            result["album"] = clean_name.strip()

        return result

    def _extract_artist_from_path(self, path: Path) -> str:
        """Extract artist name from download path structure."""
        name = path.name
        if " - " in name:
            return name.split(" - ")[0]
        return path.parent.name if path.parent.name != "downloads" else name
