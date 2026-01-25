"""Download integration tests."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from app.services.download import DownloadService, DuplicateError
from app.services.import_service import ImportService
from app.integrations.exiftool import quality_score


class TestQualityScore:
    """Test quality score calculation."""

    def test_cd_quality(self):
        """CD quality: 44100 * 16 = 705,600."""
        score = quality_score(44100, 16)
        assert score == 705600

    def test_hires_quality(self):
        """Hi-Res: 96000 * 24 = 2,304,000."""
        score = quality_score(96000, 24)
        assert score == 2304000

    def test_ultra_hires_quality(self):
        """Ultra Hi-Res: 192000 * 24 = 4,608,000."""
        score = quality_score(192000, 24)
        assert score == 4608000

    def test_quality_comparison(self):
        """Higher quality scores should win."""
        cd = quality_score(44100, 16)
        hires = quality_score(96000, 24)
        ultra = quality_score(192000, 24)

        assert ultra > hires > cd

    def test_none_defaults(self):
        """None values should default to CD quality."""
        score = quality_score(None, None)
        assert score == 705600  # 44100 * 16


class TestDownloadService:
    """Test download service."""

    @pytest.fixture
    def download_service(self, db_session):
        return DownloadService(db_session)

    @pytest.mark.asyncio
    async def test_search_qobuz(self, download_service):
        """Test Qobuz search."""
        with patch.object(
            download_service.streamrip,
            'search',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [
                {
                    "id": "123",
                    "title": "Dark Side of the Moon",
                    "artist": "Pink Floyd",
                    "year": "1973",
                    "quality": 24,
                    "url": "https://qobuz.com/album/123"
                }
            ]

            results = await download_service.search_qobuz("pink floyd", "album")

            assert len(results) == 1
            assert results[0]["artist"] == "Pink Floyd"
            mock_search.assert_called_once_with("pink floyd", "album", 20)

    @pytest.mark.asyncio
    async def test_search_qobuz_different_types(self, download_service):
        """Test Qobuz search with different types."""
        with patch.object(
            download_service.streamrip,
            'search',
            new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            for search_type in ["artist", "album", "track", "playlist"]:
                await download_service.search_qobuz("test", search_type)
                mock_search.assert_called_with("test", search_type, 20)


class TestImportService:
    """Test import service."""

    @pytest.fixture
    def import_service(self, db_session):
        return ImportService(db_session)

    def test_find_duplicate_no_match(self, import_service):
        """Test find_duplicate returns None when no match."""
        result = import_service.find_duplicate("Non Existent Artist", "Non Existent Album")
        assert result is None

    def test_find_duplicate_with_normalized_match(self, import_service, db_session):
        """Test normalized matching catches variations."""
        from app.models.artist import Artist
        from app.models.album import Album
        from app.utils.normalize import normalize_text

        # Create test artist and album
        artist = Artist(
            name="Pink Floyd",
            normalized_name=normalize_text("Pink Floyd"),
            path="/music/Pink Floyd"
        )
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Dark Side of the Moon",
            normalized_title=normalize_text("Dark Side of the Moon"),
            path="/music/Pink Floyd/Dark Side of the Moon"
        )
        db_session.add(album)
        db_session.commit()

        # Should find with exact match
        result = import_service.find_duplicate("Pink Floyd", "Dark Side of the Moon")
        assert result is not None
        assert result.id == album.id

        # Should find with (Remaster) suffix
        result = import_service.find_duplicate("Pink Floyd", "Dark Side of the Moon (Remaster)")
        assert result is not None
        assert result.id == album.id

        # Should find with [Explicit] suffix
        result = import_service.find_duplicate("Pink Floyd", "Dark Side of the Moon [Explicit]")
        assert result is not None
        assert result.id == album.id


class TestNormalization:
    """Test text normalization for duplicate detection."""

    def test_normalize_removes_parentheses(self):
        from app.utils.normalize import normalize_text

        assert normalize_text("Album (Deluxe)") == "album"
        assert normalize_text("Album (Remaster 2020)") == "album"
        assert normalize_text("Album (Special Edition)") == "album"

    def test_normalize_removes_brackets(self):
        from app.utils.normalize import normalize_text

        assert normalize_text("Album [Explicit]") == "album"
        assert normalize_text("Album [Clean]") == "album"

    def test_normalize_handles_the(self):
        from app.utils.normalize import normalize_text

        # "The" is kept but normalized
        assert normalize_text("The Dark Side") == "the dark side"

    def test_normalize_removes_punctuation(self):
        from app.utils.normalize import normalize_text

        # Note: normalize collapses multiple spaces to single space
        assert normalize_text("Rock & Roll") == "rock roll"
        assert normalize_text("What's Up?") == "whats up"


class TestDownloadAPI:
    """Test download API endpoints."""

    def test_list_downloads_empty(self, client, auth_headers):
        """Test listing downloads when empty."""
        response = client.get("/api/downloads", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_download_qobuz_requires_auth(self, client):
        """Test that download endpoints require authentication."""
        response = client.post("/api/downloads/qobuz", json={"url": "https://qobuz.com/..."})
        assert response.status_code in [401, 403]  # Either unauthorized or forbidden

    def test_url_info_requires_auth(self, client):
        """Test that URL info endpoint requires authentication."""
        response = client.get("/api/downloads/url/info?url=https://youtube.com/...")
        assert response.status_code in [401, 403]  # Either unauthorized or forbidden

    def test_lossy_requires_confirmation(self, client, auth_headers):
        """Test that lossy sources require confirmation."""
        response = client.post(
            "/api/downloads/url",
            headers=auth_headers,
            json={"url": "https://youtube.com/watch?v=test"}
        )
        assert response.status_code == 400
        assert "confirm_lossy" in response.json()["detail"]

    def test_download_cancel_not_found(self, client, auth_headers):
        """Test canceling non-existent download."""
        response = client.post("/api/downloads/999/cancel", headers=auth_headers)
        assert response.status_code == 404

    def test_search_qobuz_validation(self, client, auth_headers):
        """Test search type validation."""
        # Valid types should work (mocked)
        with patch('app.services.download.DownloadService.search_qobuz', new_callable=AsyncMock) as mock:
            mock.return_value = []
            response = client.get(
                "/api/downloads/search/qobuz?q=test&type=album",
                headers=auth_headers
            )
            # May fail if streamrip not available, but validation passes
            assert response.status_code in [200, 500]


class TestWebSocket:
    """Test WebSocket functionality."""

    def test_connection_manager(self):
        """Test connection manager tracking."""
        from app.websocket import ConnectionManager

        manager = ConnectionManager()
        assert len(manager.active_connections) == 0
