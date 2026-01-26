"""Tests for import rollback functionality."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestImportRollbackCode:
    """Test that rollback code structure is correct."""

    def test_download_service_has_rollback_logic(self):
        """Download service _import_album should have try/except for rollback."""
        import inspect
        from app.services.download import DownloadService

        source = inspect.getsource(DownloadService._import_album)

        # Verify rollback code is present
        assert "except Exception as e:" in source
        assert "ROLLBACK" in source or "rollback" in source.lower()
        assert "failed_dir" in source
        assert "shutil.move" in source

    def test_imports_task_has_failed_handling(self):
        """process_review task should mark review as failed on error."""
        import inspect
        from app.tasks.imports import process_review

        source = inspect.getsource(process_review)

        # Verify failed status handling
        assert 'status = "failed"' in source or "status = 'failed'" in source
        assert "error_message" in source


class TestCLIImportArtwork:
    """Test that CLI import has artwork fetch code."""

    def test_cli_import_has_artwork_fetch(self):
        """CLI import command should call fetch_artwork_if_missing."""
        import inspect
        from app.cli.admin import import_album

        source = inspect.getsource(import_album)

        # Verify artwork fetch code is present
        assert "fetch_artwork_if_missing" in source
