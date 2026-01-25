"""Quality service for extracting and comparing audio quality."""
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackQuality:
    """Audio quality metadata."""
    sample_rate: int
    bit_depth: int
    bitrate: int
    channels: int
    file_size: int
    format: str
    is_lossy: bool


class QualityService:
    """Service for extracting and comparing audio quality."""

    # Lossy formats
    LOSSY_FORMATS = {"mp3", "aac", "ogg", "opus", "m4a", "wma"}

    def extract(self, file_path: Path) -> Optional[TrackQuality]:
        """Extract audio quality metadata using exiftool."""
        try:
            from exiftool import ExifToolHelper
        except ImportError:
            return self._extract_fallback(file_path)

        try:
            with ExifToolHelper() as et:
                tags = et.get_tags(
                    [str(file_path)],
                    tags=[
                        "SampleRate",
                        "BitsPerSample",
                        "AudioBitrate",
                        "AudioChannels",
                        "FileSize",
                        "FileType",
                    ],
                )[0]

            format_type = tags.get("File:FileType", "").upper()
            is_lossy = format_type.lower() in self.LOSSY_FORMATS

            return TrackQuality(
                sample_rate=tags.get("FLAC:SampleRate") or tags.get("MPEG:SampleRate") or 44100,
                bit_depth=tags.get("FLAC:BitsPerSample") or 16,
                bitrate=tags.get("MPEG:AudioBitrate") or 0,
                channels=tags.get("FLAC:AudioChannels") or tags.get("MPEG:AudioChannels") or 2,
                file_size=tags.get("File:FileSize") or file_path.stat().st_size,
                format=format_type,
                is_lossy=is_lossy,
            )
        except Exception:
            return self._extract_fallback(file_path)

    def _extract_fallback(self, file_path: Path) -> Optional[TrackQuality]:
        """Fallback extraction using mutagen."""
        try:
            import mutagen

            audio = mutagen.File(str(file_path))
            if audio is None:
                return None

            info = audio.info
            format_type = file_path.suffix.lstrip(".").upper()
            is_lossy = format_type.lower() in self.LOSSY_FORMATS

            return TrackQuality(
                sample_rate=getattr(info, "sample_rate", 44100),
                bit_depth=getattr(info, "bits_per_sample", 16),
                bitrate=int(getattr(info, "bitrate", 0) / 1000),
                channels=getattr(info, "channels", 2),
                file_size=file_path.stat().st_size,
                format=format_type,
                is_lossy=is_lossy,
            )
        except Exception:
            return None

    def is_better_quality(self, new: TrackQuality, existing: TrackQuality) -> bool:
        """Check if new file is higher quality than existing."""
        # Lossless always beats lossy
        if not new.is_lossy and existing.is_lossy:
            return True
        if new.is_lossy and not existing.is_lossy:
            return False

        # Compare sample rate first
        if new.sample_rate > existing.sample_rate:
            return True
        if new.sample_rate < existing.sample_rate:
            return False

        # Compare bit depth
        if new.bit_depth > existing.bit_depth:
            return True
        if new.bit_depth < existing.bit_depth:
            return False

        # Compare file size (larger = more data = better)
        return new.file_size > existing.file_size

    def quality_score(self, quality: TrackQuality) -> int:
        """Compute numeric quality score for comparison."""
        # Lossy penalty
        if quality.is_lossy:
            return quality.bitrate

        # Lossless: sample_rate * 100 + bit_depth
        return (quality.sample_rate * 100) + quality.bit_depth

    def quality_display(self, quality: TrackQuality) -> str:
        """Human-readable quality string."""
        if quality.is_lossy:
            return f"{quality.bitrate}kbps {quality.format}"
        return f"{quality.bit_depth}/{quality.sample_rate // 1000}kHz {quality.format}"

    def quality_tier(self, quality: TrackQuality) -> str:
        """Quality tier classification."""
        if quality.is_lossy:
            return "Lossy"
        if quality.sample_rate >= 192000 and quality.bit_depth == 24:
            return "Ultra Hi-Res"
        if quality.sample_rate >= 96000 and quality.bit_depth == 24:
            return "Hi-Res"
        if quality.sample_rate >= 44100 and quality.bit_depth >= 16:
            return "CD Quality"
        return "Unknown"


def generate_checksum(file_path: Path) -> str:
    """Generate SHA-256 checksum for integrity verification."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()
