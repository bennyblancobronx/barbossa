"""ExifTool integration for quality metadata extraction."""
import asyncio
import json
from pathlib import Path
from typing import Optional


class ExifToolClient:
    """Wrapper for ExifTool CLI.

    Extracts audio quality metadata including:
    - Sample rate (44100, 96000, 192000)
    - Bit depth (16, 24)
    - Bitrate (for lossy)
    - Format (FLAC, MP3, etc.)
    - Extended metadata (ISRC, composer, lyrics, MusicBrainz IDs)
    """

    AUDIO_TAGS = [
        # Core identification
        "Title",
        "Artist",
        "Album",
        "AlbumArtist",
        "TrackNumber",
        "DiscNumber",
        "Year",
        "Date",
        "OriginalDate",

        # Quality metadata
        "SampleRate",
        "BitsPerSample",
        "AudioBitrate",
        "NumChannels",
        "AudioChannels",
        "Duration",
        "FileSize",
        "FileType",

        # Extended metadata
        "Genre",
        "Composer",
        "Label",
        "Publisher",
        "CatalogNumber",
        "ISRC",
        "Compilation",
        "ContentRating",
        "Explicit",

        # Lyrics (multiple possible tags)
        "Lyrics",
        "UnsyncedLyrics",
        "USLT",

        # MusicBrainz IDs
        "MusicBrainz Album Id",
        "MusicBrainz Track Id",
        "MusicBrainz Artist Id",
        "MusicBrainz Release Group Id",
        "MusicBrainz Album Artist Id",
        "MUSICBRAINZ_ALBUMID",
        "MUSICBRAINZ_TRACKID",
        "MUSICBRAINZ_ARTISTID",
    ]

    AUDIO_EXTENSIONS = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aac", ".opus", ".wma"}
    LOSSY_FORMATS = {"mp3", "aac", "ogg", "opus", "m4a", "wma"}

    async def get_metadata(self, path: Path) -> dict:
        """Extract audio metadata from file.

        Args:
            path: Path to audio file

        Returns:
            Dict with sample_rate, bit_depth, bitrate, channels, duration, etc.
        """
        cmd = [
            "exiftool",
            "-json",
            "-n",  # Numeric values
            *[f"-{tag}" for tag in self.AUDIO_TAGS],
            str(path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        try:
            data = json.loads(stdout.decode())[0]
        except (json.JSONDecodeError, IndexError):
            # Fallback to basic info
            return self._basic_metadata(path)

        return self._normalize_metadata(data, path)

    def _normalize_metadata(self, data: dict, path: Path) -> dict:
        """Normalize ExifTool output to consistent field names.

        Handles format prefixes (FLAC:, ID3:, Vorbis:) and extracts
        all available metadata fields.
        """
        def get_first(*keys):
            """Get first non-empty value from multiple possible tag names."""
            for key in keys:
                # Try exact match
                if key in data and data[key]:
                    return data[key]
                # Try with format prefix (FLAC:, ID3:, Vorbis:, QuickTime:)
                for prefix in ["FLAC:", "ID3:", "Vorbis:", "QuickTime:", "MPEG:"]:
                    prefixed = f"{prefix}{key}"
                    if prefixed in data and data[prefixed]:
                        return data[prefixed]
            return None

        file_type = data.get("FileType", path.suffix.lstrip(".")).upper()
        is_lossy = file_type.lower() in self.LOSSY_FORMATS

        # Extract year from various tag formats (Qobuz uses DATE)
        year = get_first("Year")
        if not year:
            date_str = get_first("Date", "OriginalDate") or ""
            if date_str and len(str(date_str)) >= 4:
                try:
                    year = int(str(date_str)[:4])
                except ValueError:
                    year = None

        # Extract lyrics from multiple possible tags
        lyrics = get_first("Lyrics", "UnsyncedLyrics", "USLT")

        # Extract MusicBrainz IDs (various tag names used)
        mb_track_id = get_first(
            "MusicBrainz Track Id",
            "MUSICBRAINZ_TRACKID",
            "MusicBrainzTrackId"
        )
        mb_album_id = get_first(
            "MusicBrainz Album Id",
            "MUSICBRAINZ_ALBUMID",
            "MusicBrainzAlbumId"
        )
        mb_artist_id = get_first(
            "MusicBrainz Artist Id",
            "MUSICBRAINZ_ARTISTID",
            "MusicBrainzArtistId"
        )

        # Detect compilation
        compilation_raw = get_first("Compilation")
        is_compilation = compilation_raw in ["1", "true", True, 1]

        # Detect explicit content
        explicit_raw = get_first("ContentRating", "Explicit")
        is_explicit = (
            explicit_raw == "Explicit" or
            explicit_raw in ["1", "true", True, 1]
        )

        return {
            # Core
            "title": get_first("Title"),
            "artist": get_first("AlbumArtist", "Artist"),
            "album": get_first("Album"),
            "album_artist": get_first("AlbumArtist"),
            "track_number": self._parse_track_number(get_first("TrackNumber")),
            "disc_number": self._parse_disc_number(get_first("DiscNumber")) or 1,
            "year": year,

            # Quality
            "sample_rate": get_first("SampleRate"),
            "bit_depth": get_first("BitsPerSample"),
            "bitrate": get_first("AudioBitrate"),
            "channels": get_first("NumChannels", "AudioChannels") or 2,
            "duration": int(get_first("Duration") or 0),
            "file_size": get_first("FileSize") or path.stat().st_size,
            "format": file_type,
            "is_lossy": is_lossy,

            # Extended metadata
            "genre": get_first("Genre"),
            "composer": get_first("Composer"),
            "label": get_first("Label", "Publisher"),
            "catalog_number": get_first("CatalogNumber"),
            "isrc": self._normalize_isrc(get_first("ISRC")),
            "is_compilation": is_compilation,
            "explicit": is_explicit,

            # Lyrics
            "lyrics": lyrics,

            # MusicBrainz IDs
            "musicbrainz_track_id": mb_track_id,
            "musicbrainz_album_id": mb_album_id,
            "musicbrainz_artist_id": mb_artist_id,

            # Path
            "path": str(path)
        }

    def _normalize_isrc(self, isrc: str) -> str | None:
        """Normalize ISRC to standard format (no hyphens, uppercase).

        ISRC format: CC-XXX-YY-NNNNN (12 characters when normalized)
        """
        if not isrc:
            return None
        # Remove hyphens, spaces, uppercase
        normalized = str(isrc).replace("-", "").replace(" ", "").upper()
        # Validate: should be 12 characters
        if len(normalized) == 12:
            return normalized
        return None

    def _parse_track_number(self, value) -> int | None:
        """Parse track number from various formats (e.g., '3/12' or '3')."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        value_str = str(value)
        if "/" in value_str:
            value_str = value_str.split("/")[0]
        try:
            return int(value_str)
        except ValueError:
            return None

    def _parse_disc_number(self, value) -> int | None:
        """Parse disc number from various formats (e.g., '1/2' or '1')."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        value_str = str(value)
        if "/" in value_str:
            value_str = value_str.split("/")[0]
        try:
            return int(value_str)
        except ValueError:
            return None

    async def get_album_metadata(self, path: Path) -> list[dict]:
        """Extract metadata from all audio files in folder.

        Args:
            path: Path to album folder

        Returns:
            List of track metadata dicts
        """
        tracks = []

        for file in sorted(path.iterdir()):
            if file.suffix.lower() in self.AUDIO_EXTENSIONS:
                metadata = await self.get_metadata(file)
                tracks.append(metadata)

        return tracks

    async def write_metadata(
        self,
        path: Path,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        title: Optional[str] = None,
        track_number: Optional[int] = None,
        year: Optional[int] = None
    ) -> None:
        """Write metadata tags to audio file.

        Args:
            path: Path to audio file
            **kwargs: Tag values to write
        """
        cmd = ["exiftool", "-overwrite_original"]

        if artist:
            cmd.append(f"-Artist={artist}")
        if album:
            cmd.append(f"-Album={album}")
        if title:
            cmd.append(f"-Title={title}")
        if track_number:
            cmd.append(f"-TrackNumber={track_number}")
        if year:
            cmd.append(f"-Year={year}")

        cmd.append(str(path))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

    def _basic_metadata(self, path: Path) -> dict:
        """Return basic metadata when exiftool fails."""
        return {
            # Core
            "title": path.stem,
            "artist": None,
            "album": None,
            "album_artist": None,
            "track_number": None,
            "disc_number": 1,
            "year": None,

            # Quality
            "sample_rate": None,
            "bit_depth": None,
            "bitrate": None,
            "channels": 2,
            "duration": 0,
            "file_size": path.stat().st_size if path.exists() else 0,
            "format": path.suffix.lstrip(".").upper(),
            "is_lossy": path.suffix.lower().lstrip(".") in self.LOSSY_FORMATS,

            # Extended metadata
            "genre": None,
            "composer": None,
            "label": None,
            "catalog_number": None,
            "isrc": None,
            "is_compilation": False,
            "explicit": False,

            # Lyrics
            "lyrics": None,

            # MusicBrainz IDs
            "musicbrainz_track_id": None,
            "musicbrainz_album_id": None,
            "musicbrainz_artist_id": None,

            # Path
            "path": str(path)
        }


def quality_score(sample_rate: Optional[int], bit_depth: Optional[int]) -> int:
    """Calculate quality score for comparison.

    Higher is better. Used for duplicate detection.

    Examples:
        44100 * 16 = 705,600 (CD quality)
        96000 * 24 = 2,304,000 (Hi-Res)
        192000 * 24 = 4,608,000 (Ultra Hi-Res)
    """
    sr = sample_rate or 44100
    bd = bit_depth or 16
    return sr * bd


def format_quality(sample_rate: Optional[int], bit_depth: Optional[int], format: str, is_lossy: bool, bitrate: Optional[int] = None) -> str:
    """Format quality string for display.

    Returns:
        String like "24/192 FLAC" or "320kbps MP3"
    """
    if is_lossy:
        br = bitrate or 0
        return f"{br}kbps {format}"

    bd = bit_depth or 16
    sr = (sample_rate or 44100) // 1000
    return f"{bd}/{sr} {format}"
