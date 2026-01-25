"""Bandcamp integration for syncing purchased collection."""
import asyncio
from pathlib import Path
from typing import Optional, List, Callable
from app.config import settings


class BandcampError(Exception):
    """Bandcamp operation failed."""
    pass


class BandcampClient:
    """Bandcamp collection sync via bandcamp-collection-downloader."""

    def __init__(self):
        self.cookies_path = Path(settings.bandcamp_cookies) if settings.bandcamp_cookies else None
        self.download_path = Path(settings.music_downloads) / "bandcamp"

    async def sync_collection(
        self,
        cookies_file: Optional[Path] = None,
        progress_callback: Optional[Callable] = None
    ) -> List[Path]:
        """Download user's purchased Bandcamp collection.

        Args:
            cookies_file: Path to cookies.txt with Bandcamp session
            progress_callback: Callback for progress updates

        Returns:
            List of downloaded album paths
        """
        cookies = cookies_file or self.cookies_path
        if not cookies or not cookies.exists():
            raise BandcampError("Bandcamp cookies file not found")

        self.download_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "bandcamp-collection-downloader",
            "--cookies", str(cookies),
            "--output", str(self.download_path),
            "--format", "flac",
            "--skip-existing"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        downloaded = []
        async for line in process.stdout:
            text = line.decode().strip()

            # Parse output for downloaded albums
            if "Downloaded:" in text or "Downloading:" in text:
                # Extract path from output
                parts = text.split(":")
                if len(parts) > 1:
                    path_str = parts[-1].strip()
                    if path_str:
                        downloaded.append(Path(path_str))

                if progress_callback:
                    await progress_callback(f"Downloaded: {path_str}")

        await process.wait()

        if process.returncode != 0:
            raise BandcampError("Bandcamp sync failed")

        return downloaded

    async def get_collection_info(self, cookies_file: Optional[Path] = None) -> dict:
        """Get info about Bandcamp collection without downloading.

        Returns count and list of purchased items.
        """
        cookies = cookies_file or self.cookies_path
        if not cookies or not cookies.exists():
            raise BandcampError("Bandcamp cookies file not found")

        cmd = [
            "bandcamp-collection-downloader",
            "--cookies", str(cookies),
            "--dry-run"
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        stdout, _ = await process.communicate()
        output = stdout.decode()

        # Parse output to get collection info
        items = []
        for line in output.split("\n"):
            if line.strip() and not line.startswith("["):
                items.append(line.strip())

        return {
            "count": len(items),
            "items": items[:50]  # Return first 50 for preview
        }
