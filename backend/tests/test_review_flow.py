"""Tests for the review approval/rejection flow."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from app.models.pending_review import PendingReview, PendingReviewStatus


class TestReviewStatus:
    """Test that review status constants are defined correctly."""

    def test_failed_status_exists(self):
        """PendingReviewStatus should have FAILED status."""
        assert hasattr(PendingReviewStatus, "FAILED")
        assert PendingReviewStatus.FAILED == "failed"


class TestReviewModel:
    """Test PendingReview model has required fields."""

    def test_error_message_field(self, db_session):
        """PendingReview should have error_message field."""
        review = PendingReview(
            path="/tmp/test",
            suggested_artist="Test",
            suggested_album="Album",
            status=PendingReviewStatus.FAILED,
            error_message="Test error"
        )
        db_session.add(review)
        db_session.commit()

        fetched = db_session.query(PendingReview).filter(
            PendingReview.id == review.id
        ).first()
        assert fetched.error_message == "Test error"
        assert fetched.status == PendingReviewStatus.FAILED
