"""
Tests for Plex API client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from services.plex_client import PlexClient


@pytest.fixture
def plex_client():
    """Create a PlexClient instance for testing."""
    return PlexClient(
        auth_token="test_token_123", server_url="http://192.168.1.100:32400"
    )


class TestPlexClient:
    """Test Plex API client."""

    def test_init(self, plex_client):
        """Test client initialization."""
        assert plex_client.auth_token == "test_token_123"
        assert plex_client.server_url == "http://192.168.1.100:32400"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from server URL."""
        client = PlexClient(
            auth_token="test_token", server_url="http://192.168.1.100:32400/"
        )
        assert client.server_url == "http://192.168.1.100:32400"

    def test_get_headers(self, plex_client):
        """Test header generation."""
        headers = plex_client._get_headers()

        assert headers["X-Plex-Token"] == "test_token_123"
        assert headers["Accept"] == "application/json"

    @patch("services.plex_client.requests.get")
    def test_make_request_success(self, mock_get, plex_client):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {"size": 1, "Metadata": [{"title": "Test"}]}
        }
        mock_get.return_value = mock_response

        result = plex_client._make_request("/test")

        assert result is not None
        assert result["size"] == 1
        assert "Metadata" in result

    @patch("services.plex_client.requests.get")
    def test_make_request_unauthorized(self, mock_get, plex_client):
        """Test API request with invalid token."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        result = plex_client._make_request("/test")

        assert result is None

    @patch("services.plex_client.requests.get")
    def test_make_request_network_error(self, mock_get, plex_client):
        """Test API request with network error."""
        mock_get.side_effect = Exception("Network error")

        result = plex_client._make_request("/test")

        assert result is None

    @patch("services.plex_client.requests.get")
    def test_get_library_sections(self, mock_get, plex_client):
        """Test fetching library sections."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Directory": [
                    {"key": "1", "title": "Movies", "type": "movie"},
                    {"key": "2", "title": "TV Shows", "type": "show"},
                ]
            }
        }
        mock_get.return_value = mock_response

        sections = plex_client.get_library_sections()

        assert len(sections) == 2
        assert sections[0]["title"] == "Movies"
        assert sections[1]["type"] == "show"

    @patch("services.plex_client.requests.get")
    def test_get_library_sections_empty(self, mock_get, plex_client):
        """Test fetching library sections with no sections."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"MediaContainer": {"Directory": []}}
        mock_get.return_value = mock_response

        sections = plex_client.get_library_sections()

        assert sections == []

    @patch("services.plex_client.requests.get")
    def test_get_recently_watched(self, mock_get, plex_client):
        """Test fetching recently watched items."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "title": "Pilot",
                        "type": "episode",
                        "ratingKey": "12345",
                        "grandparentTitle": "Breaking Bad",
                        "parentIndex": 1,
                        "index": 1,
                        "viewedAt": 1609459200,
                        "thumb": "/library/metadata/12345/thumb",
                        "year": 2008,
                    },
                    {
                        "title": "Inception",
                        "type": "movie",
                        "ratingKey": "67890",
                        "viewedAt": 1609372800,
                        "year": 2010,
                    },
                ]
            }
        }
        mock_get.return_value = mock_response

        items = plex_client.get_recently_watched(limit=10)

        assert len(items) == 2
        assert items[0]["type"] == "episode"
        assert items[0]["show_title"] == "Breaking Bad"
        assert items[1]["type"] == "movie"
        assert items[1]["title"] == "Inception"

    @patch("services.plex_client.requests.get")
    def test_get_on_deck(self, mock_get, plex_client):
        """Test fetching On Deck items."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "title": "The One Where...",
                        "type": "episode",
                        "ratingKey": "111",
                        "grandparentTitle": "Friends",
                        "parentIndex": 1,
                        "index": 2,
                        "summary": "Episode summary",
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        items = plex_client.get_on_deck()

        assert len(items) == 1
        assert items[0]["show_title"] == "Friends"
        assert items[0]["season"] == 1
        assert items[0]["episode"] == 2

    @patch("services.plex_client.requests.get")
    def test_get_recently_added(self, mock_get, plex_client):
        """Test fetching recently added items."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "title": "New Episode",
                        "type": "episode",
                        "ratingKey": "222",
                        "key": "/library/metadata/222",
                        "grandparentTitle": "The Expanse",
                        "parentIndex": 6,
                        "index": 4,
                        "addedAt": 1640000000,
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        items = plex_client.get_recently_added(section_key="2", limit=10)

        assert len(items) == 1
        assert items[0]["type"] == "episode"
        assert items[0]["show_title"] == "The Expanse"

    @patch("services.plex_client.requests.get")
    def test_get_currently_playing(self, mock_get, plex_client):
        """Test fetching currently playing sessions."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "title": "Episode 1",
                        "type": "episode",
                        "grandparentTitle": "The Office",
                        "parentIndex": 1,
                        "index": 1,
                        "viewOffset": 120000,
                        "duration": 1200000,
                        "Player": {"title": "Living Room TV", "state": "playing"},
                        "User": {"title": "testuser"},
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        sessions = plex_client.get_currently_playing()

        assert len(sessions) == 1
        assert sessions[0]["user"] == "testuser"
        assert sessions[0]["player"] == "Living Room TV"
        assert sessions[0]["state"] == "playing"

    @patch("services.plex_client.requests.get")
    def test_get_item_details(self, mock_get, plex_client):
        """Test fetching item details."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "MediaContainer": {
                "Metadata": [
                    {
                        "title": "Pilot",
                        "type": "episode",
                        "ratingKey": "12345",
                        "summary": "The first episode",
                        "rating": 8.5,
                        "year": 2008,
                        "duration": 2700000,
                        "grandparentTitle": "Breaking Bad",
                        "parentIndex": 1,
                        "index": 1,
                    }
                ]
            }
        }
        mock_get.return_value = mock_response

        details = plex_client.get_item_details("12345")

        assert details is not None
        assert details["title"] == "Pilot"
        assert details["summary"] == "The first episode"
        assert details["rating"] == 8.5

    @patch("services.plex_client.requests.get")
    def test_get_item_details_not_found(self, mock_get, plex_client):
        """Test fetching item details for non-existent item."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"MediaContainer": {"Metadata": []}}
        mock_get.return_value = mock_response

        details = plex_client.get_item_details("99999")

        assert details is None

    @patch("services.plex_client.requests.get")
    def test_test_connection_success(self, mock_get, plex_client):
        """Test successful connection test."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"MediaContainer": {}}
        mock_get.return_value = mock_response

        result = plex_client.test_connection()

        assert result is True

    @patch("services.plex_client.requests.get")
    def test_test_connection_failure(self, mock_get, plex_client):
        """Test failed connection test."""
        mock_get.side_effect = Exception("Connection refused")

        result = plex_client.test_connection()

        assert result is False
