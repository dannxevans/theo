"""
Integration tests for API key management routes.

Tests the full API key lifecycle: create, list, update, revoke.
"""
import pytest
import json
from datetime import datetime, timedelta
from auth import generate_api_key, hash_api_key


@pytest.fixture
def create_test_api_key(memory, test_user):
    """Helper to create a test API key."""
    def _create(name="Test Key", expires_in_days=None):
        key = generate_api_key()
        key_hash = hash_api_key(key)

        expires_at = None
        if expires_in_days is not None:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        key_id = memory.create_api_key(
            user_id=test_user["id"],
            name=name,
            key_hash=key_hash,
            expires_at=expires_at
        )

        return {
            "id": key_id,
            "key": key,
            "key_hash": key_hash,
            "name": name,
            "expires_at": expires_at,
            "user_id": test_user["id"]
        }
    return _create


class TestCreateApiKey:
    """Test POST /api/api-keys - Create new API key."""

    def test_create_key_success(self, client, auth_headers):
        """Should create API key with valid session."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "My iPhone"}
        )

        assert response.status_code == 201
        data = response.json
        assert "key" in data
        assert data["key"].startswith("theo_")
        assert len(data["key"]) == 69
        assert data["name"] == "My iPhone"
        assert "id" in data
        assert "created_at" in data

    def test_create_key_with_expiration(self, client, auth_headers):
        """Should create key with expiration date."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={
                "name": "Temporary Key",
                "expires_in_days": 30
            }
        )

        assert response.status_code == 201
        data = response.json
        assert data["expires_at"] is not None

    def test_create_key_never_expires(self, client, auth_headers):
        """Should create key without expiration."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={"name": "Permanent Key"}
        )

        assert response.status_code == 201
        data = response.json
        assert data["expires_at"] is None

    def test_create_key_default_name(self, client, auth_headers):
        """Should use default name if not provided."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 201
        data = response.json
        assert data["name"] == "Untitled Key"

    def test_create_key_invalid_expiration(self, client, auth_headers):
        """Should reject invalid expiration values."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={
                "name": "Test",
                "expires_in_days": -1
            }
        )

        assert response.status_code == 400

    def test_create_key_expiration_too_long(self, client, auth_headers):
        """Should reject expiration > 10 years."""
        response = client.post(
            "/api/api-keys",
            headers=auth_headers,
            json={
                "name": "Test",
                "expires_in_days": 5000
            }
        )

        assert response.status_code == 400

    def test_create_key_no_auth(self, client):
        """Should reject request without authentication."""
        response = client.post(
            "/api/api-keys",
            json={"name": "Test"}
        )

        assert response.status_code == 401

    def test_create_key_with_api_key_auth(self, client, create_test_api_key):
        """Should reject API key trying to create keys."""
        test_key = create_test_api_key()

        response = client.post(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"},
            json={"name": "Another Key"}
        )

        assert response.status_code == 403
        assert "Session authentication required" in response.json["error"]


class TestListApiKeys:
    """Test GET /api/api-keys - List user's API keys."""

    def test_list_keys_empty(self, client, auth_headers):
        """Should return empty list if no keys."""
        response = client.get("/api/api-keys", headers=auth_headers)

        assert response.status_code == 200
        assert response.json == []

    def test_list_keys_multiple(self, client, auth_headers, create_test_api_key):
        """Should list all user's keys."""
        create_test_api_key("Key 1")
        create_test_api_key("Key 2")
        create_test_api_key("Key 3")

        response = client.get("/api/api-keys", headers=auth_headers)

        assert response.status_code == 200
        keys = response.json
        assert len(keys) == 3
        assert {k["name"] for k in keys} == {"Key 1", "Key 2", "Key 3"}

    def test_list_keys_no_hash_leaked(self, client, auth_headers, create_test_api_key):
        """Should never return key hashes."""
        create_test_api_key()

        response = client.get("/api/api-keys", headers=auth_headers)

        assert response.status_code == 200
        keys = response.json
        for key in keys:
            assert "key_hash" not in key
            assert "key" not in key

    def test_list_keys_includes_metadata(self, client, auth_headers, create_test_api_key):
        """Should include all metadata fields."""
        create_test_api_key("Test Key", expires_in_days=30)

        response = client.get("/api/api-keys", headers=auth_headers)

        assert response.status_code == 200
        key = response.json[0]
        assert "id" in key
        assert "name" in key
        assert "created_at" in key
        assert "last_used_at" in key
        assert "expires_at" in key
        assert "is_revoked" in key

    def test_list_keys_no_auth(self, client):
        """Should reject request without authentication."""
        response = client.get("/api/api-keys")

        assert response.status_code == 401

    def test_list_keys_with_api_key_auth(self, client, create_test_api_key):
        """Should allow API key to list keys."""
        test_key = create_test_api_key()

        response = client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )

        # This actually works - API keys CAN list (just can't create/revoke)
        assert response.status_code == 200


class TestRevokeApiKey:
    """Test DELETE /api/api-keys/:id - Revoke API key."""

    def test_revoke_key_success(self, client, auth_headers, create_test_api_key):
        """Should revoke key successfully."""
        test_key = create_test_api_key()

        response = client.delete(
            f"/api/api-keys/{test_key['id']}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json["status"] == "ok"

    def test_revoke_key_not_found(self, client, auth_headers):
        """Should return 404 for non-existent key."""
        response = client.delete(
            "/api/api-keys/999999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_revoke_key_other_user(self, client, memory, create_test_api_key):
        """Should not allow revoking other user's keys."""
        # Create key for admin user
        test_key = create_test_api_key()

        # Create second user
        from auth import hash_password
        second_user_hash = hash_password("password")
        second_user_id = memory.create_user("testuser2", second_user_hash)

        # Login as second user
        from auth import generate_session_token
        token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(days=1)
        memory.create_auth_session(token, second_user_id, expires_at)

        # Try to revoke admin's key
        response = client.delete(
            f"/api/api-keys/{test_key['id']}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404  # Not found (hidden for security)

    def test_revoke_key_no_auth(self, client, create_test_api_key):
        """Should reject request without authentication."""
        test_key = create_test_api_key()

        response = client.delete(f"/api/api-keys/{test_key['id']}")

        assert response.status_code == 401

    def test_revoke_key_with_api_key_auth(self, client, create_test_api_key):
        """Should reject API key trying to revoke keys."""
        test_key = create_test_api_key()

        response = client.delete(
            f"/api/api-keys/{test_key['id']}",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )

        assert response.status_code == 403

    def test_revoked_key_cannot_authenticate(self, client, create_test_api_key, auth_headers):
        """Revoked key should not work for authentication."""
        test_key = create_test_api_key()

        # Key should work initially
        response = client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )
        assert response.status_code == 200

        # Revoke the key
        client.delete(f"/api/api-keys/{test_key['id']}", headers=auth_headers)

        # Key should no longer work
        response = client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )
        assert response.status_code == 401


class TestUpdateApiKey:
    """Test PATCH /api/api-keys/:id - Update API key metadata."""

    def test_update_key_name(self, client, auth_headers, create_test_api_key):
        """Should update key name."""
        test_key = create_test_api_key("Old Name")

        response = client.patch(
            f"/api/api-keys/{test_key['id']}",
            headers=auth_headers,
            json={"name": "New Name"}
        )

        assert response.status_code == 200

        # Verify name changed
        list_response = client.get("/api/api-keys", headers=auth_headers)
        keys = list_response.json
        updated_key = next(k for k in keys if k["id"] == test_key["id"])
        assert updated_key["name"] == "New Name"

    def test_update_key_no_name(self, client, auth_headers, create_test_api_key):
        """Should reject update without name."""
        test_key = create_test_api_key()

        response = client.patch(
            f"/api/api-keys/{test_key['id']}",
            headers=auth_headers,
            json={}
        )

        assert response.status_code == 400

    def test_update_key_not_found(self, client, auth_headers):
        """Should return 404 for non-existent key."""
        response = client.patch(
            "/api/api-keys/999999",
            headers=auth_headers,
            json={"name": "Test"}
        )

        assert response.status_code == 404

    def test_update_key_no_auth(self, client, create_test_api_key):
        """Should reject request without authentication."""
        test_key = create_test_api_key()

        response = client.patch(
            f"/api/api-keys/{test_key['id']}",
            json={"name": "Test"}
        )

        assert response.status_code == 401


class TestApiKeyAuthentication:
    """Test using API keys for authentication."""

    def test_api_key_grants_access(self, client, create_test_api_key):
        """Valid API key should grant access to protected endpoints."""
        test_key = create_test_api_key()

        response = client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )

        assert response.status_code == 200

    def test_invalid_api_key_rejected(self, client):
        """Invalid API key should be rejected."""
        response = client.get(
            "/api/api-keys",
            headers={"Authorization": "Bearer theo_invalidkey123"}
        )

        assert response.status_code == 401

    def test_expired_key_rejected(self, client, create_test_api_key):
        """Expired API key should be rejected."""
        # Create key that expired 1 day ago
        test_key = create_test_api_key(expires_in_days=-1)

        response = client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )

        assert response.status_code == 401

    def test_malformed_key_rejected(self, client):
        """Malformed API key should be rejected."""
        response = client.get(
            "/api/api-keys",
            headers={"Authorization": "Bearer not_a_valid_key"}
        )

        assert response.status_code == 401

    def test_api_key_updates_last_used(self, client, auth_headers, create_test_api_key, memory):
        """Using API key should update last_used_at."""
        test_key = create_test_api_key()

        # Initially, last_used_at should be None
        key_data = memory.get_api_key_by_id(test_key["id"])
        initial_last_used = key_data["last_used_at"]

        # Use the key
        client.get(
            "/api/api-keys",
            headers={"Authorization": f"Bearer {test_key['key']}"}
        )

        # last_used_at should be updated
        key_data = memory.get_api_key_by_id(test_key["id"])
        assert key_data["last_used_at"] is not None
        if initial_last_used:
            assert key_data["last_used_at"] > initial_last_used
