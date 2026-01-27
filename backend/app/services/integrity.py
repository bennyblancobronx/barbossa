"""Integrity service for verifying audio file integrity.

Phase 6 of audit-014: File integrity verification before/after import.
"""
import asyncio
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Audio formats that support integrity verification
VERIFIABLE_FORMATS = {".flac", ".wav", ".aiff"}

# FLAC-specific formats
FLAC_FORMATS = {".flac"}


class IntegrityStatus(str, Enum):
    """Result of integrity check."""
    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"  # Format doesn't support verification
    NO_MD5 = "no_md5"    # FLAC without embedded MD5 (common for Qobuz)
    ERROR = "error"      # Check failed to run


@dataclass
class IntegrityResult:
    """Result of a single file integrity check."""
    path: Path
    status: IntegrityStatus
    format: str
    message: Optional[str] = None
    has_embedded_md5: bool = False


@dataclass
class AlbumIntegrityResult:
    """Result of album-wide integrity check."""
    path: Path
    total_files: int
    verified: int
    failed: int
    skipped: int
    no_md5: int
    errors: int
    results: list[IntegrityResult]

    @property
    def is_ok(self) -> bool:
        """True if no files failed verification."""
        return self.failed == 0 and self.errors == 0

    @property
    def has_warnings(self) -> bool:
        """True if any files have warnings (no_md5, skipped)."""
        return self.no_md5 > 0 or self.skipped > 0


class IntegrityError(Exception):
    """File integrity verification failed."""
    def __init__(self, path: Path, message: str):
        self.path = path
        super().__init__(f"Integrity check failed for {path}: {message}")


class IntegrityService:
    """Service for verifying audio file integrity.

    Supports:
    - FLAC: Uses `flac -t` for stream testing
    - Handles Qobuz files that lack embedded MD5 checksums
    - Non-blocking async verification
    """

    async def verify_flac(self, file_path: Path) -> IntegrityResult:
        """Verify FLAC file integrity using flac -t.

        The `flac -t` command tests:
        1. Frame CRC checks (always present)
        2. MD5 signature verification (if embedded)

        Qobuz FLAC files often lack embedded MD5, which is not an error
        but means only frame CRCs are verified.

        Args:
            file_path: Path to FLAC file

        Returns:
            IntegrityResult with status and details
        """
        if not file_path.exists():
            return IntegrityResult(
                path=file_path,
                status=IntegrityStatus.ERROR,
                format="flac",
                message="File not found"
            )

        if file_path.suffix.lower() != ".flac":
            return IntegrityResult(
                path=file_path,
                status=IntegrityStatus.SKIPPED,
                format=file_path.suffix.lower().lstrip("."),
                message="Not a FLAC file"
            )

        try:
            # Run flac -t (test mode)
            # -s = silent (only errors)
            # -t = test (decode but don't output)
            process = await asyncio.create_subprocess_exec(
                "flac", "-t", "-s", str(file_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            stderr_text = stderr.decode().strip() if stderr else ""

            if process.returncode == 0:
                # Check if MD5 was verified or missing
                # flac outputs warning about missing MD5 to stderr even on success
                has_md5 = "MD5 signature" not in stderr_text or "ok" in stderr_text.lower()

                if "MD5 signature" in stderr_text and "missing" in stderr_text.lower():
                    # Qobuz case: no embedded MD5, but frame CRCs passed
                    return IntegrityResult(
                        path=file_path,
                        status=IntegrityStatus.NO_MD5,
                        format="flac",
                        message="Frame CRCs OK, no embedded MD5 (typical for Qobuz)",
                        has_embedded_md5=False
                    )

                return IntegrityResult(
                    path=file_path,
                    status=IntegrityStatus.OK,
                    format="flac",
                    message="Verified OK",
                    has_embedded_md5=has_md5
                )
            else:
                # Verification failed
                return IntegrityResult(
                    path=file_path,
                    status=IntegrityStatus.FAILED,
                    format="flac",
                    message=stderr_text or f"flac -t returned {process.returncode}"
                )

        except FileNotFoundError:
            # flac command not installed
            logger.warning("flac command not found - install flac for integrity verification")
            return IntegrityResult(
                path=file_path,
                status=IntegrityStatus.ERROR,
                format="flac",
                message="flac command not installed"
            )
        except Exception as e:
            return IntegrityResult(
                path=file_path,
                status=IntegrityStatus.ERROR,
                format="flac",
                message=str(e)
            )

    async def verify_file(self, file_path: Path) -> IntegrityResult:
        """Verify any supported audio file.

        Args:
            file_path: Path to audio file

        Returns:
            IntegrityResult with status and details
        """
        suffix = file_path.suffix.lower()

        if suffix in FLAC_FORMATS:
            return await self.verify_flac(file_path)

        # Formats without built-in integrity checks
        # MP3, AAC, etc. don't have frame CRCs by default
        return IntegrityResult(
            path=file_path,
            status=IntegrityStatus.SKIPPED,
            format=suffix.lstrip("."),
            message=f"Format {suffix} doesn't support integrity verification"
        )

    async def verify_album(
        self,
        album_path: Path,
        fail_fast: bool = False
    ) -> AlbumIntegrityResult:
        """Verify all audio files in an album directory.

        Args:
            album_path: Path to album directory
            fail_fast: If True, stop on first failure

        Returns:
            AlbumIntegrityResult with per-file results
        """
        audio_extensions = {".flac", ".mp3", ".m4a", ".ogg", ".wav", ".aiff", ".alac", ".aac"}

        audio_files = sorted([
            f for f in album_path.iterdir()
            if f.is_file() and f.suffix.lower() in audio_extensions
        ])

        results: list[IntegrityResult] = []
        verified = 0
        failed = 0
        skipped = 0
        no_md5 = 0
        errors = 0

        for audio_file in audio_files:
            result = await self.verify_file(audio_file)
            results.append(result)

            if result.status == IntegrityStatus.OK:
                verified += 1
            elif result.status == IntegrityStatus.FAILED:
                failed += 1
                logger.warning(f"Integrity check FAILED: {audio_file} - {result.message}")
                if fail_fast:
                    break
            elif result.status == IntegrityStatus.SKIPPED:
                skipped += 1
            elif result.status == IntegrityStatus.NO_MD5:
                no_md5 += 1
                # Not an error, just informational
                logger.debug(f"No embedded MD5: {audio_file}")
            elif result.status == IntegrityStatus.ERROR:
                errors += 1
                logger.error(f"Integrity check error: {audio_file} - {result.message}")

        return AlbumIntegrityResult(
            path=album_path,
            total_files=len(audio_files),
            verified=verified,
            failed=failed,
            skipped=skipped,
            no_md5=no_md5,
            errors=errors,
            results=results
        )

    def check_flac_installed(self) -> bool:
        """Check if flac command is available."""
        try:
            result = subprocess.run(
                ["flac", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
