"""
Unit tests for WHOOP Token Refresh Service.

Tests the proactive token refresh functionality that ensures
WHOOP OAuth tokens are refreshed before expiration.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from core.proactive.whoop_token_refresh_service import (
    WHOOPTokenRefreshService,
    refresh_all_whoop_tokens
)


class TestWHOOPTokenRefreshService:
    """Test WHOOP token refresh service."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory store."""
        memory = Mock()
        memory.engine = Mock()
        memory.whoop_credentials = Mock()
        memory.whoop_credentials.c = Mock()
        memory.whoop_credentials.c.user_id = Mock()
        memory.whoop_credentials.c.is_valid = Mock()
        return memory

    @pytest.fixture
    def service(self, mock_memory):
        """Create service instance."""
        return WHOOPTokenRefreshService(mock_memory)

    def test_init(self, mock_memory):
        """Test service initialization."""
        service = WHOOPTokenRefreshService(mock_memory)
        assert service.memory == mock_memory

    def test_refresh_all_tokens_no_users(self, service, mock_memory):
        """Test refresh when no users have WHOOP credentials."""
        # Mock engine to return empty list
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execute = Mock(return_value=[])
        mock_memory.engine.begin = Mock(return_value=mock_conn)

        # Should complete without errors
        service.refresh_all_tokens()

        # Verify connection was created
        mock_memory.engine.begin.assert_called_once()

    def test_refresh_all_tokens_with_users(self, service, mock_memory):
        """Test refresh with multiple users."""
        # Mock _get_whoop_users to return user IDs
        with patch.object(service, '_get_whoop_users', return_value=[1, 2]):
            # Mock successful refresh for both users
            with patch.object(service, '_refresh_user_token', return_value='refreshed'):
                service.refresh_all_tokens()

                # Verify refresh was called for both users
                assert service._refresh_user_token.call_count == 2

    def test_refresh_user_token_success(self, service, mock_memory):
        """Test successful token refresh for a user."""
        user_id = 1
        old_refresh_time = datetime.utcnow() - timedelta(hours=1)
        new_refresh_time = datetime.utcnow()

        # Mock credentials before refresh
        old_creds = {
            'user_id': user_id,
            'access_token': 'old_token',
            'refresh_token': 'refresh_token',
            'expires_at': datetime.utcnow() - timedelta(minutes=10),
            'is_valid': True,
            'last_refreshed_at': old_refresh_time
        }

        # Mock credentials after refresh
        new_creds = {
            'user_id': user_id,
            'access_token': 'new_token',
            'refresh_token': 'refresh_token',
            'expires_at': datetime.utcnow() + timedelta(hours=1),
            'is_valid': True,
            'last_refreshed_at': new_refresh_time
        }

        # First call returns old creds, second call returns new creds
        mock_memory.get_whoop_credentials = Mock(return_value=old_creds)
        mock_memory.refresh_whoop_token_if_needed = Mock(return_value=new_creds)

        result = service._refresh_user_token(user_id)

        assert result == "refreshed"
        mock_memory.get_whoop_credentials.assert_called_once_with(user_id)
        mock_memory.refresh_whoop_token_if_needed.assert_called_once_with(user_id)

    def test_refresh_user_token_skipped(self, service, mock_memory):
        """Test token refresh skipped when token still valid."""
        user_id = 1
        refresh_time = datetime.utcnow() - timedelta(minutes=30)

        # Mock credentials that are still valid
        creds = {
            'user_id': user_id,
            'access_token': 'valid_token',
            'refresh_token': 'refresh_token',
            'expires_at': datetime.utcnow() + timedelta(minutes=30),
            'is_valid': True,
            'last_refreshed_at': refresh_time
        }

        # Both calls return same credentials (not refreshed)
        mock_memory.get_whoop_credentials = Mock(return_value=creds)
        mock_memory.refresh_whoop_token_if_needed = Mock(return_value=creds)

        result = service._refresh_user_token(user_id)

        assert result == "skipped"
        mock_memory.refresh_whoop_token_if_needed.assert_called_once_with(user_id)

    def test_refresh_user_token_no_credentials(self, service, mock_memory):
        """Test refresh when user has no credentials."""
        user_id = 1

        mock_memory.get_whoop_credentials = Mock(return_value=None)

        result = service._refresh_user_token(user_id)

        assert result == "error"
        mock_memory.get_whoop_credentials.assert_called_once_with(user_id)

    def test_refresh_user_token_invalid_credentials(self, service, mock_memory):
        """Test refresh when credentials are marked invalid."""
        user_id = 1

        creds = {
            'user_id': user_id,
            'is_valid': False,
            'last_error': 'Previous refresh failed'
        }

        mock_memory.get_whoop_credentials = Mock(return_value=creds)

        result = service._refresh_user_token(user_id)

        assert result == "error"

    def test_refresh_user_token_refresh_fails(self, service, mock_memory):
        """Test when token refresh API call fails."""
        user_id = 1

        creds = {
            'user_id': user_id,
            'access_token': 'old_token',
            'expires_at': datetime.utcnow() - timedelta(minutes=10),
            'is_valid': True,
            'last_refreshed_at': datetime.utcnow() - timedelta(hours=1)
        }

        mock_memory.get_whoop_credentials = Mock(return_value=creds)
        mock_memory.refresh_whoop_token_if_needed = Mock(return_value=None)

        result = service._refresh_user_token(user_id)

        assert result == "error"

    def test_refresh_user_token_exception(self, service, mock_memory):
        """Test handling of exceptions during refresh."""
        user_id = 1

        mock_memory.get_whoop_credentials = Mock(side_effect=Exception("Database error"))

        result = service._refresh_user_token(user_id)

        assert result == "error"

    def test_get_whoop_users_success_with_real_db(self, service):
        """Test getting list of users - integration test requiring real DB setup."""
        # This is more of an integration test and would require a real database
        # In unit tests, we mock at a higher level (in refresh_all_tokens)
        # Skipping detailed DB mocking for _get_whoop_users
        pass

    def test_get_whoop_users_exception(self, service, mock_memory):
        """Test handling of database errors when getting users."""
        # Make engine.begin raise an exception
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(side_effect=Exception("Database error"))
        mock_memory.engine.begin = Mock(return_value=mock_conn)

        users = service._get_whoop_users()

        assert users == []

    def test_refresh_all_tokens_mixed_results(self, service, mock_memory):
        """Test refresh with mix of success, skip, and error."""
        # Mock _get_whoop_users to return 3 users
        with patch.object(service, '_get_whoop_users', return_value=[1, 2, 3]):
            # Mock different outcomes for each user
            with patch.object(service, '_refresh_user_token') as mock_refresh:
                mock_refresh.side_effect = ['refreshed', 'skipped', 'error']

                service.refresh_all_tokens()

                assert mock_refresh.call_count == 3

    def test_refresh_all_whoop_tokens_function(self, mock_memory):
        """Test standalone function for scheduler integration."""
        # Mock the service's methods
        with patch('core.proactive.whoop_token_refresh_service.WHOOPTokenRefreshService') as MockService:
            mock_instance = Mock()
            MockService.return_value = mock_instance

            # Call the function
            refresh_all_whoop_tokens(mock_memory)

            # Verify service was created with memory store
            MockService.assert_called_once_with(mock_memory)
            # Verify refresh_all_tokens was called
            mock_instance.refresh_all_tokens.assert_called_once()


class TestWHOOPTokenRefreshIntegration:
    """Integration tests for token refresh with real-ish scenarios."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory with more realistic behavior."""
        memory = Mock()
        memory.engine = Mock()
        memory.whoop_credentials = Mock()
        memory.whoop_credentials.c = Mock()
        memory.whoop_credentials.c.user_id = Mock()
        memory.whoop_credentials.c.is_valid = Mock()
        return memory

    def test_full_refresh_cycle(self, mock_memory):
        """Test complete refresh cycle from scheduler perspective."""
        # Setup: 2 users, one needs refresh, one doesn't
        user1_id = 1
        user2_id = 2

        # User 1: token expiring soon
        user1_creds_before = {
            'user_id': user1_id,
            'access_token': 'old_token_1',
            'expires_at': datetime.utcnow() + timedelta(minutes=3),  # Expiring soon
            'is_valid': True,
            'last_refreshed_at': datetime.utcnow() - timedelta(hours=1)
        }

        user1_creds_after = {
            'user_id': user1_id,
            'access_token': 'new_token_1',
            'expires_at': datetime.utcnow() + timedelta(hours=1),
            'is_valid': True,
            'last_refreshed_at': datetime.utcnow()
        }

        # User 2: token still fresh
        user2_creds = {
            'user_id': user2_id,
            'access_token': 'token_2',
            'expires_at': datetime.utcnow() + timedelta(minutes=30),
            'is_valid': True,
            'last_refreshed_at': datetime.utcnow() - timedelta(minutes=20)
        }

        # Mock get_whoop_credentials
        def get_creds(user_id):
            if user_id == user1_id:
                return user1_creds_before
            return user2_creds

        mock_memory.get_whoop_credentials = Mock(side_effect=get_creds)

        # Mock refresh_whoop_token_if_needed
        def refresh_if_needed(user_id):
            if user_id == user1_id:
                return user1_creds_after  # User 1 gets new token
            return user2_creds  # User 2 unchanged

        mock_memory.refresh_whoop_token_if_needed = Mock(side_effect=refresh_if_needed)

        # Execute
        service = WHOOPTokenRefreshService(mock_memory)

        # Mock _get_whoop_users to return both user IDs
        with patch.object(service, '_get_whoop_users', return_value=[user1_id, user2_id]):
            service.refresh_all_tokens()

        # Verify both users were processed
        assert mock_memory.get_whoop_credentials.call_count == 2
        assert mock_memory.refresh_whoop_token_if_needed.call_count == 2
