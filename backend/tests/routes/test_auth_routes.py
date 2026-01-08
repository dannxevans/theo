"""
Tests for authentication routes.

Tests login, logout, session verification, and password management.
"""

import pytest
from datetime import datetime, timedelta


def test_login_success(client, memory, test_user):
    """Test successful login."""
    response = client.post("/api/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })

    assert response.status_code == 200
    data = response.json

    assert "token" in data
    assert "user" in data
    assert data["user"]["username"] == test_user["username"]
    assert data["user"]["id"] == test_user["id"]


def test_login_invalid_credentials(client, memory, test_user):
    """Test login with wrong password."""
    response = client.post("/api/auth/login", json={
        "username": test_user["username"],
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    assert "error" in response.json


def test_login_nonexistent_user(client):
    """Test login with non-existent user."""
    response = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "password"
    })

    assert response.status_code == 401
    assert "error" in response.json


def test_login_missing_fields(client):
    """Test login with missing fields."""
    # Missing password
    response = client.post("/api/auth/login", json={
        "username": "testuser"
    })
    assert response.status_code == 400

    # Missing username
    response = client.post("/api/auth/login", json={
        "password": "password"
    })
    assert response.status_code == 400

    # Missing both
    response = client.post("/api/auth/login", json={})
    assert response.status_code == 400


def test_login_disabled_user(client, memory, test_user):
    """Test login with disabled user account."""
    # Disable user
    memory.disable_user(test_user["id"])

    response = client.post("/api/auth/login", json={
        "username": test_user["username"],
        "password": test_user["password"]
    })

    assert response.status_code == 401
    assert "disabled" in response.json["error"].lower()


def test_logout_success(client, memory, test_user, auth_token):
    """Test successful logout."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify session is deleted
    session = memory.get_auth_session(auth_token)
    assert session is None


def test_logout_without_token(client):
    """Test logout without authorization header."""
    response = client.post("/api/auth/logout")

    assert response.status_code == 400


def test_logout_invalid_token(client):
    """Test logout with invalid token format."""
    headers = {"Authorization": "InvalidToken"}
    response = client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 400


def test_verify_session_valid(client, memory, test_user, auth_token):
    """Test session verification with valid token."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/auth/verify", headers=headers)

    assert response.status_code == 200
    data = response.json

    assert data["valid"] is True
    assert data["user"]["username"] == test_user["username"]
    assert data["user"]["id"] == test_user["id"]


def test_verify_session_invalid(client):
    """Test session verification with invalid token."""
    headers = {"Authorization": "Bearer invalid-token-123"}
    response = client.get("/api/auth/verify", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["valid"] is False


def test_verify_session_expired(client, memory, test_user):
    """Test session verification with expired token."""
    from auth import generate_session_token

    # Create expired session
    token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/auth/verify", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["valid"] is False

    # Verify session was deleted
    session = memory.get_auth_session(token)
    assert session is None


def test_verify_session_disabled_user(client, memory, test_user, auth_token):
    """Test session verification with disabled user."""
    # Disable user
    memory.disable_user(test_user["id"])

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/auth/verify", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["valid"] is False


def test_verify_session_without_token(client):
    """Test session verification without token."""
    response = client.get("/api/auth/verify")

    assert response.status_code == 200
    assert response.json["valid"] is False


def test_change_password_success(client, memory, test_user, auth_token):
    """Test successful password change."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/auth/change-password", headers=headers, json={
        "current_password": test_user["password"],
        "new_password": "NewPass123!"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify new password works
    login_response = client.post("/api/auth/login", json={
        "username": test_user["username"],
        "password": "NewPass123!"
    })
    assert login_response.status_code == 200


def test_change_password_wrong_current(client, auth_token):
    """Test password change with wrong current password."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/auth/change-password", headers=headers, json={
        "current_password": "wrongpassword",
        "new_password": "newpassword123"
    })

    assert response.status_code == 401
    assert "incorrect" in response.json["error"].lower()


def test_change_password_too_short(client, test_user, auth_token):
    """Test password change with too short new password."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/auth/change-password", headers=headers, json={
        "current_password": test_user["password"],
        "new_password": "abc"
    })

    assert response.status_code == 400
    assert "at least 8 characters" in response.json["error"].lower()


def test_change_password_missing_fields(client, auth_token):
    """Test password change with missing fields."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Missing new password
    response = client.post("/api/auth/change-password", headers=headers, json={
        "current_password": "password"
    })
    assert response.status_code == 400

    # Missing current password
    response = client.post("/api/auth/change-password", headers=headers, json={
        "new_password": "newpassword"
    })
    assert response.status_code == 400


def test_change_password_unauthorized(client):
    """Test password change without authentication."""
    response = client.post("/api/auth/change-password", json={
        "current_password": "password",
        "new_password": "newpassword"
    })

    assert response.status_code == 401


def test_change_password_expired_session(client, memory, test_user):
    """Test password change with expired session."""
    from auth import generate_session_token

    # Create expired session
    token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/auth/change-password", headers=headers, json={
        "current_password": "password",
        "new_password": "newpassword"
    })

    assert response.status_code == 401
