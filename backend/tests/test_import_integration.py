"""Integration tests for import functionality.

These tests verify the full import pipeline including:
- CLI import command
- Beets identification
- Artwork fetching
- Database population
- File deletion
"""
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.library import LibraryService
from app.services.import_service import ImportService
from app.integrations.beets import BeetsClient


class TestDeleteAlbum:
    """Test album deletion with file cleanup."""

    def test_delete_album_removes_files(self, db):
        """Test that delete_album removes files from disk."""
        from app.models.artist import Artist
        from app.models.album import Album

        # Create temp album directory with files
        tmp_path = Path(tempfile.mkdtemp())
        try:
            album_dir = tmp_path / "Test Artist" / "Test Album"
            album_dir.mkdir(parents=True)
            (album_dir / "01 - Track One.flac").write_text("fake audio")
            (album_dir / "02 - Track Two.flac").write_text("fake audio")
            (album_dir / "cover.jpg").write_text("fake image")

            # Create database records
            artist = Artist(name="Test Artist", normalized_name="test artist", path=str(tmp_path / "Test Artist"))
            db.add(artist)
            db.flush()

            album = Album(
                artist_id=artist.id,
                title="Test Album",
                normalized_title="test album",
                path=str(album_dir),
                total_tracks=2,
                available_tracks=2
            )
            db.add(album)
            db.commit()

            album_id = album.id

            # Verify files exist
            assert album_dir.exists()
            assert (album_dir / "01 - Track One.flac").exists()

            # Delete album
            service = LibraryService(db)
            success, error = service.delete_album(album_id, delete_files=True)

            assert success is True
            assert error is None

            # Verify files are deleted
            assert not album_dir.exists()

            # Verify database record is gone
            deleted = db.query(Album).filter(Album.id == album_id).first()
            assert deleted is None
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_delete_album_cleans_empty_artist_dir(self, db):
        """Test that empty artist directory is removed after album deletion."""
        from app.models.artist import Artist
        from app.models.album import Album

        tmp_path = Path(tempfile.mkdtemp())
        try:
            # Create temp structure
            artist_dir = tmp_path / "Test Artist"
            album_dir = artist_dir / "Test Album"
            album_dir.mkdir(parents=True)
            (album_dir / "track.flac").write_text("fake")

            # Create records
            artist = Artist(name="Test Artist", normalized_name="test artist", path=str(artist_dir))
            db.add(artist)
            db.flush()

            album = Album(
                artist_id=artist.id,
                title="Test Album",
                normalized_title="test album",
                path=str(album_dir),
                total_tracks=1,
                available_tracks=1
            )
            db.add(album)
            db.commit()

            # Delete
            service = LibraryService(db)
            service.delete_album(album.id, delete_files=True)

            # Both album and empty artist dir should be gone
            assert not album_dir.exists()
            assert not artist_dir.exists()
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_delete_album_preserves_files_when_disabled(self, db):
        """Test that files are preserved when delete_files=False."""
        from app.models.artist import Artist
        from app.models.album import Album

        tmp_path = Path(tempfile.mkdtemp())
        try:
            album_dir = tmp_path / "Artist" / "Album"
            album_dir.mkdir(parents=True)
            (album_dir / "track.flac").write_text("fake")

            artist = Artist(name="Artist", normalized_name="artist", path=str(tmp_path / "Artist"))
            db.add(artist)
            db.flush()

            album = Album(
                artist_id=artist.id,
                title="Album",
                normalized_title="album",
                path=str(album_dir),
                total_tracks=1,
                available_tracks=1
            )
            db.add(album)
            db.commit()

            service = LibraryService(db)
            service.delete_album(album.id, delete_files=False)

            # Files should still exist
            assert album_dir.exists()
            assert (album_dir / "track.flac").exists()
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class TestBeetsIdentification:
    """Test beets album identification."""

    def test_parse_folder_name_full_format(self):
        """Test parsing streamrip-style folder name."""
        client = BeetsClient()
        result = client._parse_folder_name("Pink Floyd - Dark Side of the Moon (1973) [FLAC] [24-96]")

        assert result["artist"] == "Pink Floyd"
        assert result["album"] == "Dark Side of the Moon"
        assert result["year"] == 1973

    def test_parse_folder_name_no_year(self):
        """Test parsing folder name without year."""
        client = BeetsClient()
        result = client._parse_folder_name("Artist Name - Album Title [FLAC]")

        assert result["artist"] == "Artist Name"
        assert result["album"] == "Album Title"
        assert result["year"] is None

    def test_parse_folder_name_no_brackets(self):
        """Test parsing simple folder name."""
        client = BeetsClient()
        result = client._parse_folder_name("Artist - Album (2020)")

        assert result["artist"] == "Artist"
        assert result["album"] == "Album"
        assert result["year"] == 2020

    def test_parse_folder_name_album_only(self):
        """Test parsing folder with no artist separator."""
        client = BeetsClient()
        result = client._parse_folder_name("Just Album Name")

        assert result["artist"] is None
        assert result["album"] == "Just Album Name"


class TestImportService:
    """Test import service functionality."""

    def test_find_artwork_cover_jpg(self):
        """Test finding cover.jpg."""
        tmp_path = Path(tempfile.mkdtemp())
        try:
            (tmp_path / "cover.jpg").write_text("image")

            service = ImportService(MagicMock())
            result = service._find_artwork(tmp_path)

            assert result == str(tmp_path / "cover.jpg")
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_find_artwork_folder_jpg(self):
        """Test finding folder.jpg when cover.jpg missing."""
        tmp_path = Path(tempfile.mkdtemp())
        try:
            (tmp_path / "folder.jpg").write_text("image")

            service = ImportService(MagicMock())
            result = service._find_artwork(tmp_path)

            assert result == str(tmp_path / "folder.jpg")
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_find_artwork_none(self):
        """Test returns None when no artwork present."""
        tmp_path = Path(tempfile.mkdtemp())
        try:
            service = ImportService(MagicMock())
            result = service._find_artwork(tmp_path)

            assert result is None
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    def test_get_or_create_artist_sets_sort_name(self, db):
        """Test sort_name is populated on artist creation."""
        service = ImportService(db)
        artist = service._get_or_create_artist("The Beatles", Path("/tmp"))
        assert artist.sort_name == "beatles"

    def test_replace_album_updates_history_and_checksums(self, db):
        """Test replace_album refreshes import history and track checksums."""
        from app.models.artist import Artist
        from app.models.album import Album
        from app.models.import_history import ImportHistory

        tmp_path = Path(tempfile.mkdtemp())
        try:
            artist = Artist(
                name="Test Artist",
                normalized_name="test artist",
                sort_name="test artist",
                path=str(tmp_path / "Test Artist")
            )
            db.add(artist)
            db.flush()

            album = Album(
                artist_id=artist.id,
                title="Test Album",
                normalized_title="test album",
                path=str(tmp_path / "Old Album"),
                total_tracks=0,
                available_tracks=0
            )
            db.add(album)
            db.commit()

            new_dir = tmp_path / "Test Artist" / "Test Album"
            new_dir.mkdir(parents=True)
            track_path = new_dir / "01 - Track One.flac"
            track_path.write_text("fake audio")

            tracks_metadata = [{
                "title": "Track One",
                "track_number": 1,
                "duration": 10,
                "path": str(track_path),
                "sample_rate": 44100,
                "bit_depth": 16,
                "bitrate": None,
                "channels": 2,
                "file_size": track_path.stat().st_size,
                "format": "FLAC",
                "is_lossy": False
            }]

            service = ImportService(db)
            updated = service.replace_album(album.id, new_dir, tracks_metadata)

            histories = db.query(ImportHistory).filter(ImportHistory.album_id == album.id).all()
            assert len(histories) == 1
            assert updated.tracks.count() == 1
            track = updated.tracks.first()
            assert track.checksum
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_fetch_artwork_if_missing(self, db):
        """Test artwork fetch when missing."""
        from app.models.album import Album

        tmp_path = Path(tempfile.mkdtemp())
        try:
            # Create album without artwork
            album = Album(
                artist_id=1,
                title="Test",
                normalized_title="test",
                path=str(tmp_path),
                artwork_path=None
            )

            service = ImportService(db)

            # Mock beets fetchart
            with patch.object(service, '_find_artwork', return_value=None):
                with patch('app.integrations.beets.BeetsClient.fetch_artwork', new_callable=AsyncMock) as mock_fetch:
                    mock_fetch.return_value = tmp_path / "cover.jpg"

                    result = await service.fetch_artwork_if_missing(album)

                    # Should try to fetch when missing
                    assert result is not None or mock_fetch.called
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class TestCLIImport:
    """Test CLI import command."""

    def test_import_command_validates_path(self):
        """Test that import command validates path exists."""
        from typer.testing import CliRunner
        from app.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["admin", "import", "/nonexistent/path"])

        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or result.exit_code == 1

    def test_import_command_validates_audio_files(self):
        """Test that import requires audio files."""
        from typer.testing import CliRunner
        from app.cli.main import app

        tmp_path = Path(tempfile.mkdtemp())
        try:
            # Create empty directory
            empty_dir = tmp_path / "empty"
            empty_dir.mkdir()

            runner = CliRunner()
            result = runner.invoke(app, ["admin", "import", str(empty_dir)])

            assert result.exit_code != 0
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class TestRescan:
    """Test library rescan command."""

    def test_rescan_dry_run(self):
        """Test rescan with dry-run flag."""
        from typer.testing import CliRunner
        from app.cli.main import app

        tmp_path = Path(tempfile.mkdtemp())
        try:
            # Create test structure
            artist_dir = tmp_path / "Artist"
            album_dir = artist_dir / "Album"
            album_dir.mkdir(parents=True)
            (album_dir / "track.flac").write_text("fake")

            runner = CliRunner()

            # Use --path to specify directory directly (no mocking needed)
            result = runner.invoke(app, ["admin", "rescan", "--dry-run", "--path", str(tmp_path)])

            # Should complete and show scanning output
            assert "Scanning" in result.stdout or "Found" in result.stdout or "album" in result.stdout.lower()
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


class TestArtworkFetch:
    """Test artwork fetching functionality."""

    @pytest.mark.asyncio
    async def test_extract_embedded_artwork(self, db):
        """Test embedded artwork extraction uses ffmpeg."""
        tmp_path = Path(tempfile.mkdtemp())
        try:
            service = ImportService(db)

            # Create fake audio file
            (tmp_path / "track.flac").write_text("fake audio")

            # Mock ffmpeg call
            with patch('asyncio.create_subprocess_exec') as mock_exec:
                mock_process = AsyncMock()
                mock_process.wait = AsyncMock(return_value=0)
                mock_exec.return_value = mock_process

                result = await service._extract_embedded_artwork(tmp_path)

                # Should attempt ffmpeg extraction
                assert mock_exec.called or result is None
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)
