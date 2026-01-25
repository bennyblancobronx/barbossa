"""Tests for Qobuz catalog browsing API endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.api.qobuz import check_albums_in_library


class TestQobuzRoutes:
    """Test Qobuz API endpoints."""

    def test_search_requires_auth(self, client):
        """Search endpoint requires authentication."""
        response = client.get("/api/qobuz/search?q=test&type=album")
        assert response.status_code in [401, 403]

    def test_artist_requires_auth(self, client):
        """Artist endpoint requires authentication."""
        response = client.get("/api/qobuz/artist/12345")
        assert response.status_code in [401, 403]

    def test_album_requires_auth(self, client):
        """Album endpoint requires authentication."""
        response = client.get("/api/qobuz/album/12345")
        assert response.status_code in [401, 403]

    def test_search_validates_type(self, client, auth_token):
        """Search endpoint validates type parameter."""
        response = client.get(
            "/api/qobuz/search?q=test&type=invalid",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 422  # Validation error

    def test_search_requires_query(self, client, auth_token):
        """Search endpoint requires q parameter."""
        response = client.get(
            "/api/qobuz/search?type=album",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 422

    @patch("app.api.qobuz.get_qobuz_api")
    def test_search_albums_success(self, mock_get_api, client, auth_token, db_session):
        """Search albums returns results with in_library flag."""
        mock_api = MagicMock()
        mock_api.search_albums = AsyncMock(return_value=[
            {
                "id": "123",
                "title": "Test Album",
                "artist_id": "456",
                "artist_name": "Test Artist",
                "year": "2024",
                "track_count": 10,
                "duration": 3600,
                "label": "Test Label",
                "genre": "Rock",
                "hires": True,
                "hires_streamable": True,
                "maximum_bit_depth": 24,
                "maximum_sampling_rate": 96.0,
                "artwork_small": "https://example.com/small.jpg",
                "artwork_thumbnail": "https://example.com/thumb.jpg",
                "artwork_large": "https://example.com/large.jpg",
                "artwork_url": "https://example.com/large.jpg",
                "url": "https://www.qobuz.com/us-en/album/123",
            }
        ])
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/search?q=Test&type=album&limit=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Test"
        assert data["type"] == "album"
        assert data["count"] == 1
        assert len(data["albums"]) == 1
        assert data["albums"][0]["title"] == "Test Album"
        assert data["albums"][0]["in_library"] is False

    @patch("app.api.qobuz.get_qobuz_api")
    def test_search_artists_success(self, mock_get_api, client, auth_token):
        """Search artists returns results."""
        mock_api = MagicMock()
        mock_api.search_artists = AsyncMock(return_value=[
            {
                "id": "456",
                "name": "Test Artist",
                "biography": "Test bio",
                "album_count": 5,
                "image_small": "https://example.com/small.jpg",
                "image_medium": "https://example.com/medium.jpg",
                "image_large": "https://example.com/large.jpg",
                "image_url": "https://example.com/medium.jpg",
            }
        ])
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/search?q=Test&type=artist",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "artist"
        assert len(data["artists"]) == 1
        assert data["artists"][0]["name"] == "Test Artist"

    @patch("app.api.qobuz.get_qobuz_api")
    def test_search_tracks_success(self, mock_get_api, client, auth_token):
        """Search tracks returns results."""
        mock_api = MagicMock()
        mock_api.search_tracks = AsyncMock(return_value=[
            {
                "id": "789",
                "title": "Test Track",
                "track_number": 1,
                "disc_number": 1,
                "duration": 240,
                "album_id": "123",
                "album_title": "Test Album",
                "album_artwork": "https://example.com/thumb.jpg",
                "artist_name": "Test Artist",
                "hires": False,
                "maximum_bit_depth": 16,
                "maximum_sampling_rate": 44.1,
                "preview_url": "",
            }
        ])
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/search?q=Test&type=track",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "track"
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["title"] == "Test Track"

    @patch("app.api.qobuz.get_qobuz_api")
    def test_get_artist_success(self, mock_get_api, client, auth_token, db_session):
        """Get artist returns artist with discography."""
        mock_api = MagicMock()
        mock_api.get_artist = AsyncMock(return_value={
            "id": "456",
            "name": "Test Artist",
            "biography": "Test bio",
            "album_count": 2,
            "image_small": "https://example.com/small.jpg",
            "image_medium": "https://example.com/medium.jpg",
            "image_large": "https://example.com/large.jpg",
            "image_url": "https://example.com/medium.jpg",
            "albums": [
                {
                    "id": "123",
                    "title": "Album One",
                    "artist_id": "456",
                    "artist_name": "Test Artist",
                    "year": "2024",
                    "track_count": 10,
                    "duration": 3600,
                    "label": "",
                    "genre": "",
                    "hires": True,
                    "hires_streamable": True,
                    "maximum_bit_depth": 24,
                    "maximum_sampling_rate": 96.0,
                    "artwork_small": "",
                    "artwork_thumbnail": "",
                    "artwork_large": "",
                    "artwork_url": "",
                    "url": "",
                },
                {
                    "id": "124",
                    "title": "Album Two",
                    "artist_id": "456",
                    "artist_name": "Test Artist",
                    "year": "2020",
                    "track_count": 8,
                    "duration": 2800,
                    "label": "",
                    "genre": "",
                    "hires": False,
                    "hires_streamable": False,
                    "maximum_bit_depth": 16,
                    "maximum_sampling_rate": 44.1,
                    "artwork_small": "",
                    "artwork_thumbnail": "",
                    "artwork_large": "",
                    "artwork_url": "",
                    "url": "",
                },
            ]
        })
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/artist/456",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "456"
        assert data["name"] == "Test Artist"
        assert len(data["albums"]) == 2
        # Default sort is year descending
        assert data["albums"][0]["year"] == "2024"

    @patch("app.api.qobuz.get_qobuz_api")
    def test_get_artist_sort_by_title(self, mock_get_api, client, auth_token, db_session):
        """Get artist sorts by title when requested."""
        mock_api = MagicMock()
        mock_api.get_artist = AsyncMock(return_value={
            "id": "456",
            "name": "Test Artist",
            "biography": "",
            "album_count": 2,
            "image_small": "",
            "image_medium": "",
            "image_large": "",
            "image_url": "",
            "albums": [
                {
                    "id": "123",
                    "title": "Zebra Album",
                    "artist_id": "456",
                    "artist_name": "Test Artist",
                    "year": "2024",
                    "track_count": 10,
                    "duration": 3600,
                    "label": "",
                    "genre": "",
                    "hires": False,
                    "hires_streamable": False,
                    "maximum_bit_depth": 16,
                    "maximum_sampling_rate": 44.1,
                    "artwork_small": "",
                    "artwork_thumbnail": "",
                    "artwork_large": "",
                    "artwork_url": "",
                    "url": "",
                },
                {
                    "id": "124",
                    "title": "Alpha Album",
                    "artist_id": "456",
                    "artist_name": "Test Artist",
                    "year": "2020",
                    "track_count": 8,
                    "duration": 2800,
                    "label": "",
                    "genre": "",
                    "hires": False,
                    "hires_streamable": False,
                    "maximum_bit_depth": 16,
                    "maximum_sampling_rate": 44.1,
                    "artwork_small": "",
                    "artwork_thumbnail": "",
                    "artwork_large": "",
                    "artwork_url": "",
                    "url": "",
                },
            ]
        })
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/artist/456?sort=title",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        # Title sort is ascending
        assert data["albums"][0]["title"] == "Alpha Album"

    @patch("app.api.qobuz.get_qobuz_api")
    def test_get_album_success(self, mock_get_api, client, auth_token, db_session):
        """Get album returns album with tracks."""
        mock_api = MagicMock()
        mock_api.get_album = AsyncMock(return_value={
            "id": "123",
            "title": "Test Album",
            "artist_id": "456",
            "artist_name": "Test Artist",
            "year": "2024",
            "track_count": 2,
            "duration": 480,
            "label": "Test Label",
            "genre": "Rock",
            "hires": True,
            "hires_streamable": True,
            "maximum_bit_depth": 24,
            "maximum_sampling_rate": 96.0,
            "artwork_small": "https://example.com/small.jpg",
            "artwork_thumbnail": "https://example.com/thumb.jpg",
            "artwork_large": "https://example.com/large.jpg",
            "artwork_url": "https://example.com/large.jpg",
            "url": "https://www.qobuz.com/us-en/album/123",
            "tracks": [
                {
                    "id": "789",
                    "title": "Track One",
                    "track_number": 1,
                    "disc_number": 1,
                    "duration": 240,
                    "album_id": "123",
                    "album_title": "Test Album",
                    "album_artwork": "",
                    "artist_name": "Test Artist",
                    "hires": True,
                    "maximum_bit_depth": 24,
                    "maximum_sampling_rate": 96.0,
                    "preview_url": "",
                },
                {
                    "id": "790",
                    "title": "Track Two",
                    "track_number": 2,
                    "disc_number": 1,
                    "duration": 240,
                    "album_id": "123",
                    "album_title": "Test Album",
                    "album_artwork": "",
                    "artist_name": "Test Artist",
                    "hires": True,
                    "maximum_bit_depth": 24,
                    "maximum_sampling_rate": 96.0,
                    "preview_url": "",
                },
            ]
        })
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/album/123",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "123"
        assert data["title"] == "Test Album"
        assert data["in_library"] is False
        assert len(data["tracks"]) == 2
        assert data["tracks"][0]["title"] == "Track One"

    @patch("app.api.qobuz.get_qobuz_api")
    def test_api_error_returns_502(self, mock_get_api, client, auth_token):
        """Qobuz API errors return 502."""
        from app.integrations.qobuz_api import QobuzAPIError

        mock_api = MagicMock()
        mock_api.search_albums = AsyncMock(side_effect=QobuzAPIError("Connection failed"))
        mock_get_api.return_value = mock_api

        response = client.get(
            "/api/qobuz/search?q=test&type=album",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        assert response.status_code == 502
        assert "Connection failed" in response.json()["detail"]


class TestCheckAlbumsInLibrary:
    """Test the check_albums_in_library helper function."""

    def test_marks_album_in_library(self, db_session, test_artist, test_album):
        """Album matching local library is marked as in_library."""
        albums = [
            {
                "id": "123",
                "title": test_album.title,
                "artist_name": test_artist.name,
            }
        ]

        result = check_albums_in_library(db_session, albums)

        assert result[0]["in_library"] is True
        assert result[0]["local_album_id"] == test_album.id

    def test_album_not_in_library(self, db_session):
        """Album not in local library is marked correctly."""
        albums = [
            {
                "id": "999",
                "title": "Unknown Album",
                "artist_name": "Unknown Artist",
            }
        ]

        result = check_albums_in_library(db_session, albums)

        assert result[0]["in_library"] is False
        assert result[0]["local_album_id"] is None

    def test_normalized_matching(self, db_session, test_artist, test_album):
        """Matching ignores case, parenthetical content, etc."""
        albums = [
            {
                "id": "123",
                # Different case, extra content in parens
                "title": test_album.title.upper() + " (Deluxe Edition)",
                "artist_name": test_artist.name.lower(),
            }
        ]

        result = check_albums_in_library(db_session, albums)

        # Should still match due to normalization
        assert result[0]["in_library"] is True
