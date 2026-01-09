"""
Tests for Plex API routes.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


@pytest.fixture
def test_user(memory):
    """Create a test user."""
    user = memory.create_user(
        username=f"plex_route_test_{datetime.now().timestamp()}",
        password="test_password_123",
        is_admin=False,
    )
    yield user


@pytest.fixture
def auth_headers(memory, test_user):
    """Create authentication headers."""
    token = memory.create_auth_session(
        test_user["id"], expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def personal_mode(memory, test_user):
    """Set user to Personal Mode."""
    memory.set_user_mode(test_user["id"], "personal")


class TestPlexAuthRoutes:
    """Test Plex authentication routes."""

    @patch("routes.plex_routes.PlexOAuth.request_pin")
    def test_start_plex_auth_success(
        self, mock_request_pin, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test starting Plex OAuth flow."""
        mock_request_pin.return_value = {
            "id": 123456,
            "code": "ABCD",
            "auth_url": "https://app.plex.tv/auth#?clientID=xxx&code=ABCD",
        }

        response = client.post("/api/plex/auth/start", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["pin_id"] == 123456
        assert data["code"] == "ABCD"
        assert "auth_url" in data

    def test_start_plex_auth_unauthorized(self, client):
        """Test starting OAuth without authentication."""
        response = client.post("/api/plex/auth/start")

        assert response.status_code == 401

    def test_start_plex_auth_work_mode(
        self, client, memory, auth_headers, test_user
    ):
        """Test starting OAuth in Work Mode (should fail)."""
        memory.set_user_mode(test_user["id"], "work")

        response = client.post("/api/plex/auth/start", headers=auth_headers)

        assert response.status_code == 403
        assert "Personal Mode" in response.get_json()["error"]

    @patch("routes.plex_routes.PlexOAuth.request_pin")
    def test_start_plex_auth_plex_error(
        self, mock_request_pin, client, auth_headers, personal_mode
    ):
        """Test starting OAuth when Plex API fails."""
        mock_request_pin.return_value = None

        response = client.post("/api/plex/auth/start", headers=auth_headers)

        assert response.status_code == 500

    @patch("routes.plex_routes.PlexOAuth.check_pin_status")
    def test_poll_plex_auth_pending(
        self, mock_check_pin, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test polling when authorization is pending."""
        # Store PIN ID
        memory.set_user_preference(test_user["id"], "plex_pin_id", "123456")
        memory.set_user_preference(
            test_user["id"],
            "plex_pin_expires",
            str((datetime.utcnow() + timedelta(minutes=5)).timestamp()),
        )

        mock_check_pin.return_value = None  # Still pending

        response = client.post(
            "/api/plex/auth/poll",
            headers=auth_headers,
            json={"pin_id": 123456},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "pending"

    @patch("routes.plex_routes.PlexOAuth.get_primary_server")
    @patch("routes.plex_routes.PlexOAuth.get_user_info")
    @patch("routes.plex_routes.PlexOAuth.check_pin_status")
    def test_poll_plex_auth_authorized(
        self,
        mock_check_pin,
        mock_get_user,
        mock_get_server,
        client,
        memory,
        auth_headers,
        test_user,
        personal_mode,
    ):
        """Test polling when authorization is complete."""
        # Store PIN ID
        memory.set_user_preference(test_user["id"], "plex_pin_id", "123456")
        memory.set_user_preference(
            test_user["id"],
            "plex_pin_expires",
            str((datetime.utcnow() + timedelta(minutes=5)).timestamp()),
        )

        mock_check_pin.return_value = "plex_auth_token"
        mock_get_user.return_value = {
            "id": "plex_user_123",
            "username": "testuser",
            "email": "test@example.com",
        }
        mock_get_server.return_value = {
            "name": "Home Server",
            "url": "http://192.168.1.100:32400",
            "version": "1.30.0",
            "owned": True,
        }

        response = client.post(
            "/api/plex/auth/poll",
            headers=auth_headers,
            json={"pin_id": 123456},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "authorized"
        assert data["connected"] is True
        assert data["server_name"] == "Home Server"

        # Verify credentials were stored
        credentials = memory.get_plex_credentials(test_user["id"])
        assert credentials is not None
        assert credentials["plex_user_id"] == "plex_user_123"

    def test_poll_plex_auth_invalid_pin(
        self, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test polling with invalid PIN ID."""
        # Store different PIN ID
        memory.set_user_preference(test_user["id"], "plex_pin_id", "999999")

        response = client.post(
            "/api/plex/auth/poll",
            headers=auth_headers,
            json={"pin_id": 123456},
        )

        assert response.status_code == 400
        assert "Invalid PIN ID" in response.get_json()["error"]

    def test_poll_plex_auth_expired_pin(
        self, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test polling with expired PIN."""
        memory.set_user_preference(test_user["id"], "plex_pin_id", "123456")
        memory.set_user_preference(
            test_user["id"],
            "plex_pin_expires",
            str((datetime.utcnow() - timedelta(minutes=1)).timestamp()),
        )

        response = client.post(
            "/api/plex/auth/poll",
            headers=auth_headers,
            json={"pin_id": 123456},
        )

        assert response.status_code == 400
        assert "expired" in response.get_json()["error"]


class TestPlexStatusRoutes:
    """Test Plex status routes."""

    def test_get_plex_status_connected(
        self, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test getting status when connected."""
        memory.store_plex_credentials(
            user_id=test_user["id"],
            access_token="test_token",
            plex_user_id="plex_123",
            plex_username="testuser",
            server_url="http://192.168.1.100:32400",
            server_name="Home Server",
        )

        response = client.get("/api/plex/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["connected"] is True
        assert data["server_name"] == "Home Server"
        assert data["plex_username"] == "testuser"

    def test_get_plex_status_disconnected(
        self, client, auth_headers, personal_mode
    ):
        """Test getting status when not connected."""
        response = client.get("/api/plex/status", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["connected"] is False

    def test_get_plex_status_work_mode(
        self, client, memory, auth_headers, test_user
    ):
        """Test getting status in Work Mode."""
        memory.set_user_mode(test_user["id"], "work")

        response = client.get("/api/plex/status", headers=auth_headers)

        assert response.status_code == 403

    def test_disconnect_plex(
        self, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test disconnecting Plex account."""
        # Setup connected state
        memory.store_plex_credentials(
            user_id=test_user["id"],
            access_token="test_token",
            plex_user_id="plex_123",
            plex_username="testuser",
            server_url="http://server:32400",
        )
        memory.update_plex_settings(
            test_user["id"], new_episode_notifications_enabled=True
        )
        memory.track_plex_notification(
            test_user["id"], "/library/metadata/123", "episode"
        )

        response = client.delete("/api/plex/disconnect", headers=auth_headers)

        assert response.status_code == 200
        assert response.get_json()["success"] is True

        # Verify cleanup
        assert memory.get_plex_credentials(test_user["id"]) is None
        assert not memory.is_plex_item_notified(test_user["id"], "/library/metadata/123")


class TestPlexSettingsRoutes:
    """Test Plex settings routes."""

    def test_get_plex_settings(
        self, client, auth_headers, personal_mode
    ):
        """Test getting Plex settings."""
        response = client.get("/api/plex/settings", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "new_episode_notifications_enabled" in data
        assert data["check_frequency_minutes"] == 15

    def test_update_plex_settings(
        self, client, memory, auth_headers, test_user, personal_mode
    ):
        """Test updating Plex settings."""
        response = client.put(
            "/api/plex/settings",
            headers=auth_headers,
            json={
                "new_episode_notifications_enabled": True,
                "check_frequency_minutes": 30,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["settings"]["new_episode_notifications_enabled"] is True
        assert data["settings"]["check_frequency_minutes"] == 30

    def test_update_plex_settings_invalid_frequency(
        self, client, auth_headers, personal_mode
    ):
        """Test updating settings with invalid frequency."""
        response = client.put(
            "/api/plex/settings",
            headers=auth_headers,
            json={"check_frequency_minutes": 200},  # Too high
        )

        assert response.status_code == 400


class TestPlexLibraryRoutes:
    """Test Plex library routes."""

    @patch("routes.plex_routes.PlexClient")
    def test_get_recently_watched(
        self,
        mock_client_class,
        client,
        memory,
        auth_headers,
        test_user,
        personal_mode,
    ):
        """Test getting recently watched items."""
        # Setup
        memory.store_plex_credentials(
            user_id=test_user["id"],
            access_token="test_token",
            plex_user_id="plex_123",
            plex_username="testuser",
            server_url="http://server:32400",
        )

        mock_client = Mock()
        mock_client.get_recently_watched.return_value = [
            {
                "title": "Episode 1",
                "type": "episode",
                "show_title": "The Office",
                "season": 1,
                "episode": 1,
            }
        ]
        mock_client_class.return_value = mock_client

        response = client.get("/api/plex/library/recent", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "items" in data
        assert len(data["items"]) == 1

    def test_get_recently_watched_not_connected(
        self, client, auth_headers, personal_mode
    ):
        """Test getting recently watched when not connected."""
        response = client.get("/api/plex/library/recent", headers=auth_headers)

        assert response.status_code == 400
        assert "not connected" in response.get_json()["error"]

    @patch("routes.plex_routes.PlexClient")
    def test_get_on_deck(
        self,
        mock_client_class,
        client,
        memory,
        auth_headers,
        test_user,
        personal_mode,
    ):
        """Test getting On Deck items."""
        memory.store_plex_credentials(
            user_id=test_user["id"],
            access_token="test_token",
            plex_user_id="plex_123",
            plex_username="testuser",
            server_url="http://server:32400",
        )

        mock_client = Mock()
        mock_client.get_on_deck.return_value = [
            {"title": "Next Episode", "type": "episode"}
        ]
        mock_client_class.return_value = mock_client

        response = client.get("/api/plex/library/on-deck", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "items" in data

    @patch("routes.plex_routes.PlexClient")
    def test_get_currently_playing(
        self,
        mock_client_class,
        client,
        memory,
        auth_headers,
        test_user,
        personal_mode,
    ):
        """Test getting currently playing sessions."""
        memory.store_plex_credentials(
            user_id=test_user["id"],
            access_token="test_token",
            plex_user_id="plex_123",
            plex_username="testuser",
            server_url="http://server:32400",
        )

        mock_client = Mock()
        mock_client.get_currently_playing.return_value = [
            {"title": "Playing Now", "state": "playing"}
        ]
        mock_client_class.return_value = mock_client

        response = client.get(
            "/api/plex/library/currently-playing", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "sessions" in data
