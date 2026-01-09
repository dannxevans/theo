"""
Tests for Work Mode IP restriction routes.

Tests admin configuration endpoints and IP access checking.
"""

import pytest
import json


class TestIPConfigurationRoutes:
    """Tests for GET/POST /api/work-mode-ip/config endpoints (admin only)."""

    def test_get_config_requires_auth(self, client):
        """Test that GET config requires authentication."""
        response = client.get("/api/work-mode-ip/config")
        assert response.status_code == 401

    def test_get_config_requires_admin(self, client, memory, auth_headers_non_admin):
        """Test that GET config requires admin privileges."""
        response = client.get("/api/work-mode-ip/config", headers=auth_headers_non_admin)
        assert response.status_code == 403
        assert "Admin access required" in response.json["error"]

    def test_get_config_returns_default(self, client, memory, auth_headers_admin):
        """Test GET config returns default configuration."""
        response = client.get("/api/work-mode-ip/config", headers=auth_headers_admin)

        assert response.status_code == 200
        data = response.json
        assert "enabled" in data
        assert "allowed_ranges" in data
        assert data["enabled"] == False
        assert isinstance(data["allowed_ranges"], list)

    def test_update_config_requires_auth(self, client):
        """Test that POST config requires authentication."""
        response = client.post(
            "/api/work-mode-ip/config",
            json={"enabled": True, "allowed_ranges": ["192.168.1.0/24"]}
        )
        assert response.status_code == 401

    def test_update_config_requires_admin(self, client, memory, auth_headers_non_admin):
        """Test that POST config requires admin privileges."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_non_admin,
            json={"enabled": True, "allowed_ranges": ["192.168.1.0/24"]}
        )
        assert response.status_code == 403
        assert "Admin access required" in response.json["error"]

    def test_update_config_missing_body(self, client, memory, auth_headers_admin):
        """Test update config with missing request body."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin
        )
        assert response.status_code == 400
        assert "Missing request body" in response.json["error"]

    def test_update_config_invalid_enabled_type(self, client, memory, auth_headers_admin):
        """Test update config with invalid enabled type."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": "not-a-boolean", "allowed_ranges": []}
        )
        assert response.status_code == 400
        assert "enabled must be a boolean" in response.json["error"]

    def test_update_config_invalid_ranges_type(self, client, memory, auth_headers_admin):
        """Test update config with invalid allowed_ranges type."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": True, "allowed_ranges": "not-a-list"}
        )
        assert response.status_code == 400
        assert "allowed_ranges must be a list" in response.json["error"]

    def test_update_config_invalid_cidr(self, client, memory, auth_headers_admin):
        """Test update config with invalid CIDR notation."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": True, "allowed_ranges": ["not-valid-cidr"]}
        )
        assert response.status_code == 400
        assert "Invalid CIDR notation" in response.json["error"]

    def test_update_config_success(self, client, memory, auth_headers_admin):
        """Test successful config update."""
        response = client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={
                "enabled": True,
                "allowed_ranges": ["192.168.1.0/24", "10.0.0.0/8"]
            }
        )

        assert response.status_code == 200
        data = response.json
        assert data["enabled"] == True
        assert len(data["allowed_ranges"]) == 2
        assert "192.168.1.0/24" in data["allowed_ranges"]
        assert "10.0.0.0/8" in data["allowed_ranges"]

        # Verify persistence
        verify_response = client.get("/api/work-mode-ip/config", headers=auth_headers_admin)
        assert verify_response.status_code == 200
        verify_data = verify_response.json
        assert verify_data["enabled"] == True
        assert len(verify_data["allowed_ranges"]) == 2


class TestIPCheckRoute:
    """Tests for GET /api/work-mode-ip/check endpoint."""

    def test_check_ip_requires_auth(self, client):
        """Test that check endpoint requires authentication."""
        response = client.get("/api/work-mode-ip/check")
        assert response.status_code == 401

    def test_check_ip_returns_current_ip(self, client, memory, auth_headers):
        """Test check endpoint returns current IP address."""
        response = client.get("/api/work-mode-ip/check", headers=auth_headers)

        assert response.status_code == 200
        data = response.json
        assert "allowed" in data
        assert "current_ip" in data
        assert "reason" in data
        assert isinstance(data["current_ip"], str)

    def test_check_ip_when_disabled(self, client, memory, auth_headers, auth_headers_admin):
        """Test check endpoint when IP restrictions are disabled."""
        # Ensure disabled
        client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": False, "allowed_ranges": []}
        )

        response = client.get("/api/work-mode-ip/check", headers=auth_headers)

        assert response.status_code == 200
        data = response.json
        assert data["allowed"] == True
        assert data["reason"] == "IP restrictions disabled"

    def test_check_ip_when_enabled_no_ranges(self, client, memory, auth_headers, auth_headers_admin):
        """Test check endpoint when enabled with no allowed ranges."""
        # Enable with no ranges
        client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": True, "allowed_ranges": []}
        )

        response = client.get("/api/work-mode-ip/check", headers=auth_headers)

        assert response.status_code == 200
        data = response.json
        assert data["allowed"] == False
        assert data["reason"] == "No allowed IP ranges configured"

    def test_check_ip_with_x_forwarded_for(self, client, memory, auth_headers, auth_headers_admin):
        """Test check endpoint uses X-Forwarded-For header."""
        # Configure to allow specific IP
        client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": True, "allowed_ranges": ["203.0.113.0/24"]}
        )

        # Make request with X-Forwarded-For header
        headers_with_ip = {**auth_headers, "X-Forwarded-For": "203.0.113.42"}
        response = client.get("/api/work-mode-ip/check", headers=headers_with_ip)

        assert response.status_code == 200
        data = response.json
        assert data["current_ip"] == "203.0.113.42"
        assert data["allowed"] == True

    def test_check_ip_with_x_real_ip(self, client, memory, auth_headers, auth_headers_admin):
        """Test check endpoint uses X-Real-IP header."""
        # Configure to allow specific IP
        client.post(
            "/api/work-mode-ip/config",
            headers=auth_headers_admin,
            json={"enabled": True, "allowed_ranges": ["203.0.113.0/24"]}
        )

        # Make request with X-Real-IP header
        headers_with_ip = {**auth_headers, "X-Real-IP": "203.0.113.50"}
        response = client.get("/api/work-mode-ip/check", headers=headers_with_ip)

        assert response.status_code == 200
        data = response.json
        assert data["current_ip"] == "203.0.113.50"
        assert data["allowed"] == True
