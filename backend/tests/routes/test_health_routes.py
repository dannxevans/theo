"""
Tests for health routes.

Tests health check endpoints and M365 integration status.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def test_health_endpoint(client):
    """Test basic health check endpoint."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["service"] == "THEO-Backend"


def test_api_health_endpoint(client):
    """Test API health check endpoint."""
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["service"] == "THEO"


def test_health_overview_unauthorized(client):
    """Test health overview requires authentication."""
    response = client.get("/api/health/overview")

    assert response.status_code == 401
    assert "error" in response.json


def test_health_overview_success(client, memory, auth_headers, test_user, sample_provider):
    """Test health overview returns system status."""
    # Create M365 credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="test-token",
        refresh_token="test-refresh",
        expires_at=expires_at,
        scope="Calendars.ReadWrite",
        upn="test@example.com"
    )

    # Create WHOOP credentials
    whoop_expires_at = datetime.utcnow() + timedelta(hours=2)
    memory.store_whoop_credentials(
        user_id=test_user["id"],
        access_token="whoop-token",
        refresh_token="whoop-refresh",
        expires_at=whoop_expires_at,
        whoop_user_id=12345
    )

    # Create service provider
    memory.store_service_provider(
        user_id=test_user["id"],
        name="Test Calendar",
        category="calendar",
        provider_type="m365"
    )

    response = client.get("/api/health/overview", headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    # Check structure
    assert "ai_providers" in data
    assert "m365_integration" in data
    assert "whoop_integration" in data
    assert "service_providers" in data

    # Check AI providers
    assert len(data["ai_providers"]) > 0
    provider = data["ai_providers"][0]
    assert "id" in provider
    assert "name" in provider
    assert "health_status" in provider

    # Check M365 integration
    m365 = data["m365_integration"]
    assert m365["connected"] is True
    assert m365["account"] == "test@example.com"

    # Check WHOOP integration
    whoop = data["whoop_integration"]
    assert whoop["connected"] is True
    assert whoop["whoop_user_id"] == "12345"  # Stored as string in DB
    assert whoop["token_valid"] is True
    assert whoop["hours_until_expiry"] is not None

    # Check service providers
    assert len(data["service_providers"]) > 0


def test_health_overview_no_m365(client, auth_headers, sample_provider):
    """Test health overview when M365 not connected."""
    response = client.get("/api/health/overview", headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    m365 = data["m365_integration"]
    assert m365["connected"] is False

    # WHOOP should also be not connected
    whoop = data["whoop_integration"]
    assert whoop["connected"] is False


def test_health_overview_expired_session(client, memory, test_user):
    """Test health overview with expired session."""
    from auth import generate_session_token

    # Create expired session
    token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/health/overview", headers=headers)

    assert response.status_code == 401


@patch("actions.m365_provider.M365Provider")
def test_m365_health_check_success(mock_provider, client, memory, auth_headers, test_user):
    """Test M365 health check endpoint."""
    # Create M365 credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="test-token",
        refresh_token="test-refresh",
        expires_at=expires_at
    )

    # Mock health check
    mock_instance = MagicMock()
    mock_instance.check_health.return_value = {
        "healthy": True,
        "status": "connected",
        "last_check": datetime.utcnow().isoformat()
    }
    mock_provider.return_value = mock_instance

    response = client.post("/api/health/test-m365", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["healthy"] is True
    assert "response_time_ms" in data


def test_m365_health_check_not_connected(client, auth_headers):
    """Test M365 health check when not connected."""
    response = client.post("/api/health/test-m365", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["healthy"] is False
    assert data["status"] == "not_connected"


def test_m365_health_check_unauthorized(client):
    """Test M365 health check requires authentication."""
    response = client.post("/api/health/test-m365")

    assert response.status_code == 401


@patch("actions.m365_provider.M365Provider")
def test_m365_health_check_error(mock_provider, client, memory, auth_headers, test_user):
    """Test M365 health check with error."""
    # Create M365 credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="test-token",
        refresh_token="test-refresh",
        expires_at=expires_at
    )

    # Mock health check error
    mock_provider.side_effect = Exception("Connection failed")

    response = client.post("/api/health/test-m365", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["healthy"] is False
    assert data["status"] == "error"
    assert "error" in data
