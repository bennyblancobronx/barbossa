"""Torrent creation service."""
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List
from app.config import settings
from app.models.album import Album


class TorrentError(Exception):
    """Torrent operation failed."""
    pass


class TorrentService:
    """Creates .torrent files and NFOs."""

    def __init__(self):
        self.output_dir = Path(settings.music_downloads) / "torrents"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def create_torrent(
        self,
        source_path: str,
        name: str,
        trackers: List[str],
        piece_size: int = 18  # 2^18 = 256KB pieces
    ) -> Path:
        """Create .torrent file using mktorrent.

        Args:
            source_path: Path to album folder
            name: Release name
            trackers: List of tracker announce URLs
            piece_size: Piece size exponent (2^n)

        Returns:
            Path to created .torrent file
        """
        output_path = self.output_dir / f"{name}.torrent"

        cmd = [
            "mktorrent",
            "-p",  # Private torrent
            "-l", str(piece_size),
        ]

        for tracker in trackers:
            cmd.extend(["-a", tracker])

        cmd.extend([
            "-o", str(output_path),
            source_path
        ])

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise TorrentError(stderr.decode())

        return output_path

    async def generate_nfo(self, album: Album, release_name: str) -> Path:
        """Generate NFO file for release."""
        nfo_path = self.output_dir / f"{release_name}.nfo"

        # Get quality info from first track
        first_track = album.tracks.first()
        quality = "Unknown"
        if first_track:
            if first_track.is_lossy:
                quality = f"{first_track.bitrate}kbps {first_track.format}"
            else:
                sr = first_track.sample_rate // 1000 if first_track.sample_rate else 44
                bd = first_track.bit_depth or 16
                quality = f"{bd}/{sr}kHz {first_track.format}"

        nfo_content = f"""
================================================================================
                              {release_name}
================================================================================

Artist:  {album.artist.name}
Album:   {album.title}
Year:    {album.year or 'Unknown'}
Genre:   {album.genre or 'Unknown'}
Label:   {album.label or 'Unknown'}
Quality: {quality}
Tracks:  {album.total_tracks}

--------------------------------------------------------------------------------
                                 TRACKLIST
--------------------------------------------------------------------------------
"""

        for track in album.tracks.order_by("disc_number", "track_number"):
            duration = f"{track.duration // 60}:{track.duration % 60:02d}" if track.duration else "?:??"
            nfo_content += f"\n{track.track_number:02d}. {track.title} [{duration}]"

        nfo_content += f"""

--------------------------------------------------------------------------------

Source: {album.source or 'Unknown'}
Ripped with Barbossa Music Library
"""

        nfo_path.write_text(nfo_content.strip())
        return nfo_path
