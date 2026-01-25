"""End-to-end tests for Barbossa."""
import pytest


class TestHealthEndpoints:
    """Health check endpoint tests."""

    def test_health_endpoint(self, client):
        """Test health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "checks" in data
        assert "version" in data

    def test_ready_endpoint(self, client):
        """Test readiness check."""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data

    def test_live_endpoint(self, client):
        """Test liveness check."""
        response = client.get("/live")
        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True


class TestAuthWorkflow:
    """Authentication workflow tests."""

    def test_login_and_browse(self, client, db):
        """Test login and library browsing flow."""
        from app.services.auth import AuthService

        # Create user
        auth = AuthService(db)
        auth.create_user("e2euser", "e2epass")

        # Login
        response = client.post(
            "/api/auth/login",
            json={"username": "e2euser", "password": "e2epass"}
        )
        assert response.status_code == 200
        token = response.json()["token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Browse library
        response = client.get("/api/artists", headers=headers)
        assert response.status_code == 200

        # Get user info
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["username"] == "e2euser"


class TestLibraryWorkflow:
    """Library browsing workflow tests."""

    def test_heart_workflow(self, client, db, test_user, test_album, auth_headers):
        """Test heart/unheart album flow."""
        album_id = test_album.id

        # Heart album
        response = client.post(
            f"/api/me/library/albums/{album_id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Check in user library
        response = client.get("/api/me/library", headers=auth_headers)
        assert response.status_code == 200
        albums = response.json().get("albums", [])
        album_ids = [a["id"] for a in albums]
        assert album_id in album_ids

        # Unheart album
        response = client.delete(
            f"/api/me/library/albums/{album_id}",
            headers=auth_headers
        )
        assert response.status_code == 200

        # Verify removed
        response = client.get("/api/me/library", headers=auth_headers)
        albums = response.json().get("albums", [])
        album_ids = [a["id"] for a in albums]
        assert album_id not in album_ids


class TestSearchWorkflow:
    """Search functionality tests."""

    def test_search_library(self, client, auth_headers, db):
        """Test search returns expected structure."""
        response = client.get(
            "/api/search",
            params={"q": "test", "type": "all"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "artists" in data
        assert "albums" in data
        assert "tracks" in data


class TestAdminWorkflow:
    """Admin functionality tests."""

    def test_admin_user_management(self, client, db, admin_headers):
        """Test admin can manage users."""
        # Create user
        response = client.post(
            "/api/admin/users",
            json={"username": "newuser", "password": "newpass"},
            headers=admin_headers
        )
        assert response.status_code in [200, 201]

        # List users
        response = client.get("/api/admin/users", headers=admin_headers)
        assert response.status_code == 200
        users = response.json()
        usernames = [u["username"] for u in users]
        assert "newuser" in usernames

    def test_non_admin_cannot_manage_users(self, client, auth_headers):
        """Test regular user cannot access admin endpoints."""
        response = client.get("/api/admin/users", headers=auth_headers)
        assert response.status_code in [401, 403]


class TestAPIStructure:
    """API structure validation tests."""

    def test_root_endpoint(self, client):
        """Test root returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_docs_available(self, client):
        """Test API docs are accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_unauthorized_access(self, client):
        """Test protected endpoints require auth."""
        endpoints = [
            "/api/auth/me",
            "/api/me/library",
            "/api/artists",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"
