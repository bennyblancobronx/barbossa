"""Tests for artist artwork endpoint."""
import pytest
from pathlib import Path
import tempfile
import shutil


class TestArtistArtwork:
    """Tests for GET /api/artists/{artist_id}/artwork endpoint."""

    def test_artist_artwork_not_found(self, client, auth_headers):
        """Test 404 when artist doesn't exist."""
        response = client.get("/api/artists/999999/artwork")
        assert response.status_code == 404
        assert response.json()["detail"] == "Artist not found"

    def test_artist_artwork_no_artwork(self, client, auth_headers, test_artist):
        """Test 404 when artist has no artwork."""
        response = client.get(f"/api/artists/{test_artist.id}/artwork")
        assert response.status_code == 404
        assert response.json()["detail"] == "Artwork not found"

    def test_artist_artwork_from_album(self, client, auth_headers, test_album, db):
        """Test artist artwork falls back to album cover."""
        # Create a temp directory with cover art
        with tempfile.TemporaryDirectory() as tmpdir:
            album_path = Path(tmpdir) / "test_album"
            album_path.mkdir()
            cover_path = album_path / "cover.jpg"
            # Create a minimal valid JPEG (just header)
            cover_path.write_bytes(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00')
            
            # Update album path in DB
            test_album.path = str(album_path)
            db.commit()
            
            response = client.get(f"/api/artists/{test_album.artist_id}/artwork")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"


class TestArtistHeartEndpoints:
    """Tests for artist heart/unheart endpoints."""

    def test_heart_artist(self, client, auth_headers, test_artist, test_album):
        """Test hearting an artist adds all their albums."""
        response = client.post(
            f"/api/me/library/artists/{test_artist.id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "album" in response.json()["message"].lower()

    def test_heart_artist_not_found(self, client, auth_headers):
        """Test 404 when artist doesn't exist."""
        response = client.post(
            "/api/me/library/artists/999999",
            headers=auth_headers
        )
        assert response.status_code == 404

    def test_unheart_artist(self, client, auth_headers, test_artist, test_album):
        """Test unhearting an artist removes all their albums."""
        # First heart
        client.post(f"/api/me/library/artists/{test_artist.id}", headers=auth_headers)
        
        # Then unheart
        response = client.delete(
            f"/api/me/library/artists/{test_artist.id}",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_unheart_artist_not_found(self, client, auth_headers):
        """Test 404 when artist doesn't exist."""
        response = client.delete(
            "/api/me/library/artists/999999",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestArtistIsHearted:
    """Tests for is_hearted field in artist responses."""

    def test_list_artists_includes_is_hearted(self, client, auth_headers, test_artist):
        """Test list_artists returns is_hearted field."""
        response = client.get("/api/artists", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()
        for artist in response.json()["items"]:
            assert "is_hearted" in artist

    def test_get_artist_includes_is_hearted(self, client, auth_headers, test_artist):
        """Test get_artist returns is_hearted field."""
        response = client.get(f"/api/artists/{test_artist.id}", headers=auth_headers)
        assert response.status_code == 200
        assert "is_hearted" in response.json()

    def test_is_hearted_changes_after_heart(self, client, auth_headers, test_artist, test_album):
        """Test is_hearted reflects actual heart status."""
        # Initially not hearted
        response = client.get(f"/api/artists/{test_artist.id}", headers=auth_headers)
        assert response.json()["is_hearted"] == False

        # Heart the artist
        client.post(f"/api/me/library/artists/{test_artist.id}", headers=auth_headers)

        # Now should be hearted
        response = client.get(f"/api/artists/{test_artist.id}", headers=auth_headers)
        assert response.json()["is_hearted"] == True

        # Unheart
        client.delete(f"/api/me/library/artists/{test_artist.id}", headers=auth_headers)

        # Back to not hearted
        response = client.get(f"/api/artists/{test_artist.id}", headers=auth_headers)
        assert response.json()["is_hearted"] == False
