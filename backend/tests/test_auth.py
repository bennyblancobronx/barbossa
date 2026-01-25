"""Tests for authentication endpoints."""
import pytest
from app.services.auth import AuthService


def test_login_success(client, db):
    """Test successful login."""
    # Create user
    auth = AuthService(db)
    auth.create_user("testuser", "testpass")

    # Login
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "testpass"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["username"] == "testuser"
    assert data["user"]["is_admin"] is False


def test_login_invalid_password(client, db):
    """Test login with wrong password."""
    auth = AuthService(db)
    auth.create_user("testuser", "testpass")

    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "wrongpass"},
    )

    assert response.status_code == 401


def test_login_invalid_user(client, db):
    """Test login with non-existent user."""
    response = client.post(
        "/api/auth/login",
        json={"username": "nouser", "password": "testpass"},
    )

    assert response.status_code == 401


def test_get_me(client, db, test_user, auth_headers):
    """Test getting current user info."""
    response = client.get("/api/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"


def test_get_me_unauthorized(client):
    """Test getting current user without auth."""
    response = client.get("/api/auth/me")

    assert response.status_code == 403


def test_logout(client, auth_headers):
    """Test logout endpoint."""
    response = client.post("/api/auth/logout", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
