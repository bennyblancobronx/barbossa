"""Tests for album deletion with proper file handling."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app.services.library import LibraryService
from app.models.album import Album
from app.models.artist import Artist
from app.models.track import Track


class TestAlbumDeletion:
    """Test album deletion returns proper success/failure status."""

    def test_delete_album_not_found(self, db_session):
        """Deleting non-existent album returns False with error."""
        service = LibraryService(db_session)
        success, error = service.delete_album(99999)

        assert success is False
        assert error == "Album not found"

    def test_delete_album_success(self, db_session, test_album):
        """Successful deletion returns True with no error."""
        service = LibraryService(db_session)

        # Mock shutil.rmtree to avoid actual file operations
        with patch("shutil.rmtree") as mock_rmtree:
            success, error = service.delete_album(test_album.id)

        assert success is True
        assert error is None

        # Verify album is gone from DB
        album = db_session.query(Album).filter(Album.id == test_album.id).first()
        assert album is None

    def test_delete_album_permission_denied(self, db_session, test_album, tmp_path):
        """When file deletion fails with permission error, returns False and keeps DB record."""
        # Set album path to a real location
        album_dir = tmp_path / "Artist" / "Album"
        album_dir.mkdir(parents=True)
        test_album.path = str(album_dir)
        db_session.commit()

        service = LibraryService(db_session)

        # Mock rmtree to raise permission error
        with patch("app.services.library.shutil.rmtree", side_effect=PermissionError("Access denied")):
            success, error = service.delete_album(test_album.id)

        assert success is False
        assert "Permission denied" in error

        # Verify album still exists in DB
        album = db_session.query(Album).filter(Album.id == test_album.id).first()
        assert album is not None

    def test_delete_album_os_error(self, db_session, test_album, tmp_path):
        """When file deletion fails with OS error, returns False and keeps DB record."""
        # Set album path to a real location
        album_dir = tmp_path / "Artist" / "Album"
        album_dir.mkdir(parents=True)
        test_album.path = str(album_dir)
        db_session.commit()

        service = LibraryService(db_session)

        # Mock rmtree to raise OS error
        with patch("app.services.library.shutil.rmtree", side_effect=OSError("Disk full")):
            success, error = service.delete_album(test_album.id)

        assert success is False
        assert "Failed to delete files" in error

        # Verify album still exists in DB
        album = db_session.query(Album).filter(Album.id == test_album.id).first()
        assert album is not None

    def test_delete_album_skip_file_deletion(self, db_session, test_album):
        """delete_files=False skips file deletion but removes DB record."""
        service = LibraryService(db_session)

        with patch("shutil.rmtree") as mock_rmtree:
            success, error = service.delete_album(test_album.id, delete_files=False)

        assert success is True
        assert error is None
        mock_rmtree.assert_not_called()

        # Verify album is gone from DB
        album = db_session.query(Album).filter(Album.id == test_album.id).first()
        assert album is None


class TestDeleteAlbumAPI:
    """Test the DELETE /albums/{id} endpoint."""

    def test_delete_album_endpoint_success(self, client, auth_headers, test_album):
        """API returns success when deletion works."""
        with patch("app.services.library.LibraryService.delete_album") as mock:
            mock.return_value = (True, None)
            response = client.delete(
                f"/api/albums/{test_album.id}",
                headers=auth_headers
            )

        assert response.status_code == 200
        assert response.json()["message"] == "Album deleted"

    def test_delete_album_endpoint_not_found(self, client, auth_headers):
        """API returns 404 when album not found."""
        with patch("app.services.library.LibraryService.delete_album") as mock:
            mock.return_value = (False, "Album not found")
            response = client.delete(
                "/api/albums/99999",
                headers=auth_headers
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_album_endpoint_file_error(self, client, auth_headers, test_album):
        """API returns 500 when file deletion fails."""
        with patch("app.services.library.LibraryService.delete_album") as mock:
            mock.return_value = (False, "Permission denied: cannot delete files")
            response = client.delete(
                f"/api/albums/{test_album.id}",
                headers=auth_headers
            )

        assert response.status_code == 500
        assert "Permission denied" in response.json()["detail"]
