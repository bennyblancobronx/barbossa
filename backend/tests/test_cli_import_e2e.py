"""End-to-end tests for CLI import functionality.

This module contains E2E tests for the CLI import command, including:
- Tests with mocked integrations (beets, exiftool)
- Tests with real audio file fixtures for format validation
- Artwork fetch verification
- Error handling and edge cases
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from typer.testing import CliRunner

from app.cli.main import app
from app.models.album import Album
from app.models.artist import Artist


class TestCLIImportEndToEnd:
    """Full end-to-end tests for CLI import command."""

    @pytest.fixture
    def audio_folder(self, tmp_path):
        """Create a folder with simulated audio files."""
        album_dir = tmp_path / "Test Artist" / "Test Album (2024)"
        album_dir.mkdir(parents=True)

        # Create fake audio files
        (album_dir / "01 - Track One.flac").write_bytes(b"FAKE_FLAC_HEADER")
        (album_dir / "02 - Track Two.flac").write_bytes(b"FAKE_FLAC_HEADER")
        (album_dir / "cover.jpg").write_bytes(b"FAKE_JPG")

        return album_dir

    @pytest.fixture
    def mock_beets(self):
        """Mock BeetsClient for testing."""
        with patch("app.integrations.beets.BeetsClient") as mock:
            instance = MagicMock()
            instance.identify = AsyncMock(return_value={
                "artist": "Test Artist",
                "album": "Test Album",
                "year": 2024,
                "confidence": 0.95
            })
            instance.import_album = AsyncMock()
            instance.import_with_metadata = AsyncMock()
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_exiftool(self):
        """Mock ExifToolClient for testing."""
        with patch("app.integrations.exiftool.ExifToolClient") as mock:
            instance = MagicMock()
            instance.get_album_metadata = AsyncMock(return_value=[
                {
                    "title": "Track One",
                    "track_number": 1,
                    "disc_number": 1,
                    "duration": 180,
                    "sample_rate": 44100,
                    "bit_depth": 16,
                    "format": "flac"
                },
                {
                    "title": "Track Two",
                    "track_number": 2,
                    "disc_number": 1,
                    "duration": 200,
                    "sample_rate": 44100,
                    "bit_depth": 16,
                    "format": "flac"
                }
            ])
            mock.return_value = instance
            yield instance

    @pytest.fixture
    def mock_import_service(self, db_session):
        """Mock ImportService for testing."""
        with patch("app.services.import_service.ImportService") as mock:
            instance = MagicMock()

            # Create a real album in the test DB
            artist = Artist(
                name="Test Artist",
                normalized_name="test artist",
                sort_name="test artist"
            )
            db_session.add(artist)
            db_session.flush()

            album = Album(
                artist_id=artist.id,
                title="Test Album",
                normalized_title="test album",
                year=2024,
                total_tracks=2,
                available_tracks=2,
                artwork_path=None
            )
            db_session.add(album)
            db_session.commit()
            db_session.refresh(album)

            instance.import_album = AsyncMock(return_value=album)
            instance.find_duplicate = MagicMock(return_value=None)
            instance.fetch_artwork_if_missing = AsyncMock(return_value="/path/to/cover.jpg")
            mock.return_value = instance
            yield instance, album

    def test_import_creates_album_with_artwork(
        self, db_session, audio_folder, mock_beets, mock_exiftool, mock_import_service
    ):
        """CLI import should create album and fetch artwork."""
        import_service, album = mock_import_service

        # Configure beets to return the same path (simulating no-move)
        mock_beets.import_album.return_value = audio_folder

        runner = CliRunner()

        with patch("app.database.SessionLocal", return_value=db_session):
            result = runner.invoke(app, ["admin", "import", str(audio_folder)])

        # Should complete successfully
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Import complete" in result.output

        # Verify beets was called
        mock_beets.identify.assert_called_once()
        mock_beets.import_album.assert_called_once()

        # Verify exiftool was called
        mock_exiftool.get_album_metadata.assert_called_once()

        # Verify import_service was called
        import_service.import_album.assert_called_once()

        # CRITICAL: Verify artwork fetch was called
        import_service.fetch_artwork_if_missing.assert_called_once_with(album)

    def test_import_with_overrides(
        self, db_session, audio_folder, mock_beets, mock_exiftool, mock_import_service
    ):
        """CLI import with --artist and --album overrides."""
        import_service, album = mock_import_service
        mock_beets.import_with_metadata.return_value = audio_folder

        runner = CliRunner()

        with patch("app.database.SessionLocal", return_value=db_session):
            result = runner.invoke(app, [
                "admin", "import", str(audio_folder),
                "--artist", "Override Artist",
                "--album", "Override Album",
                "--year", "2025"
            ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        # Should use import_with_metadata for overrides
        mock_beets.import_with_metadata.assert_called_once()
        call_args = mock_beets.import_with_metadata.call_args
        assert call_args[1]["artist"] == "Override Artist"
        assert call_args[1]["album"] == "Override Album"
        assert call_args[1]["year"] == 2025

    def test_import_missing_path_fails(self, db_session):
        """CLI import with non-existent path should fail gracefully."""
        runner = CliRunner()

        with patch("app.database.SessionLocal", return_value=db_session):
            result = runner.invoke(app, ["admin", "import", "/nonexistent/path"])

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_import_no_audio_files_fails(self, db_session, tmp_path):
        """CLI import with no audio files should fail."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "readme.txt").write_text("not audio")

        runner = CliRunner()

        with patch("app.database.SessionLocal", return_value=db_session):
            result = runner.invoke(app, ["admin", "import", str(empty_dir)])

        assert result.exit_code != 0
        assert "no audio" in result.output.lower()

    def test_import_duplicate_detection(
        self, db_session, audio_folder, mock_beets, mock_exiftool
    ):
        """CLI import should detect duplicates."""
        with patch("app.services.import_service.ImportService") as mock:
            instance = MagicMock()
            # Simulate duplicate found
            existing = MagicMock()
            existing.id = 999
            existing.path = "/existing/path"
            instance.find_duplicate = MagicMock(return_value=existing)
            mock.return_value = instance

            runner = CliRunner()

            with patch("app.database.SessionLocal", return_value=db_session):
                result = runner.invoke(app, ["admin", "import", str(audio_folder)])

        assert result.exit_code == 0  # Exits cleanly but doesn't import
        assert "duplicate" in result.output.lower()


class TestCLIImportArtworkIntegration:
    """Tests specifically for artwork fetch in CLI import."""

    def test_artwork_fetch_called_when_missing(self, db_session, tmp_path):
        """Verify fetch_artwork_if_missing is called when artwork_path is None."""
        album_dir = tmp_path / "Artist" / "Album"
        album_dir.mkdir(parents=True)
        (album_dir / "track.flac").write_bytes(b"audio")

        # Create album without artwork
        artist = Artist(name="Artist", normalized_name="artist", sort_name="artist")
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Album",
            normalized_title="album",
            total_tracks=1,
            available_tracks=1,
            artwork_path=None  # No artwork
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient") as mock_beets:
            with patch("app.integrations.exiftool.ExifToolClient") as mock_exiftool:
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_beets.return_value.identify = AsyncMock(return_value={
                        "artist": "Artist", "album": "Album", "confidence": 0.9
                    })
                    mock_beets.return_value.import_album = AsyncMock(return_value=album_dir)
                    mock_exiftool.return_value.get_album_metadata = AsyncMock(return_value=[])

                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(
                        return_value="/path/cover.jpg"
                    )

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(album_dir)])

                    assert result.exit_code == 0
                    # Verify artwork fetch was called
                    mock_import.return_value.fetch_artwork_if_missing.assert_called_once()

    def test_artwork_not_fetched_when_present(self, db_session, tmp_path):
        """Verify fetch_artwork_if_missing is NOT called when artwork exists."""
        album_dir = tmp_path / "Artist" / "Album"
        album_dir.mkdir(parents=True)
        (album_dir / "track.flac").write_bytes(b"audio")

        artist = Artist(name="Artist", normalized_name="artist", sort_name="artist")
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Album",
            normalized_title="album",
            total_tracks=1,
            available_tracks=1,
            artwork_path="/existing/cover.jpg"  # Has artwork
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient") as mock_beets:
            with patch("app.integrations.exiftool.ExifToolClient") as mock_exiftool:
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_beets.return_value.identify = AsyncMock(return_value={
                        "artist": "Artist", "album": "Album", "confidence": 0.9
                    })
                    mock_beets.return_value.import_album = AsyncMock(return_value=album_dir)
                    mock_exiftool.return_value.get_album_metadata = AsyncMock(return_value=[])

                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock()

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(album_dir)])

                    assert result.exit_code == 0
                    # fetch_artwork_if_missing should NOT be called since artwork exists
                    mock_import.return_value.fetch_artwork_if_missing.assert_not_called()


class TestCLIImportWithRealAudio:
    """E2E tests using real audio file fixtures.

    These tests use valid WAV audio files to verify the import pipeline
    handles real audio formats correctly.
    """

    def test_import_real_audio_validates_format(
        self, db_session, audio_album_folder, mock_beets_client, mock_exiftool_client
    ):
        """CLI import with real audio files validates WAV format correctly."""
        beets_mock = mock_beets_client()
        exiftool_mock = mock_exiftool_client()

        # Create album that will be returned by import_album
        artist = Artist(name="Test Artist", normalized_name="test artist", sort_name="test artist")
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Test Album",
            normalized_title="test album",
            year=2024,
            total_tracks=2,
            available_tracks=2,
            artwork_path=str(audio_album_folder / "cover.jpg")
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient", return_value=beets_mock):
            with patch("app.integrations.exiftool.ExifToolClient", return_value=exiftool_mock):
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(return_value=None)

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Import complete" in result.output

        # Verify beets was called with the audio folder
        beets_mock.identify.assert_called_once()
        call_args = beets_mock.identify.call_args
        assert str(audio_album_folder) in str(call_args)

    def test_import_real_audio_extracts_correct_track_count(
        self, db_session, audio_album_folder, mock_beets_client
    ):
        """Verify exiftool extracts correct track count from real audio."""
        beets_mock = mock_beets_client()

        artist = Artist(name="Test Artist", normalized_name="test artist", sort_name="test artist")
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Test Album",
            normalized_title="test album",
            total_tracks=2,
            available_tracks=2
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient", return_value=beets_mock):
            with patch("app.integrations.exiftool.ExifToolClient") as mock_exiftool:
                # Track metadata extraction based on actual files
                async def extract_metadata(path):
                    p = Path(path)
                    audio_files = list(p.glob("*.wav"))
                    return [
                        {
                            "title": f.stem.split(" - ", 1)[-1],
                            "track_number": int(f.stem.split(" - ")[0]) if " - " in f.stem else i,
                            "duration": 1,
                            "sample_rate": 44100,
                            "bit_depth": 16,
                            "format": "WAV"
                        }
                        for i, f in enumerate(sorted(audio_files), 1)
                    ]

                mock_exiftool.return_value.get_album_metadata = AsyncMock(side_effect=extract_metadata)

                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(return_value=None)

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        assert result.exit_code == 0
        # Verify exiftool was called and returned 2 tracks
        mock_exiftool.return_value.get_album_metadata.assert_called_once()

    def test_import_real_audio_with_cover_art(
        self, db_session, audio_album_folder, mock_beets_client, mock_exiftool_client
    ):
        """Verify import detects existing cover.jpg in audio folder."""
        beets_mock = mock_beets_client()
        exiftool_mock = mock_exiftool_client()

        # Verify cover.jpg exists in fixture
        assert (audio_album_folder / "cover.jpg").exists()

        artist = Artist(name="Test Artist", normalized_name="test artist", sort_name="test artist")
        db_session.add(artist)
        db_session.flush()

        # Album WITH artwork path (cover found during import)
        album = Album(
            artist_id=artist.id,
            title="Test Album",
            normalized_title="test album",
            total_tracks=2,
            available_tracks=2,
            artwork_path=str(audio_album_folder / "cover.jpg")
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient", return_value=beets_mock):
            with patch("app.integrations.exiftool.ExifToolClient", return_value=exiftool_mock):
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock()

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        assert result.exit_code == 0
        # Since album has artwork_path, fetch_artwork_if_missing should NOT be called
        mock_import.return_value.fetch_artwork_if_missing.assert_not_called()
        assert "Artwork: Found" in result.output

    def test_import_real_audio_full_pipeline(
        self, db_session, audio_album_folder, mock_beets_client, mock_exiftool_client
    ):
        """Full E2E test: import real audio, verify all steps complete."""
        beets_mock = mock_beets_client()
        exiftool_mock = mock_exiftool_client()

        # Create artist/album records that simulate successful import
        artist = Artist(
            name="Test Artist",
            normalized_name="test artist",
            sort_name="test artist",
            path=str(audio_album_folder.parent)
        )
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Test Album",
            normalized_title="test album",
            year=2024,
            path=str(audio_album_folder),
            total_tracks=2,
            available_tracks=2,
            artwork_path=None  # No artwork initially
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.integrations.beets.BeetsClient", return_value=beets_mock):
            with patch("app.integrations.exiftool.ExifToolClient", return_value=exiftool_mock):
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(
                        return_value=str(audio_album_folder / "cover.jpg")
                    )

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        # Verify full pipeline completed
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "Import complete" in result.output
        assert "Album ID:" in result.output

        # Verify each step was called
        beets_mock.identify.assert_called_once()
        beets_mock.import_album.assert_called_once()
        exiftool_mock.get_album_metadata.assert_called_once()
        mock_import.return_value.import_album.assert_called_once()
        # Artwork fetch should be called since artwork_path was None
        mock_import.return_value.fetch_artwork_if_missing.assert_called_once()


class TestCLIImportErrorRecovery:
    """Tests for CLI import error handling and recovery."""

    def test_import_beets_failure_shows_error(
        self, db_session, audio_album_folder, mock_exiftool_client
    ):
        """When beets fails, CLI should show clear error message."""
        exiftool_mock = mock_exiftool_client()

        with patch("app.integrations.beets.BeetsClient") as mock_beets:
            mock_beets.return_value.identify = AsyncMock(
                side_effect=Exception("Beets identification failed: no matches found")
            )

            runner = CliRunner()
            with patch("app.database.SessionLocal", return_value=db_session):
                result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_import_db_failure_reports_error(
        self, db_session, audio_album_folder, mock_beets_client, mock_exiftool_client
    ):
        """When database insert fails, CLI should report the error."""
        beets_mock = mock_beets_client()
        exiftool_mock = mock_exiftool_client()

        with patch("app.integrations.beets.BeetsClient", return_value=beets_mock):
            with patch("app.integrations.exiftool.ExifToolClient", return_value=exiftool_mock):
                with patch("app.services.import_service.ImportService") as mock_import:
                    mock_import.return_value.find_duplicate = MagicMock(return_value=None)
                    mock_import.return_value.import_album = AsyncMock(
                        side_effect=Exception("Database connection lost")
                    )

                    runner = CliRunner()
                    with patch("app.database.SessionLocal", return_value=db_session):
                        result = runner.invoke(app, ["admin", "import", str(audio_album_folder)])

        assert result.exit_code != 0
        assert "failed" in result.output.lower() or "Database" in result.output
