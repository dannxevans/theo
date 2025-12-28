"""
Tests for M365 routes.

Tests Microsoft 365 OAuth authentication and integration management.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


@patch("auth.m365_oauth.M365OAuth.is_configured")
@patch("auth.m365_oauth.M365OAuth.initiate_device_flow")
def test_m365_auth_start_success(mock_flow, mock_configured, client, auth_headers):
    """Test initiate M365 OAuth flow."""
    mock_configured.return_value = True
    mock_flow.return_value = {
        "user_code": "ABC123",
        "verification_url": "https://microsoft.com/devicelogin",
        "message": "Enter code ABC123",
        "expires_in": 900,
        "interval": 5,
        "device_code": "device-code-123"
    }

    response = client.post("/api/m365/auth/start", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["user_code"] == "ABC123"
    assert "verification_url" in data
    assert "device_code" in data


def test_m365_auth_start_unauthorized(client):
    """Test M365 auth start requires authentication."""
    response = client.post("/api/m365/auth/start")

    assert response.status_code == 401


@patch("auth.m365_oauth.M365OAuth.is_configured")
def test_m365_auth_start_not_configured(mock_configured, client, auth_headers):
    """Test M365 auth when not configured."""
    mock_configured.return_value = False

    response = client.post("/api/m365/auth/start", headers=auth_headers)

    assert response.status_code == 500
    assert "not configured" in response.json["error"].lower()


@patch("auth.m365_oauth.M365OAuth.is_configured")
@patch("requests.post")
def test_m365_auth_poll_success(mock_post, mock_configured, client, memory, auth_headers, test_user):
    """Test M365 auth poll with successful token."""
    mock_configured.return_value = True
    mock_post.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "access_token": "access-token-123",
            "refresh_token": "refresh-token-123",
            "expires_in": 3600,
            "scope": "Calendars.ReadWrite"
        }
    )

    response = client.post("/api/m365/auth/poll", headers=auth_headers, json={
        "device_code": "device-code-123"
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "success"

    # Verify credentials stored
    creds = memory.get_m365_credentials(test_user["id"])
    assert creds is not None


@patch("requests.post")
def test_m365_auth_poll_pending(mock_post, client, auth_headers):
    """Test M365 auth poll when authorization pending."""
    mock_post.return_value = MagicMock(
        status_code=400,
        json=lambda: {"error": "authorization_pending"}
    )

    response = client.post("/api/m365/auth/poll", headers=auth_headers, json={
        "device_code": "device-code-123"
    })

    assert response.status_code == 202
    assert response.json["status"] == "pending"


@patch("requests.post")
def test_m365_auth_poll_declined(mock_post, client, auth_headers):
    """Test M365 auth poll when user declines."""
    mock_post.return_value = MagicMock(
        status_code=400,
        json=lambda: {"error": "authorization_declined"}
    )

    response = client.post("/api/m365/auth/poll", headers=auth_headers, json={
        "device_code": "device-code-123"
    })

    assert response.status_code == 400
    assert response.json["status"] == "declined"


@patch("requests.post")
def test_m365_auth_poll_expired(mock_post, client, auth_headers):
    """Test M365 auth poll when device code expired."""
    mock_post.return_value = MagicMock(
        status_code=400,
        json=lambda: {"error": "expired_token"}
    )

    response = client.post("/api/m365/auth/poll", headers=auth_headers, json={
        "device_code": "device-code-123"
    })

    assert response.status_code == 400
    assert response.json["status"] == "expired"


def test_m365_auth_poll_missing_device_code(client, auth_headers):
    """Test M365 auth poll without device code."""
    response = client.post("/api/m365/auth/poll", headers=auth_headers, json={})

    assert response.status_code == 400


def test_m365_status_not_connected(client, auth_headers):
    """Test M365 status when not connected."""
    response = client.get("/api/m365/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["connected"] is False


def test_m365_status_connected(client, memory, auth_headers, test_user):
    """Test M365 status when connected."""
    # Store credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at,
        upn="user@example.com"
    )

    response = client.get("/api/m365/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["connected"] is True
    assert data["is_valid"] is True
    assert "expires_at" in data


def test_m365_status_token_expires_soon(client, memory, auth_headers, test_user):
    """Test M365 status when token expires soon."""
    # Token expires in 5 minutes
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    response = client.get("/api/m365/status", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["token_expires_soon"] is True


def test_m365_status_unauthorized(client):
    """Test M365 status requires authentication."""
    response = client.get("/api/m365/status")

    assert response.status_code == 401


def test_m365_disconnect(client, memory, auth_headers, test_user):
    """Test disconnect M365 account."""
    # Store credentials first
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    # Create service provider
    memory.store_service_provider(
        user_id=test_user["id"],
        name="M365",
        category="calendar",
        provider_type="m365"
    )

    response = client.post("/api/m365/disconnect", headers=auth_headers)

    assert response.status_code == 200
    assert response.json["status"] == "disconnected"

    # Verify credentials deleted
    creds = memory.get_m365_credentials(test_user["id"])
    assert creds is None

    # Verify service providers deleted
    providers = memory.get_service_providers(test_user["id"])
    m365_providers = [p for p in providers if p.get("provider_type") == "m365"]
    assert len(m365_providers) == 0


def test_m365_disconnect_when_not_connected(client, auth_headers):
    """Test disconnect when M365 not connected."""
    response = client.post("/api/m365/disconnect", headers=auth_headers)

    # Should succeed (idempotent)
    assert response.status_code == 200


def test_m365_disconnect_unauthorized(client):
    """Test disconnect requires authentication."""
    response = client.post("/api/m365/disconnect")

    assert response.status_code == 401
