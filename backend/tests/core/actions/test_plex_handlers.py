"""
Tests for Plex action handlers.

Tests the PlexHandlers class including recently watched, on deck,
and currently playing functionality with lightweight LLM processing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.actions.plex_handlers import PlexHandlers


@pytest.fixture
def mock_memory():
    """Create mock memory store."""
    memory = Mock()
    return memory


@pytest.fixture
def mock_action_registry():
    """Create mock action registry."""
    registry = Mock()
    return registry


@pytest.fixture
def plex_handlers(mock_action_registry, mock_memory):
    """Create PlexHandlers instance with mocks."""
    return PlexHandlers(mock_action_registry, mock_memory)


@pytest.fixture
def mock_plex_credentials():
    """Valid Plex credentials."""
    return {
        "access_token": "test-token-123",
        "server_url": "http://192.168.1.100:32400",
        "server_name": "Test Server",
        "plex_username": "testuser",
        "is_valid": True
    }


@pytest.fixture
def mock_recently_watched_items():
    """Sample recently watched items."""
    return [
        {
            "type": "episode",
            "show_title": "The Office",
            "season": 1,
            "episode": 1,
            "title": "Pilot",
            "viewed_at": "2024-01-10T20:00:00Z"
        },
        {
            "type": "movie",
            "title": "Inception",
            "year": 2010,
            "viewed_at": "2024-01-09T19:30:00Z"
        }
    ]


@pytest.fixture
def mock_on_deck_items():
    """Sample on deck items."""
    return [
        {
            "type": "episode",
            "show_title": "Breaking Bad",
            "season": 2,
            "episode": 5,
            "title": "Breakage"
        },
        {
            "type": "movie",
            "title": "The Matrix",
            "year": 1999
        }
    ]


class TestPlexHandlers:
    """Test suite for PlexHandlers."""

    def test_handle_plex_not_connected(self, plex_handlers, mock_memory):
        """Test handle_plex when Plex account not connected."""
        # Setup
        mock_memory.get_plex_credentials.return_value = None

        # Execute
        result = plex_handlers.handle_plex(
            user_text="What was I watching?",
            session_id="test-session",
            user_id=1,
            context={}
        )

        # Assert - when not connected, returns provider="plex" not "action_router"
        assert result["provider"] == "plex"
        assert "plex" in result["task_type"]
        assert "not connected" in result["text"].lower() or "invalid" in result["text"].lower()

    def test_handle_plex_routes_to_recently_watched(self, plex_handlers, mock_memory):
        """Test handle_plex routes 'what was i watching' to recently watched."""
        # Setup
        mock_memory.get_plex_credentials.return_value = {"is_valid": True, "access_token": "token", "server_url": "http://test"}

        with patch.object(plex_handlers, 'handle_get_recently_watched') as mock_handler:
            mock_handler.return_value = {"text": "mocked"}

            # Execute
            result = plex_handlers.handle_plex(
                user_text="What was I watching?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            mock_handler.assert_called_once()

    def test_handle_plex_routes_to_on_deck(self, plex_handlers, mock_memory):
        """Test handle_plex routes 'what should i watch' to on deck."""
        # Setup
        mock_memory.get_plex_credentials.return_value = {"is_valid": True, "access_token": "token", "server_url": "http://test"}

        with patch.object(plex_handlers, 'handle_get_on_deck') as mock_handler:
            mock_handler.return_value = {"text": "mocked"}

            # Execute
            result = plex_handlers.handle_plex(
                user_text="What should I watch next?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            mock_handler.assert_called_once()

    def test_handle_plex_routes_to_currently_playing(self, plex_handlers, mock_memory):
        """Test handle_plex routes 'what am i watching' to currently playing."""
        # Setup
        mock_memory.get_plex_credentials.return_value = {"is_valid": True, "access_token": "token", "server_url": "http://test"}

        with patch.object(plex_handlers, 'handle_get_currently_playing') as mock_handler:
            mock_handler.return_value = {"text": "mocked"}

            # Execute
            result = plex_handlers.handle_plex(
                user_text="What am I watching now?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            mock_handler.assert_called_once()

    @patch('services.plex_client.PlexClient')
    def test_handle_get_recently_watched_success(
        self, mock_client_class, plex_handlers, mock_memory,
        mock_plex_credentials, mock_recently_watched_items
    ):
        """Test successful recently watched retrieval."""
        # Setup
        mock_memory.get_plex_credentials.return_value = mock_plex_credentials
        mock_client = Mock()
        mock_client.get_recently_watched.return_value = mock_recently_watched_items
        mock_client_class.return_value = mock_client

        with patch.object(plex_handlers, '_process_with_llm') as mock_llm:
            mock_llm.return_value = {
                "text": "You've been watching The Office and Inception recently.",
                "provider_name": "Haiku-4.5",
                "model": "claude-haiku-4"
            }

            # Execute
            result = plex_handlers.handle_get_recently_watched(
                user_text="What was I watching?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            assert result["provider"] == "action_router"
            assert result["task_type"] == "plex"
            assert result["metadata"]["service"] == "Plex"
            assert result["metadata"]["sub_task"] == "Recently watched"
            assert result["metadata"]["llm_provider_name"] == "Haiku-4.5"
            assert result["metadata"]["item_count"] == 2
            assert "watching" in result["text"].lower()

    def test_handle_get_recently_watched_no_credentials(self, plex_handlers, mock_memory):
        """Test recently watched with no credentials."""
        # Setup
        mock_memory.get_plex_credentials.return_value = None

        # Execute
        result = plex_handlers.handle_get_recently_watched(
            user_text="What was I watching?",
            session_id="test-session",
            user_id=1,
            context={}
        )

        # Assert
        assert result["provider"] == "plex"
        assert "plex" in result["task_type"]
        assert "not connected" in result["text"].lower() or "invalid" in result["text"].lower()

    def test_handle_get_recently_watched_invalid_credentials(
        self, plex_handlers, mock_memory
    ):
        """Test recently watched with invalid credentials."""
        # Setup
        mock_memory.get_plex_credentials.return_value = {
            "access_token": "token",
            "server_url": "http://test",
            "is_valid": False
        }

        # Execute
        result = plex_handlers.handle_get_recently_watched(
            user_text="What was I watching?",
            session_id="test-session",
            user_id=1,
            context={}
        )

        # Assert
        assert result["provider"] == "plex"
        assert "plex" in result["task_type"]
        assert "not connected" in result["text"].lower() or "invalid" in result["text"].lower()

    @patch('services.plex_client.PlexClient')
    def test_handle_get_on_deck_success(
        self, mock_client_class, plex_handlers, mock_memory,
        mock_plex_credentials, mock_on_deck_items
    ):
        """Test successful on deck retrieval."""
        # Setup
        mock_memory.get_plex_credentials.return_value = mock_plex_credentials
        mock_client = Mock()
        mock_client.get_on_deck.return_value = mock_on_deck_items
        mock_client_class.return_value = mock_client

        with patch.object(plex_handlers, '_process_with_llm') as mock_llm:
            mock_llm.return_value = {
                "text": "You should watch Breaking Bad or The Matrix next.",
                "provider_name": "Sonnet-4.5",
                "model": "claude-sonnet-4"
            }

            # Execute
            result = plex_handlers.handle_get_on_deck(
                user_text="What should I watch?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            assert result["provider"] == "action_router"
            assert result["task_type"] == "plex"
            assert result["metadata"]["service"] == "Plex"
            assert result["metadata"]["sub_task"] == "On deck"
            assert result["metadata"]["llm_provider_name"] == "Sonnet-4.5"
            assert result["metadata"]["item_count"] == 2

    @patch('services.plex_client.PlexClient')
    def test_handle_get_currently_playing_success(
        self, mock_client_class, plex_handlers, mock_memory, mock_plex_credentials
    ):
        """Test successful currently playing retrieval."""
        # Setup
        mock_memory.get_plex_credentials.return_value = mock_plex_credentials
        mock_client = Mock()
        mock_sessions = [
            {
                "type": "episode",
                "show_title": "Stranger Things",
                "season": 4,
                "episode": 1,
                "title": "Chapter One",
                "user": "testuser",
                "player": "Chrome",
                "state": "playing"
            }
        ]
        mock_client.get_currently_playing.return_value = mock_sessions
        mock_client_class.return_value = mock_client

        with patch.object(plex_handlers, '_process_with_llm') as mock_llm:
            mock_llm.return_value = {
                "text": "Stranger Things is currently playing on Chrome.",
                "provider_name": "GPT-4o",
                "model": "gpt-4o"
            }

            # Execute
            result = plex_handlers.handle_get_currently_playing(
                user_text="What am I watching?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            assert result["provider"] == "action_router"
            assert result["task_type"] == "plex"
            assert result["metadata"]["service"] == "Plex"
            assert result["metadata"]["sub_task"] == "Currently playing"
            assert result["metadata"]["session_count"] == 1

    @patch('core.router.route_request')
    def test_process_with_llm_success(self, mock_route_request, plex_handlers):
        """Test _process_with_llm successfully processes data."""
        # Setup
        mock_route_request.return_value = {
            "text": "Processed response",
            "metadata": {
                "provider_name": "Haiku-4.5",
                "provider_type": "anthropic"
            },
            "model": "claude-haiku-4"
        }

        # Execute
        result = plex_handlers._process_with_llm("Raw data", user_id=1)

        # Assert
        assert result["text"] == "Processed response"
        assert result["provider_name"] == "Haiku-4.5"
        assert result["model"] == "claude-haiku-4"
        mock_route_request.assert_called_once()

        # Check route_request was called with correct parameters
        call_args = mock_route_request.call_args[0][0]
        assert call_args["force_intent"] == "system"
        assert call_args["user_id"] == 1
        assert "Raw data" in call_args["text"]

    @patch('core.router.route_request')
    def test_process_with_llm_no_metadata(self, mock_route_request, plex_handlers):
        """Test _process_with_llm when result has no metadata."""
        # Setup
        mock_route_request.return_value = {
            "text": "Processed response",
            "model": "test-model"
        }

        # Execute
        result = plex_handlers._process_with_llm("Raw data", user_id=1)

        # Assert
        assert result["text"] == "Processed response"
        assert result["provider_name"] is None
        assert result["model"] == "test-model"

    @patch('core.router.route_request')
    def test_process_with_llm_error_fallback(self, mock_route_request, plex_handlers):
        """Test _process_with_llm falls back to raw data on error."""
        # Setup
        mock_route_request.side_effect = Exception("LLM error")

        # Execute
        result = plex_handlers._process_with_llm("Raw fallback data", user_id=1)

        # Assert
        assert result["text"] == "Raw fallback data"
        assert result["provider_name"] is None
        assert result["model"] is None

    @patch('services.plex_client.PlexClient')
    def test_handle_get_recently_watched_client_error(
        self, mock_client_class, plex_handlers, mock_memory, mock_plex_credentials
    ):
        """Test recently watched handles client errors gracefully."""
        # Setup
        mock_memory.get_plex_credentials.return_value = mock_plex_credentials
        mock_client = Mock()
        mock_client.get_recently_watched.side_effect = Exception("Connection error")
        mock_client_class.return_value = mock_client

        # Execute
        result = plex_handlers.handle_get_recently_watched(
            user_text="What was I watching?",
            session_id="test-session",
            user_id=1,
            context={}
        )

        # Assert
        assert result["provider"] == "plex"
        assert "plex" in result["task_type"]
        assert "couldn't fetch" in result["text"].lower() or "sorry" in result["text"].lower()

    @patch('services.plex_client.PlexClient')
    def test_handle_get_recently_watched_no_items(
        self, mock_client_class, plex_handlers, mock_memory, mock_plex_credentials
    ):
        """Test recently watched with no items."""
        # Setup
        mock_memory.get_plex_credentials.return_value = mock_plex_credentials
        mock_client = Mock()
        mock_client.get_recently_watched.return_value = []
        mock_client_class.return_value = mock_client

        with patch.object(plex_handlers, '_process_with_llm') as mock_llm:
            mock_llm.return_value = {
                "text": "No recently watched items found.",
                "provider_name": "Haiku-4.5",
                "model": "claude-haiku-4"
            }

            # Execute
            result = plex_handlers.handle_get_recently_watched(
                user_text="What was I watching?",
                session_id="test-session",
                user_id=1,
                context={}
            )

            # Assert
            assert result["metadata"]["item_count"] == 0
            assert "no" in result["text"].lower()
