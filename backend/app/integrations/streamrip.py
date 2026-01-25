"""Streamrip wrapper for Qobuz downloads."""
import asyncio
import json
import re
from pathlib import Path
from typing import Optional, Callable, Any
from app.config import settings


class StreamripError(Exception):
    """Streamrip operation failed."""
    pass


class StreamripClient:
    """Wrapper for streamrip CLI.

    Streamrip handles Qobuz downloads with quality selection.
    Quality levels: 0=MP3 128, 1=MP3 320, 2=FLAC 16/44, 3=FLAC 24/96, 4=FLAC 24/192
    """

    def __init__(self):
        self.config_path = Path("/config/streamrip.toml")
        self._download_path = None

    @property
    def download_path(self) -> Path:
        """Lazy-initialize download path."""
        if self._download_path is None:
            self._download_path = Path(settings.music_downloads) / "qobuz"
            self._download_path.mkdir(parents=True, exist_ok=True)
        return self._download_path

    async def search(
        self,
        query: str,
        search_type: str = "album",
        limit: int = 20
    ) -> list[dict]:
        """Search Qobuz catalog.

        Args:
            query: Search terms
            search_type: artist, album, track, or playlist
            limit: Max results

        Returns:
            List of search results with id, title, artist, year, quality, url
        """
        if search_type not in ("artist", "album", "track", "playlist"):
            raise StreamripError(f"Invalid search type: {search_type}")

        cmd = [
            "rip", "search", "qobuz",
            "--type", search_type,
            "--limit", str(limit),
            query
        ]

        result = await self._run_command(cmd)
        return self._parse_search_results(result, search_type)

    async def download(
        self,
        url: str,
        quality: int = 4,
        callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Path:
        """Download from Qobuz URL.

        Args:
            url: Qobuz album/track URL
            quality: 0=MP3 128, 1=MP3 320, 2=FLAC 16/44, 3=FLAC 24/96, 4=FLAC 24/192
            callback: Progress callback(percent, speed, eta)

        Returns:
            Path to downloaded folder
        """
        if not 0 <= quality <= 4:
            quality = 4

        cmd = [
            "rip", "url",
            "--quality", str(quality),
            "--output", str(self.download_path),
            url
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        output_path = None
        async for line in process.stdout:
            text = line.decode().strip()

            # Parse progress: "Downloading: 45% | 2.5 MB/s | ETA: 00:01:30"
            if "Downloading:" in text and callback:
                progress = self._parse_progress(text)
                if progress:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*progress)
                    else:
                        callback(*progress)

            # Parse output path: "Saved to /music/downloads/Artist - Album"
            if "Saved to" in text:
                output_path = Path(text.split("Saved to")[-1].strip())

        await process.wait()

        if process.returncode != 0:
            raise StreamripError(f"Download failed with code {process.returncode}")

        # If we didn't catch the output path, find the newest directory
        if output_path is None:
            output_path = self._find_newest_folder()

        return output_path

    async def download_by_id(
        self,
        item_id: str,
        item_type: str = "album",
        quality: int = 4,
        callback: Optional[Callable[[int, str, str], Any]] = None
    ) -> Path:
        """Download by Qobuz ID.

        Args:
            item_id: Qobuz item ID
            item_type: album or track
            quality: Quality tier
            callback: Progress callback

        Returns:
            Path to downloaded folder
        """
        cmd = [
            "rip", item_type,
            "--quality", str(quality),
            "--output", str(self.download_path),
            "qobuz", item_id
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        output_path = None
        async for line in process.stdout:
            text = line.decode().strip()

            if "Downloading:" in text and callback:
                progress = self._parse_progress(text)
                if progress:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*progress)
                    else:
                        callback(*progress)

            if "Saved to" in text:
                output_path = Path(text.split("Saved to")[-1].strip())

        await process.wait()

        if process.returncode != 0:
            raise StreamripError(f"Download failed with code {process.returncode}")

        if output_path is None:
            output_path = self._find_newest_folder()

        return output_path

    async def _run_command(self, cmd: list[str]) -> str:
        """Run streamrip command and return output."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise StreamripError(stderr.decode() or stdout.decode())

        return stdout.decode()

    def _parse_search_results(self, output: str, search_type: str) -> list[dict]:
        """Parse streamrip search output."""
        results = []

        # Try JSON format first
        try:
            data = json.loads(output)
            for item in data.get("results", []):
                results.append({
                    "id": str(item["id"]),
                    "title": item.get("title", item.get("name")),
                    "artist": item.get("artist", {}).get("name", "Unknown"),
                    "year": str(item.get("release_date_original", ""))[:4],
                    "quality": item.get("maximum_bit_depth", 16),
                    "url": f"https://www.qobuz.com/us-en/{search_type}/{item['id']}"
                })
            return results
        except json.JSONDecodeError:
            pass

        # Fallback: parse text output line by line
        # Format varies, but typically: "1. Artist - Album (Year)"
        for line in output.strip().split("\n"):
            match = re.match(r"^\d+\.\s*(.+?)\s*-\s*(.+?)(?:\s*\((\d{4})\))?$", line)
            if match:
                results.append({
                    "id": "",
                    "title": match.group(2).strip(),
                    "artist": match.group(1).strip(),
                    "year": match.group(3) or "",
                    "quality": 16,
                    "url": ""
                })

        return results

    def _parse_progress(self, text: str) -> Optional[tuple]:
        """Parse progress line into (percent, speed, eta)."""
        match = re.search(r"(\d+)%.*?(\d+\.?\d*\s*\w+/s).*?(\d{2}:\d{2}:\d{2})", text)
        if match:
            return int(match.group(1)), match.group(2), match.group(3)
        return None

    def _find_newest_folder(self) -> Path:
        """Find the most recently modified folder in download path."""
        folders = [f for f in self.download_path.iterdir() if f.is_dir()]
        if not folders:
            raise StreamripError("No downloaded folders found")
        return max(folders, key=lambda f: f.stat().st_mtime)
