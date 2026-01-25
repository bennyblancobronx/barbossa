"""yt-dlp wrapper for YouTube, Bandcamp, Soundcloud."""
import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Callable, Any
from app.config import settings


class YtdlpError(Exception):
    """yt-dlp operation failed."""
    pass


class YtdlpClient:
    """Wrapper for yt-dlp CLI.

    Handles YouTube, Bandcamp, Soundcloud, and 1800+ other sites.
    Note: Output is always lossy even if converted to FLAC (source is compressed).
    """

    def __init__(self):
        self._download_path = None

    @property
    def download_path(self) -> Path:
        """Lazy-initialize download path."""
        if self._download_path is None:
            self._download_path = Path(settings.music_downloads) / "url"
            self._download_path.mkdir(parents=True, exist_ok=True)
        return self._download_path

    async def get_info(self, url: str) -> dict:
        """Get metadata without downloading.

        Returns:
            Dict with title, artist, album, duration, is_lossy, thumbnail, source
        """
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise YtdlpError(stderr.decode() or "Failed to get info")

        data = json.loads(stdout.decode())

        return {
            "title": data.get("title", "Unknown"),
            "artist": data.get("artist") or data.get("uploader") or data.get("channel", "Unknown"),
            "album": data.get("album") or data.get("playlist_title") or "Singles",
            "duration": data.get("duration"),
            "is_lossy": True,  # Always lossy from these sources
            "thumbnail": data.get("thumbnail"),
            "source": self._detect_source(url),
            "webpage_url": data.get("webpage_url", url),
            "description": data.get("description", "")[:500]
        }

    async def download(
        self,
        url: str,
        output_template: Optional[str] = None,
        callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Path:
        """Download audio from URL.

        Args:
            url: YouTube, Bandcamp, or Soundcloud URL
            output_template: Custom output path template
            callback: Progress callback(percent, speed, eta)

        Returns:
            Path to downloaded file or folder
        """
        # Get info first to structure output
        info = await self.get_info(url)
        artist = self._sanitize_filename(info["artist"])
        album = self._sanitize_filename(info["album"])
        title = self._sanitize_filename(info["title"])

        output_dir = self.download_path / artist / album
        output_dir.mkdir(parents=True, exist_ok=True)

        output = output_template or str(output_dir / f"%(track_number|01)02d - {title}.%(ext)s")

        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "best",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
            "--output", output,
            "--progress",
            "--newline",
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        final_path = None
        async for line in process.stdout:
            text = line.decode().strip()

            # Parse progress: "[download]  45.2% of 10.5MiB at 2.5MiB/s ETA 00:05"
            if "[download]" in text and "%" in text and callback:
                progress = self._parse_progress(text)
                if progress:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*progress)
                    else:
                        callback(*progress)

            # Parse final path: "[ExtractAudio] Destination: /path/to/file.mp3"
            if "Destination:" in text:
                final_path = Path(text.split("Destination:")[-1].strip())

        await process.wait()

        if process.returncode != 0:
            raise YtdlpError(f"Download failed with code {process.returncode}")

        # Return the album folder
        return output_dir if output_dir.exists() else final_path.parent if final_path else self.download_path

    async def download_playlist(
        self,
        url: str,
        callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Path:
        """Download entire playlist.

        Args:
            url: Playlist URL
            callback: Progress callback

        Returns:
            Path to downloaded folder
        """
        # Get playlist info
        info = await self.get_info(url)
        artist = self._sanitize_filename(info.get("artist", "Various"))
        album = self._sanitize_filename(info.get("album", "Playlist"))

        output_dir = self.download_path / artist / album
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "best",
            "--audio-quality", "0",
            "--embed-thumbnail",
            "--add-metadata",
            "--output", str(output_dir / "%(playlist_index|01)02d - %(title)s.%(ext)s"),
            "--progress",
            "--newline",
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        async for line in process.stdout:
            text = line.decode().strip()

            if "[download]" in text and "%" in text and callback:
                progress = self._parse_progress(text)
                if progress:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*progress)
                    else:
                        callback(*progress)

        await process.wait()

        if process.returncode != 0:
            raise YtdlpError(f"Playlist download failed")

        return output_dir

    def _detect_source(self, url: str) -> str:
        """Detect source from URL."""
        url_lower = url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "bandcamp.com" in url_lower:
            return "bandcamp"
        elif "soundcloud.com" in url_lower:
            return "soundcloud"
        elif "mixcloud.com" in url_lower:
            return "mixcloud"
        elif "archive.org" in url_lower:
            return "archive"
        return "url"

    def _parse_progress(self, text: str) -> Optional[tuple]:
        """Parse yt-dlp progress line."""
        match = re.search(r"(\d+\.?\d*)%.*?(\d+\.?\d*\w+/s).*?ETA\s*(\d{2}:\d{2})", text)
        if match:
            return int(float(match.group(1))), match.group(2), f"00:{match.group(3)}"

        # Simpler format without speed/eta
        match = re.search(r"(\d+\.?\d*)%", text)
        if match:
            return int(float(match.group(1))), "", ""

        return None

    def _sanitize_filename(self, name: str) -> str:
        """Remove invalid characters from filename."""
        if not name:
            return "Unknown"
        # Remove invalid chars
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        # Limit length
        return sanitized[:100].strip() or "Unknown"
