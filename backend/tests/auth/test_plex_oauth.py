"""
Tests for Plex OAuth PIN-based authentication.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from auth.plex_oauth import PlexOAuth


class TestPlexOAuth:
    """Test Plex OAuth handler."""

    def test_get_headers_without_token(self):
        """Test header generation without auth token."""
        headers = PlexOAuth.get_headers()

        assert headers["X-Plex-Product"] == "THEO"
        assert headers["X-Plex-Version"] == "1.0"
        assert "X-Plex-Client-Identifier" in headers
        assert headers["Accept"] == "application/json"
        assert "X-Plex-Token" not in headers

    def test_get_headers_with_token(self):
        """Test header generation with auth token."""
        headers = PlexOAuth.get_headers(auth_token="test_token_123")

        assert headers["X-Plex-Token"] == "test_token_123"
        assert headers["Accept"] == "application/json"

    @patch("auth.plex_oauth.requests.post")
    def test_request_pin_success(self, mock_post):
        """Test successful PIN request."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 123456,
            "code": "ABCD",
        }
        mock_post.return_value = mock_response

        result = PlexOAuth.request_pin()

        assert result is not None
        assert result["id"] == 123456
        assert result["code"] == "ABCD"
        assert "auth_url" in result
        assert "ABCD" in result["auth_url"]

        # Verify request
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["strong"] is True

    @patch("auth.plex_oauth.requests.post")
    def test_request_pin_failure(self, mock_post):
        """Test PIN request failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        result = PlexOAuth.request_pin()

        assert result is None

    @patch("auth.plex_oauth.requests.post")
    def test_request_pin_network_error(self, mock_post):
        """Test PIN request with network error."""
        mock_post.side_effect = Exception("Network error")

        result = PlexOAuth.request_pin()

        assert result is None

    @patch("auth.plex_oauth.requests.get")
    def test_check_pin_status_pending(self, mock_get):
        """Test PIN status check when pending."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123456,
            "code": "ABCD",
            "authToken": None,
        }
        mock_get.return_value = mock_response

        result = PlexOAuth.check_pin_status(123456)

        assert result is None  # Not yet authorized

    @patch("auth.plex_oauth.requests.get")
    def test_check_pin_status_authorized(self, mock_get):
        """Test PIN status check when authorized."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123456,
            "code": "ABCD",
            "authToken": "plex_auth_token_xyz",
        }
        mock_get.return_value = mock_response

        result = PlexOAuth.check_pin_status(123456)

        assert result == "plex_auth_token_xyz"

    @patch("auth.plex_oauth.requests.get")
    def test_check_pin_status_error(self, mock_get):
        """Test PIN status check with error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_get.return_value = mock_response

        result = PlexOAuth.check_pin_status(123456)

        assert result is None

    @patch("auth.plex_oauth.requests.get")
    def test_get_user_info_success(self, mock_get):
        """Test successful user info fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 12345,
            "username": "testuser",
            "email": "test@example.com",
            "thumb": "https://plex.tv/users/avatar.jpg",
        }
        mock_get.return_value = mock_response

        result = PlexOAuth.get_user_info("test_token")

        assert result is not None
        assert result["id"] == "12345"
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"

    @patch("auth.plex_oauth.requests.get")
    def test_get_user_info_failure(self, mock_get):
        """Test user info fetch failure."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_get.return_value = mock_response

        result = PlexOAuth.get_user_info("invalid_token")

        assert result is None

    @patch("auth.plex_oauth.requests.get")
    def test_get_primary_server_success(self, mock_get):
        """Test successful primary server fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "Home Server",
                "provides": "server",
                "presence": True,
                "owned": True,
                "clientIdentifier": "abc123",
                "productVersion": "1.30.0",
                "connections": [
                    {"uri": "http://192.168.1.100:32400", "local": True},
                    {"uri": "https://plex.direct:32400", "local": False},
                ],
            }
        ]
        mock_get.return_value = mock_response

        result = PlexOAuth.get_primary_server("test_token")

        assert result is not None
        assert result["name"] == "Home Server"
        assert result["url"] == "http://192.168.1.100:32400"  # Prefers local
        assert result["version"] == "1.30.0"
        assert result["owned"] is True

    @patch("auth.plex_oauth.requests.get")
    def test_get_primary_server_no_servers(self, mock_get):
        """Test primary server fetch with no servers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        result = PlexOAuth.get_primary_server("test_token")

        assert result is None

    @patch("auth.plex_oauth.requests.get")
    def test_get_primary_server_prefers_owned(self, mock_get):
        """Test that owned servers are preferred over shared."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "Shared Server",
                "provides": "server",
                "presence": True,
                "owned": False,
                "connections": [{"uri": "http://192.168.1.200:32400"}],
            },
            {
                "name": "My Server",
                "provides": "server",
                "presence": True,
                "owned": True,
                "connections": [{"uri": "http://192.168.1.100:32400"}],
            },
        ]
        mock_get.return_value = mock_response

        result = PlexOAuth.get_primary_server("test_token")

        assert result["name"] == "My Server"
        assert result["owned"] is True

    @patch("auth.plex_oauth.requests.get")
    def test_validate_token_valid(self, mock_get):
        """Test token validation with valid token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = PlexOAuth.validate_token("valid_token")

        assert result is True

    @patch("auth.plex_oauth.requests.get")
    def test_validate_token_invalid(self, mock_get):
        """Test token validation with invalid token."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = PlexOAuth.validate_token("invalid_token")

        assert result is False

    @patch("auth.plex_oauth.requests.get")
    def test_validate_token_network_error(self, mock_get):
        """Test token validation with network error."""
        mock_get.side_effect = Exception("Network error")

        result = PlexOAuth.validate_token("test_token")

        assert result is False
