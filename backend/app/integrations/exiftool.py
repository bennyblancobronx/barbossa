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
    """

    AUDIO_TAGS = [
        "SampleRate",
        "BitsPerSample",
        "AudioBitrate",
        "NumChannels",
        "Duration",
        "FileSize",
        "FileType",
        "Artist",
        "AlbumArtist",
        "Album",
        "Title",
        "TrackNumber",
        "DiscNumber",
        "Year",
        "Date",
        "OriginalDate",
        "Genre",
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

        file_type = data.get("FileType", path.suffix.lstrip(".")).upper()
        is_lossy = file_type.lower() in self.LOSSY_FORMATS

        # Extract year from various tag formats (Qobuz uses DATE)
        year = data.get("Year")
        if not year:
            date_str = data.get("Date") or data.get("OriginalDate") or ""
            if date_str and len(str(date_str)) >= 4:
                try:
                    year = int(str(date_str)[:4])
                except ValueError:
                    year = None

        return {
            "sample_rate": data.get("SampleRate") or data.get("FLAC:SampleRate") or data.get("MPEG:SampleRate"),
            "bit_depth": data.get("BitsPerSample") or data.get("FLAC:BitsPerSample"),
            "bitrate": data.get("AudioBitrate") or data.get("MPEG:AudioBitrate"),
            "channels": data.get("NumChannels") or data.get("AudioChannels") or 2,
            "duration": int(data.get("Duration", 0)),
            "file_size": data.get("FileSize") or path.stat().st_size,
            "format": file_type,
            "is_lossy": is_lossy,
            "artist": data.get("AlbumArtist") or data.get("Artist"),
            "album": data.get("Album"),
            "title": data.get("Title"),
            "track_number": data.get("TrackNumber"),
            "disc_number": data.get("DiscNumber") or 1,
            "year": year,
            "genre": data.get("Genre"),
            "path": str(path)
        }

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
            "sample_rate": None,
            "bit_depth": None,
            "bitrate": None,
            "channels": 2,
            "duration": 0,
            "file_size": path.stat().st_size if path.exists() else 0,
            "format": path.suffix.lstrip(".").upper(),
            "is_lossy": path.suffix.lower().lstrip(".") in self.LOSSY_FORMATS,
            "artist": None,
            "album": None,
            "title": path.stem,
            "track_number": None,
            "disc_number": 1,
            "year": None,
            "genre": None,
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
