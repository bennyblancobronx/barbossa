"""Post-import enrichment service.

Phase 8 of audit-014: Enrich tracks with missing metadata after import.
Supports:
- Lyrics fetching from LRCLIB.net (free, no API key required)
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models.track import Track
from app.models.album import Album
from app.models.artist import Artist

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    """Result of enrichment operation."""
    track_id: int
    field: str
    success: bool
    message: Optional[str] = None


@dataclass
class BatchEnrichmentResult:
    """Result of batch enrichment operation."""
    total: int
    enriched: int
    failed: int
    skipped: int
    results: list[EnrichmentResult]


class EnrichmentService:
    """Service for enriching track metadata post-import.

    Currently supports:
    - Lyrics fetching from LRCLIB.net

    Future enhancements:
    - Additional lyrics sources (Genius, Musixmatch)
    - Album artwork fetching
    - MusicBrainz metadata enrichment
    """

    # LRCLIB.net - free lyrics API
    LRCLIB_BASE_URL = "https://lrclib.net/api"

    def __init__(self, db: Session):
        self.db = db

    async def fetch_lyrics_lrclib(
        self,
        artist: str,
        title: str,
        album: Optional[str] = None,
        duration: Optional[int] = None
    ) -> Optional[str]:
        """Fetch lyrics from LRCLIB.net.

        LRCLIB.net is a free, community-driven lyrics database.
        No API key required.

        Args:
            artist: Artist name
            title: Track title
            album: Optional album name for better matching
            duration: Optional track duration in seconds

        Returns:
            Plain text lyrics or None if not found
        """
        if not artist or not title:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Build query params
                params = {
                    "artist_name": artist,
                    "track_name": title,
                }
                if album:
                    params["album_name"] = album
                if duration:
                    params["duration"] = duration

                # Try the get endpoint first (exact match)
                response = await client.get(
                    f"{self.LRCLIB_BASE_URL}/get",
                    params=params
                )

                if response.status_code == 200:
                    data = response.json()
                    # Prefer plain lyrics over synced
                    lyrics = data.get("plainLyrics") or data.get("syncedLyrics")
                    if lyrics:
                        logger.debug(f"Found lyrics for {artist} - {title}")
                        return lyrics

                # Try search endpoint as fallback
                response = await client.get(
                    f"{self.LRCLIB_BASE_URL}/search",
                    params={"q": f"{artist} {title}"}
                )

                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        # Take first match
                        data = results[0]
                        lyrics = data.get("plainLyrics") or data.get("syncedLyrics")
                        if lyrics:
                            logger.debug(f"Found lyrics via search for {artist} - {title}")
                            return lyrics

                logger.debug(f"No lyrics found for {artist} - {title}")
                return None

        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching lyrics for {artist} - {title}")
            return None
        except Exception as e:
            logger.warning(f"Error fetching lyrics for {artist} - {title}: {e}")
            return None

    async def enrich_track_lyrics(self, track: Track) -> EnrichmentResult:
        """Enrich a single track with lyrics if missing.

        Args:
            track: Track to enrich

        Returns:
            EnrichmentResult indicating success/failure
        """
        if track.lyrics:
            return EnrichmentResult(
                track_id=track.id,
                field="lyrics",
                success=False,
                message="Already has lyrics"
            )

        # Get artist name from album relationship
        artist_name = None
        album_title = None
        if track.album:
            album_title = track.album.title
            if track.album.artist:
                artist_name = track.album.artist.name

        if not artist_name:
            return EnrichmentResult(
                track_id=track.id,
                field="lyrics",
                success=False,
                message="No artist name available"
            )

        lyrics = await self.fetch_lyrics_lrclib(
            artist=artist_name,
            title=track.title,
            album=album_title,
            duration=track.duration
        )

        if lyrics:
            track.lyrics = lyrics
            self.db.commit()
            return EnrichmentResult(
                track_id=track.id,
                field="lyrics",
                success=True,
                message="Lyrics fetched from LRCLIB"
            )

        return EnrichmentResult(
            track_id=track.id,
            field="lyrics",
            success=False,
            message="No lyrics found"
        )

    async def enrich_album_lyrics(self, album_id: int) -> BatchEnrichmentResult:
        """Enrich all tracks in an album with lyrics.

        Args:
            album_id: Album ID to enrich

        Returns:
            BatchEnrichmentResult with per-track results
        """
        album = self.db.query(Album).filter(Album.id == album_id).first()
        if not album:
            return BatchEnrichmentResult(
                total=0,
                enriched=0,
                failed=0,
                skipped=0,
                results=[]
            )

        results = []
        enriched = 0
        failed = 0
        skipped = 0

        # Convert to list to handle lazy loading
        tracks = list(album.tracks)

        for track in tracks:
            result = await self.enrich_track_lyrics(track)
            results.append(result)

            if result.success:
                enriched += 1
            elif result.message == "Already has lyrics":
                skipped += 1
            else:
                failed += 1

        return BatchEnrichmentResult(
            total=len(tracks),
            enriched=enriched,
            failed=failed,
            skipped=skipped,
            results=results
        )

    async def enrich_missing_lyrics(
        self,
        limit: int = 100,
        album_id: Optional[int] = None,
        artist_id: Optional[int] = None
    ) -> BatchEnrichmentResult:
        """Enrich tracks missing lyrics.

        Args:
            limit: Maximum tracks to process
            album_id: Optional filter by album
            artist_id: Optional filter by artist

        Returns:
            BatchEnrichmentResult with per-track results
        """
        query = self.db.query(Track).filter(
            Track.lyrics.is_(None)
        )

        if album_id:
            query = query.filter(Track.album_id == album_id)
        elif artist_id:
            query = query.join(Album).filter(Album.artist_id == artist_id)

        tracks = query.limit(limit).all()

        results = []
        enriched = 0
        failed = 0

        for track in tracks:
            result = await self.enrich_track_lyrics(track)
            results.append(result)

            if result.success:
                enriched += 1
            else:
                failed += 1

            # Small delay to avoid overwhelming the API
            if enriched + failed < len(tracks):
                await asyncio.sleep(0.5)

        return BatchEnrichmentResult(
            total=len(tracks),
            enriched=enriched,
            failed=failed,
            skipped=0,
            results=results
        )

    def get_tracks_missing_lyrics(
        self,
        limit: int = 100,
        album_id: Optional[int] = None
    ) -> list[Track]:
        """Get tracks that are missing lyrics.

        Args:
            limit: Maximum tracks to return
            album_id: Optional filter by album

        Returns:
            List of tracks without lyrics
        """
        query = self.db.query(Track).filter(
            Track.lyrics.is_(None)
        )

        if album_id:
            query = query.filter(Track.album_id == album_id)

        return query.limit(limit).all()

    def get_enrichment_stats(self) -> dict:
        """Get statistics about enrichable metadata.

        Returns:
            Dict with counts of tracks missing various metadata
        """
        total_tracks = self.db.query(Track).count()
        missing_lyrics = self.db.query(Track).filter(Track.lyrics.is_(None)).count()
        missing_isrc = self.db.query(Track).filter(Track.isrc.is_(None)).count()
        missing_composer = self.db.query(Track).filter(Track.composer.is_(None)).count()

        return {
            "total_tracks": total_tracks,
            "missing_lyrics": missing_lyrics,
            "missing_isrc": missing_isrc,
            "missing_composer": missing_composer,
            "lyrics_coverage_pct": round((total_tracks - missing_lyrics) / total_tracks * 100, 1) if total_tracks > 0 else 0.0
        }
