"""Tests for unified search endpoint."""
import pytest
from unittest.mock import patch, MagicMock


class TestUnifiedSearch:
    """Tests for /api/search/unified endpoint."""

    def test_search_requires_auth(self, client):
        """Unauthenticated requests should fail."""
        response = client.get("/api/search/unified?q=test")
        assert response.status_code in (401, 403)

    def test_search_requires_query(self, client, auth_headers):
        """Query parameter is required."""
        response = client.get("/api/search/unified", headers=auth_headers)
        assert response.status_code == 422

    def test_search_rejects_playlist_type(self, client, auth_headers):
        """Playlist type should be rejected per contracts.md."""
        response = client.get(
            "/api/search/unified?q=test&type=playlist",
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_search_accepts_valid_types(self, client, auth_headers):
        """Valid search types should be accepted."""
        for search_type in ["artist", "album", "track"]:
            response = client.get(
                f"/api/search/unified?q=test&type={search_type}",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == search_type

    def test_search_local_only_default(self, client, auth_headers):
        """Search returns local results without external flag."""
        response = client.get(
            "/api/search/unified?q=test&type=album",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "test"
        assert data["type"] == "album"
        assert "local" in data
        assert data["external"] is None

    def test_search_response_structure(self, client, auth_headers):
        """Response should have correct structure."""
        response = client.get(
            "/api/search/unified?q=test&type=album",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "query" in data
        assert "type" in data
        assert "local" in data

        # Check local structure
        local = data["local"]
        assert "count" in local
        assert "albums" in local
        assert "artists" in local
        assert "tracks" in local

    def test_search_with_results(self, client, auth_headers, test_album):
        """Search should return matching albums."""
        response = client.get(
            f"/api/search/unified?q={test_album.title}&type=album",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["local"]["count"] >= 1
        assert len(data["local"]["albums"]) >= 1

    def test_search_external_when_empty(self, client, auth_headers):
        """External search triggered when local empty and flag set."""
        with patch(
            "app.services.download.DownloadService.search_qobuz"
        ) as mock_qobuz:
            mock_qobuz.return_value = [
                {"id": "123", "title": "Test Album", "artist": "Test Artist"}
            ]

            response = client.get(
                "/api/search/unified?q=nonexistent_xyz_123&type=album&include_external=true",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["local"]["count"] == 0
            assert data["external"] is not None
            assert data["external"]["source"] == "qobuz"

    def test_search_no_external_when_local_found(
        self, client, auth_headers, test_album
    ):
        """External search NOT triggered when local results exist."""
        with patch(
            "app.services.download.DownloadService.search_qobuz"
        ) as mock_qobuz:
            response = client.get(
                f"/api/search/unified?q={test_album.title}&type=album&include_external=true",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["local"]["count"] >= 1
            assert data["external"] is None
            mock_qobuz.assert_not_called()

    def test_search_external_error_handled(self, client, auth_headers):
        """External search error should be handled gracefully."""
        with patch(
            "app.services.download.DownloadService.search_qobuz"
        ) as mock_qobuz:
            mock_qobuz.side_effect = Exception("Qobuz API error")

            response = client.get(
                "/api/search/unified?q=nonexistent_xyz_123&type=album&include_external=true",
                headers=auth_headers
            )
            assert response.status_code == 200
            data = response.json()
            assert data["external"] is not None
            assert data["external"]["error"] is not None
            assert data["external"]["count"] == 0

    def test_search_limit_parameter(self, client, auth_headers):
        """Limit parameter should be respected."""
        response = client.get(
            "/api/search/unified?q=test&type=album&limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_search_limit_validation(self, client, auth_headers):
        """Limit should be validated (1-50)."""
        # Too high
        response = client.get(
            "/api/search/unified?q=test&type=album&limit=100",
            headers=auth_headers
        )
        assert response.status_code == 422

        # Too low
        response = client.get(
            "/api/search/unified?q=test&type=album&limit=0",
            headers=auth_headers
        )
        assert response.status_code == 422
