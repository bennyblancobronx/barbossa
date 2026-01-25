"""Streamrip wrapper for Qobuz downloads."""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Optional, Callable, Any
from app.config import settings, get_settings


class StreamripError(Exception):
    """Streamrip operation failed."""
    pass


class StreamripClient:
    """Wrapper for streamrip CLI.

    Streamrip handles Qobuz downloads with quality selection.
    Quality levels: 0=MP3 128, 1=MP3 320, 2=FLAC 16/44, 3=FLAC 24/96, 4=FLAC 24/192
    """

    def __init__(self):
        self._download_path = None
        self._config_synced = False

    @property
    def download_path(self) -> Path:
        """Lazy-initialize download path."""
        if self._download_path is None:
            self._download_path = Path(settings.music_downloads) / "qobuz"
            self._download_path.mkdir(parents=True, exist_ok=True)
        return self._download_path

    def _get_streamrip_config_path(self) -> Path:
        """Find streamrip config file location."""
        # macOS: ~/Library/Application Support/streamrip/config.toml
        # Linux: ~/.config/streamrip/config.toml
        import platform

        if platform.system() == "Darwin":
            config_dir = Path.home() / "Library" / "Application Support" / "streamrip"
        else:
            config_dir = Path.home() / ".config" / "streamrip"

        return config_dir / "config.toml"

    def _sync_credentials(self) -> None:
        """Sync Qobuz credentials from Barbossa settings to streamrip config.

        Streamrip requires credentials in its config.toml file.
        This method updates that file with credentials from Barbossa settings.
        """
        # Get fresh settings (not cached)
        current_settings = get_settings()

        if not current_settings.qobuz_email or not current_settings.qobuz_password:
            raise StreamripError(
                "Qobuz credentials not configured. "
                "Go to Settings > Sources > Qobuz to add your email and password."
            )

        config_path = self._get_streamrip_config_path()

        if not config_path.exists():
            # Run rip once to generate default config
            import subprocess
            subprocess.run(["rip", "--help"], capture_output=True)

        if not config_path.exists():
            raise StreamripError(
                f"Streamrip config not found at {config_path}. "
                "Please run 'rip config --qobuz' to initialize."
            )

        # Read current config
        with open(config_path, 'r') as f:
            config_content = f.read()

        # Hash password for streamrip (it expects md5 hash, not plaintext)
        password_hash = hashlib.md5(
            current_settings.qobuz_password.encode()
        ).hexdigest()

        # Update email_or_userid
        config_content = re.sub(
            r'^email_or_userid\s*=\s*".*"',
            f'email_or_userid = "{current_settings.qobuz_email}"',
            config_content,
            flags=re.MULTILINE
        )

        # Update password_or_token (md5 hash)
        config_content = re.sub(
            r'^password_or_token\s*=\s*".*"',
            f'password_or_token = "{password_hash}"',
            config_content,
            flags=re.MULTILINE
        )

        # Update quality setting
        config_content = re.sub(
            r'^\[qobuz\]\n.*?quality\s*=\s*\d+',
            f'[qobuz]\nquality = {current_settings.qobuz_quality}',
            config_content,
            flags=re.MULTILINE | re.DOTALL
        )

        # Update download folder
        config_content = re.sub(
            r'^folder\s*=\s*".*?"',
            f'folder = "{self.download_path}"',
            config_content,
            flags=re.MULTILINE
        )

        # Write updated config
        with open(config_path, 'w') as f:
            f.write(config_content)

        self._config_synced = True

    def _ensure_credentials(self) -> None:
        """Ensure credentials are synced before operations."""
        if not self._config_synced:
            self._sync_credentials()

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

        # Sync Qobuz credentials from Barbossa settings to streamrip config
        self._ensure_credentials()

        # Use temp file for output since -o doesn't support stdout
        import tempfile

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            output_file = f.name

        try:
            # Correct syntax: rip search <source> <type> <query> -n <limit> -o <file>
            cmd = [
                "rip", "search",
                "qobuz",
                search_type,
                query,
                "-n", str(limit),
                "-o", output_file
            ]

            await self._run_command(cmd)

            # Read results from output file
            with open(output_file, 'r') as f:
                result = f.read()

            return self._parse_search_results(result, search_type)
        finally:
            # Clean up temp file
            if os.path.exists(output_file):
                os.unlink(output_file)

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
        # Sync credentials before download
        self._ensure_credentials()

        if not 0 <= quality <= 4:
            quality = 4

        # Note: rip url doesn't support --quality or --output flags
        # Quality is set in config.toml, and output path is set in config.toml downloads.folder
        # We sync config before downloading, so quality should already be set
        cmd = [
            "rip", "url",
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

        # If we didn't catch the output path, find the newest directory
        if output_path is None:
            output_path = self._find_newest_folder()

        # Validate the download - check for audio files even if return code != 0
        # (streamrip may crash at cleanup step but download succeeded)
        if output_path and output_path.exists():
            audio_files = [
                f for f in output_path.rglob("*")
                if f.suffix.lower() in {".flac", ".mp3", ".m4a", ".ogg", ".wav"}
            ]
            if audio_files:
                # Download succeeded - clean up artwork folder if present
                artwork_dir = output_path / "__artwork"
                if artwork_dir.exists():
                    import shutil
                    try:
                        shutil.rmtree(artwork_dir)
                    except Exception:
                        pass  # Ignore cleanup errors
                return output_path

        # No valid output - report actual failure
        if process.returncode != 0:
            raise StreamripError(f"Download failed with code {process.returncode}")

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
        # Sync credentials before download
        self._ensure_credentials()

        # Note: download by ID uses different syntax
        # rip <media_type> qobuz <id>
        cmd = [
            "rip", item_type,
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

        if output_path is None:
            output_path = self._find_newest_folder()

        # Validate the download - check for audio files even if return code != 0
        if output_path and output_path.exists():
            audio_files = [
                f for f in output_path.rglob("*")
                if f.suffix.lower() in {".flac", ".mp3", ".m4a", ".ogg", ".wav"}
            ]
            if audio_files:
                # Download succeeded - clean up artwork folder if present
                artwork_dir = output_path / "__artwork"
                if artwork_dir.exists():
                    import shutil
                    try:
                        shutil.rmtree(artwork_dir)
                    except Exception:
                        pass  # Ignore cleanup errors
                return output_path

        if process.returncode != 0:
            raise StreamripError(f"Download failed with code {process.returncode}")

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

            # Handle streamrip's JSON array format:
            # [{"source": "qobuz", "media_type": "album", "id": "xxx", "desc": "Album by Artist"}]
            if isinstance(data, list):
                for item in data:
                    # Parse "desc" field: "Album Name by Artist Name"
                    desc = item.get("desc", "")
                    title = desc
                    artist = "Unknown"

                    if " by " in desc:
                        parts = desc.rsplit(" by ", 1)
                        title = parts[0].strip()
                        artist = parts[1].strip() if len(parts) > 1 else "Unknown"

                    # Extract year from title if present (e.g., "Album (2023)")
                    year = ""
                    year_match = re.search(r'\((\d{4})\)', title)
                    if year_match:
                        year = year_match.group(1)

                    results.append({
                        "id": str(item.get("id", "")),
                        "title": title,
                        "artist": artist,
                        "year": year,
                        "quality": 24,  # Assume hi-res for Qobuz
                        "url": f"https://www.qobuz.com/us-en/{search_type}/{item.get('id', '')}"
                    })
                return results

            # Handle older format with "results" key
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
