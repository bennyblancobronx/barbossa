"""End-to-end tests for GUI review API flow."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.models.pending_review import PendingReview, PendingReviewStatus
from app.models.album import Album
from app.models.artist import Artist


class TestReviewApprovalFlow:
    """Full end-to-end tests for review approval API."""

    @pytest.fixture
    def review_folder(self, tmp_path):
        """Create a review folder with audio files."""
        folder = tmp_path / "review" / "pending-album-123"
        folder.mkdir(parents=True)
        (folder / "01 - Track.flac").write_bytes(b"FAKE_AUDIO")
        (folder / "02 - Track.flac").write_bytes(b"FAKE_AUDIO")
        return folder

    @pytest.fixture
    def pending_review(self, db_session, review_folder):
        """Create a pending review record."""
        review = PendingReview(
            path=str(review_folder),
            suggested_artist="Suggested Artist",
            suggested_album="Suggested Album",
            beets_confidence=0.75,
            track_count=2,
            quality_info={"sample_rate": 44100, "bit_depth": 16, "format": "flac"},
            source="import",
            source_url="",
            status=PendingReviewStatus.PENDING
        )
        db_session.add(review)
        db_session.commit()
        db_session.refresh(review)
        return review

    @pytest.fixture
    def mock_album(self, db_session):
        """Create a mock album in the database."""
        artist = Artist(
            name="Approved Artist",
            normalized_name="approved artist",
            sort_name="approved artist"
        )
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Approved Album",
            normalized_title="approved album",
            year=2024,
            total_tracks=2,
            available_tracks=2,
            artwork_path=None
        )
        db_session.add(album)
        db_session.commit()
        db_session.refresh(album)
        return album

    def test_approve_review_success(
        self, client, admin_auth_headers, db_session, pending_review, mock_album, review_folder
    ):
        """Approving a review should create album and update status."""
        with patch("app.api.review.BeetsClient") as mock_beets:
            with patch("app.api.review.ExifToolClient") as mock_exiftool:
                with patch("app.api.review.ImportService") as mock_import:
                    # Setup mocks
                    mock_beets.return_value.import_with_metadata = AsyncMock(
                        return_value=review_folder
                    )
                    mock_exiftool.return_value.get_album_metadata = AsyncMock(return_value=[])

                    mock_import.return_value.import_album = AsyncMock(return_value=mock_album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(
                        return_value="/path/cover.jpg"
                    )

                    response = client.post(
                        f"/api/import/review/{pending_review.id}/approve",
                        json={
                            "artist": "Approved Artist",
                            "album": "Approved Album",
                            "year": 2024
                        },
                        headers=admin_auth_headers
                    )

        assert response.status_code == 200, f"Failed: {response.json()}"
        data = response.json()
        assert data["status"] == "approved"
        assert data["album_id"] == mock_album.id

        # Verify review status updated
        db_session.refresh(pending_review)
        assert pending_review.status == PendingReviewStatus.APPROVED

    def test_approve_review_requires_admin(
        self, client, auth_headers, pending_review
    ):
        """Non-admin users cannot approve reviews."""
        response = client.post(
            f"/api/import/review/{pending_review.id}/approve",
            json={"artist": "Test", "album": "Test"},
            headers=auth_headers  # Regular user, not admin
        )

        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    def test_approve_already_processed(
        self, client, admin_auth_headers, db_session, pending_review
    ):
        """Cannot approve an already-processed review."""
        # Mark as already approved
        pending_review.status = PendingReviewStatus.APPROVED
        db_session.commit()

        response = client.post(
            f"/api/import/review/{pending_review.id}/approve",
            json={"artist": "Test", "album": "Test"},
            headers=admin_auth_headers
        )

        assert response.status_code == 400
        assert "already processed" in response.json()["detail"].lower()

    def test_approve_fetches_artwork(
        self, client, admin_auth_headers, db_session, pending_review, review_folder
    ):
        """Approved review should attempt to fetch artwork if missing."""
        # Album without artwork
        artist = Artist(name="Art", normalized_name="art", sort_name="art")
        db_session.add(artist)
        db_session.flush()

        album = Album(
            artist_id=artist.id,
            title="Album",
            normalized_title="album",
            total_tracks=1,
            available_tracks=1,
            artwork_path=None
        )
        db_session.add(album)
        db_session.commit()

        with patch("app.api.review.BeetsClient") as mock_beets:
            with patch("app.api.review.ExifToolClient") as mock_exiftool:
                with patch("app.api.review.ImportService") as mock_import:
                    mock_beets.return_value.import_with_metadata = AsyncMock(
                        return_value=review_folder
                    )
                    mock_exiftool.return_value.get_album_metadata = AsyncMock(return_value=[])
                    mock_import.return_value.import_album = AsyncMock(return_value=album)
                    mock_import.return_value.fetch_artwork_if_missing = AsyncMock(
                        return_value="/cover.jpg"
                    )

                    response = client.post(
                        f"/api/import/review/{pending_review.id}/approve",
                        json={"artist": "Art", "album": "Album"},
                        headers=admin_auth_headers
                    )

        assert response.status_code == 200
        # Verify artwork fetch was called
        mock_import.return_value.fetch_artwork_if_missing.assert_called_once()


class TestReviewRejectionFlow:
    """Tests for review rejection flow."""

    @pytest.fixture
    def review_folder(self, tmp_path):
        """Create a review folder."""
        folder = tmp_path / "review" / "reject-album"
        folder.mkdir(parents=True)
        (folder / "track.flac").write_bytes(b"audio")
        return folder

    @pytest.fixture
    def pending_review(self, db_session, review_folder):
        """Create a pending review."""
        review = PendingReview(
            path=str(review_folder),
            suggested_artist="Artist",
            suggested_album="Album",
            status=PendingReviewStatus.PENDING
        )
        db_session.add(review)
        db_session.commit()
        return review

    def test_reject_deletes_files(
        self, client, admin_auth_headers, db_session, pending_review, review_folder
    ):
        """Reject with delete_files=True removes files."""
        assert review_folder.exists()

        response = client.post(
            f"/api/import/review/{pending_review.id}/reject",
            json={"delete_files": True},
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

        # Files should be deleted
        assert not review_folder.exists()

        # Review status should be rejected
        db_session.refresh(pending_review)
        assert pending_review.status == PendingReviewStatus.REJECTED

    def test_reject_moves_to_rejected_folder(
        self, client, admin_auth_headers, db_session, pending_review, review_folder, tmp_path
    ):
        """Reject with delete_files=False moves to rejected folder."""
        with patch("app.api.review.settings") as mock_settings:
            mock_settings.music_import = str(tmp_path / "import")
            (tmp_path / "import" / "rejected").mkdir(parents=True)

            response = client.post(
                f"/api/import/review/{pending_review.id}/reject",
                json={"delete_files": False, "reason": "Not wanted"},
                headers=admin_auth_headers
            )

        assert response.status_code == 200

        db_session.refresh(pending_review)
        assert pending_review.status == PendingReviewStatus.REJECTED
        assert pending_review.notes == "Not wanted"

    def test_reject_requires_admin(self, client, auth_headers, pending_review):
        """Non-admin cannot reject."""
        response = client.post(
            f"/api/import/review/{pending_review.id}/reject",
            json={"delete_files": True},
            headers=auth_headers
        )

        assert response.status_code == 403


class TestFailedReviewsEndpoint:
    """Tests for the failed reviews listing endpoint."""

    def test_list_failed_reviews(self, client, admin_auth_headers, db_session):
        """GET /import/review/failed returns failed reviews."""
        # Create some reviews with different statuses
        reviews = [
            PendingReview(
                path="/tmp/pending",
                suggested_artist="A1",
                suggested_album="Album1",
                status=PendingReviewStatus.PENDING
            ),
            PendingReview(
                path="/tmp/failed1",
                suggested_artist="A2",
                suggested_album="Album2",
                status=PendingReviewStatus.FAILED,
                error_message="DB connection lost"
            ),
            PendingReview(
                path="/tmp/failed2",
                suggested_artist="A3",
                suggested_album="Album3",
                status=PendingReviewStatus.FAILED,
                error_message="Beets crashed"
            ),
            PendingReview(
                path="/tmp/approved",
                suggested_artist="A4",
                suggested_album="Album4",
                status=PendingReviewStatus.APPROVED
            ),
        ]
        for r in reviews:
            db_session.add(r)
        db_session.commit()

        response = client.get(
            "/api/import/review/failed",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return failed reviews
        assert len(data) == 2
        assert all(r["status"] == "failed" for r in data)
        assert any("DB connection" in r.get("error_message", "") for r in data)
        assert any("Beets crashed" in r.get("error_message", "") for r in data)

    def test_list_failed_reviews_requires_admin(self, client, auth_headers):
        """Non-admin cannot list failed reviews."""
        response = client.get(
            "/api/import/review/failed",
            headers=auth_headers
        )

        assert response.status_code == 403

    def test_list_failed_reviews_empty(self, client, admin_auth_headers, db_session):
        """Returns empty list when no failed reviews."""
        response = client.get(
            "/api/import/review/failed",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        assert response.json() == []


class TestReviewNotFoundHandling:
    """Tests for 404 cases."""

    def test_approve_not_found(self, client, admin_auth_headers):
        """Approving non-existent review returns 404."""
        response = client.post(
            "/api/import/review/99999/approve",
            json={"artist": "A", "album": "B"},
            headers=admin_auth_headers
        )

        assert response.status_code == 404

    def test_reject_not_found(self, client, admin_auth_headers):
        """Rejecting non-existent review returns 404."""
        response = client.post(
            "/api/import/review/99999/reject",
            json={"delete_files": True},
            headers=admin_auth_headers
        )

        assert response.status_code == 404

    def test_get_review_not_found(self, client, admin_auth_headers):
        """Getting non-existent review returns 404."""
        response = client.get(
            "/api/import/review/99999",
            headers=admin_auth_headers
        )

        assert response.status_code == 404
