"""Tests for CLI commands."""
import pytest
from typer.testing import CliRunner
from app.cli.main import app
from app.services.auth import AuthService

runner = CliRunner()


def test_version():
    """Test version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Barbossa" in result.stdout


def test_auth_login_no_args():
    """Test auth login without arguments fails gracefully."""
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code != 0  # Should fail without username


def test_auth_whoami_not_logged_in():
    """Test whoami when not logged in."""
    result = runner.invoke(app, ["auth", "whoami"])
    # Should fail or show not logged in
    assert result.exit_code != 0 or "Not logged in" in result.stdout


def test_library_artists_not_logged_in():
    """Test library artists without login."""
    result = runner.invoke(app, ["library", "artists"])
    # Should fail without auth
    assert result.exit_code != 0


def test_library_albums_not_logged_in():
    """Test library albums without login."""
    result = runner.invoke(app, ["library", "albums"])
    assert result.exit_code != 0


def test_library_search_not_logged_in():
    """Test library search without login."""
    result = runner.invoke(app, ["library", "search", "test"])
    assert result.exit_code != 0


def test_admin_list_users_not_logged_in():
    """Test admin list-users without login."""
    result = runner.invoke(app, ["admin", "list-users"])
    assert result.exit_code != 0


def test_library_heart_requires_args():
    """Test heart command requires album or track ID."""
    result = runner.invoke(app, ["library", "heart"])
    # Should show error about missing args
    assert "album" in result.stdout.lower() or "track" in result.stdout.lower() or result.exit_code != 0


def test_library_unheart_requires_args():
    """Test unheart command requires album or track ID."""
    result = runner.invoke(app, ["library", "unheart"])
    assert "album" in result.stdout.lower() or "track" in result.stdout.lower() or result.exit_code != 0
