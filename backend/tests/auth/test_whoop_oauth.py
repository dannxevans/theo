"""
Unit tests for WHOOP OAuth functionality.

Tests OAuth 2.0 flow including authorization, token exchange,
and token refresh with proper scope handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from auth.whoop_oauth import WHOOPOAuth


class TestWHOOPOAuth:
    """Test WHOOP OAuth 2.0 implementation."""

    @pytest.fixture
    def mock_config(self):
        """Mock OAuth configuration."""
        return {
            'client_id': 'test_client_id',
            'client_secret': 'test_client_secret',
            'redirect_uri': 'http://localhost:1066/api/whoop/auth/callback'
        }

    @pytest.fixture
    def mock_memory_store(self, mock_config):
        """Mock memory store with OAuth config."""
        memory = Mock()
        memory.get_all = Mock(return_value={
            'whoop_client_id': mock_config['client_id'],
            'whoop_client_secret': mock_config['client_secret'],
            'whoop_redirect_uri': mock_config['redirect_uri']
        })
        return memory

    def test_scopes_include_offline(self):
        """Test that SCOPES includes 'offline' for refresh tokens."""
        assert 'offline' in WHOOPOAuth.SCOPES

    def test_scopes_include_required_permissions(self):
        """Test that SCOPES includes all required data permissions."""
        required_scopes = [
            'read:profile',
            'read:recovery',
            'read:sleep',
            'read:workout',
            'read:cycles',
            'offline'
        ]
        for scope in required_scopes:
            assert scope in WHOOPOAuth.SCOPES, f"Missing required scope: {scope}"

    def test_get_config_from_database(self, mock_memory_store):
        """Test config retrieval from database preferences."""
        config = WHOOPOAuth.get_config(user_id=1, memory_store=mock_memory_store)

        assert config['client_id'] == 'test_client_id'
        assert config['client_secret'] == 'test_client_secret'
        assert config['redirect_uri'] == 'http://localhost:1066/api/whoop/auth/callback'
        mock_memory_store.get_all.assert_called_once_with('1')

    def test_get_config_from_env(self):
        """Test config retrieval from environment variables."""
        with patch.dict('os.environ', {
            'WHOOP_CLIENT_ID': 'env_client_id',
            'WHOOP_CLIENT_SECRET': 'env_client_secret',
            'WHOOP_REDIRECT_URI': 'http://prod.example.com/callback'
        }):
            config = WHOOPOAuth.get_config()

            assert config['client_id'] == 'env_client_id'
            assert config['client_secret'] == 'env_client_secret'
            assert config['redirect_uri'] == 'http://prod.example.com/callback'

    def test_get_config_fallback_redirect_uri(self, mock_memory_store):
        """Test default redirect URI when not configured."""
        mock_memory_store.get_all = Mock(return_value={
            'whoop_client_id': 'test_id',
            'whoop_client_secret': 'test_secret'
        })

        config = WHOOPOAuth.get_config(user_id=1, memory_store=mock_memory_store)

        assert config['redirect_uri'] == 'http://localhost:1066/api/whoop/auth/callback'

    def test_is_configured_true(self, mock_memory_store):
        """Test is_configured returns True when credentials are set."""
        result = WHOOPOAuth.is_configured(user_id=1, memory_store=mock_memory_store)

        assert result is True

    def test_is_configured_false_no_client_id(self):
        """Test is_configured returns False when client_id missing."""
        memory = Mock()
        memory.get_all = Mock(return_value={
            'whoop_client_secret': 'test_secret'
        })

        result = WHOOPOAuth.is_configured(user_id=1, memory_store=memory)

        assert result is False

    def test_is_configured_false_no_client_secret(self):
        """Test is_configured returns False when client_secret missing."""
        memory = Mock()
        memory.get_all = Mock(return_value={
            'whoop_client_id': 'test_id'
        })

        result = WHOOPOAuth.is_configured(user_id=1, memory_store=memory)

        assert result is False

    def test_generate_pkce_pair(self):
        """Test PKCE code verifier and challenge generation."""
        verifier, challenge = WHOOPOAuth.generate_pkce_pair()

        assert len(verifier) > 0
        assert len(challenge) > 0
        assert verifier != challenge

    def test_get_authorization_url(self, mock_memory_store):
        """Test authorization URL generation."""
        state = 'test_state_token'

        result = WHOOPOAuth.get_authorization_url(state, user_id=1, memory_store=mock_memory_store)

        assert 'authorization_url' in result
        assert 'state' in result
        assert result['state'] == state
        assert 'client_id=test_client_id' in result['authorization_url']
        assert 'redirect_uri=' in result['authorization_url']
        assert 'response_type=code' in result['authorization_url']
        assert 'state=test_state_token' in result['authorization_url']

    def test_get_authorization_url_includes_all_scopes(self, mock_memory_store):
        """Test that authorization URL includes all required scopes."""
        state = 'test_state'

        result = WHOOPOAuth.get_authorization_url(state, user_id=1, memory_store=mock_memory_store)

        url = result['authorization_url']
        # Check that all scopes are in the URL (URL-encoded)
        # The URL encodes ":" as "%3A" and " " as "+"
        for scope in WHOOPOAuth.SCOPES:
            # Check for URL-encoded version of scope
            encoded_scope = scope.replace(':', '%3A')
            assert encoded_scope in url

    def test_get_authorization_url_not_configured(self):
        """Test authorization URL raises error when not configured."""
        memory = Mock()
        memory.get_all = Mock(return_value={})

        with pytest.raises(ValueError, match="WHOOP OAuth not configured"):
            WHOOPOAuth.get_authorization_url('state', user_id=1, memory_store=memory)

    @patch('auth.whoop_oauth.requests.post')
    def test_exchange_code_for_token_success(self, mock_post, mock_memory_store):
        """Test successful code exchange for access token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'scope': ' '.join(WHOOPOAuth.SCOPES)
        }
        mock_post.return_value = mock_response

        result = WHOOPOAuth.exchange_code_for_token(
            'auth_code',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is not None
        assert result['access_token'] == 'new_access_token'
        assert result['refresh_token'] == 'new_refresh_token'
        assert result['token_type'] == 'Bearer'
        assert result['expires_in'] == 3600
        assert 'expires_at' in result

    @patch('auth.whoop_oauth.requests.post')
    def test_exchange_code_for_token_failure(self, mock_post, mock_memory_store):
        """Test failed code exchange."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Invalid authorization code'
        }
        mock_post.return_value = mock_response

        result = WHOOPOAuth.exchange_code_for_token(
            'invalid_code',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is None

    @patch('auth.whoop_oauth.requests.post')
    def test_refresh_access_token_success(self, mock_post, mock_memory_store):
        """Test successful token refresh."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'refreshed_access_token',
            'refresh_token': 'new_refresh_token',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        result = WHOOPOAuth.refresh_access_token(
            'old_refresh_token',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is not None
        assert result['access_token'] == 'refreshed_access_token'
        assert result['refresh_token'] == 'new_refresh_token'
        assert 'expires_at' in result

    @patch('auth.whoop_oauth.requests.post')
    def test_refresh_access_token_includes_all_scopes(self, mock_post, mock_memory_store):
        """Test that token refresh includes all required scopes."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_token',
            'refresh_token': 'new_refresh',
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        WHOOPOAuth.refresh_access_token(
            'refresh_token',
            user_id=1,
            memory_store=mock_memory_store
        )

        # Verify the POST request was called with correct payload
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]['data']

        # CRITICAL TEST: Verify scope includes all scopes, not just "offline"
        assert payload['scope'] == ' '.join(WHOOPOAuth.SCOPES)
        assert 'read:profile' in payload['scope']
        assert 'read:recovery' in payload['scope']
        assert 'read:sleep' in payload['scope']
        assert 'read:workout' in payload['scope']
        assert 'read:cycles' in payload['scope']
        assert 'offline' in payload['scope']

    @patch('auth.whoop_oauth.requests.post')
    def test_refresh_access_token_failure(self, mock_post, mock_memory_store):
        """Test failed token refresh."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Refresh token expired'
        }
        mock_post.return_value = mock_response

        result = WHOOPOAuth.refresh_access_token(
            'expired_refresh_token',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is None

    @patch('auth.whoop_oauth.requests.post')
    def test_refresh_access_token_network_error(self, mock_post, mock_memory_store):
        """Test token refresh with network error."""
        mock_post.side_effect = Exception("Network error")

        result = WHOOPOAuth.refresh_access_token(
            'refresh_token',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is None

    @patch('auth.whoop_oauth.requests.post')
    def test_refresh_access_token_preserves_refresh_token(self, mock_post, mock_memory_store):
        """Test that refresh token is preserved if not rotated."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            # No refresh_token in response - should preserve original
            'token_type': 'Bearer',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        original_refresh_token = 'original_refresh_token'
        result = WHOOPOAuth.refresh_access_token(
            original_refresh_token,
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is not None
        assert result['refresh_token'] == original_refresh_token

    @patch('auth.whoop_oauth.requests.post')
    def test_revoke_token_success(self, mock_post, mock_memory_store):
        """Test successful token revocation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = WHOOPOAuth.revoke_token(
            'token_to_revoke',
            user_id=1,
            memory_store=mock_memory_store
        )

        assert result is True

    @patch('auth.whoop_oauth.requests.post')
    def test_revoke_token_already_invalid(self, mock_post, mock_memory_store):
        """Test revoking already invalid token still succeeds."""
        mock_response = Mock()
        mock_response.status_code = 400  # Token already invalid
        mock_post.return_value = mock_response

        result = WHOOPOAuth.revoke_token(
            'already_invalid_token',
            user_id=1,
            memory_store=mock_memory_store
        )

        # Should still return True for 4xx errors (client errors)
        assert result is True

    @patch('auth.whoop_oauth.requests.post')
    def test_revoke_token_network_error(self, mock_post, mock_memory_store):
        """Test revoke gracefully handles network errors."""
        mock_post.side_effect = Exception("Network error")

        result = WHOOPOAuth.revoke_token(
            'token',
            user_id=1,
            memory_store=mock_memory_store
        )

        # Should return True to allow local cleanup even if revoke fails
        assert result is True

    def test_get_configuration_instructions(self):
        """Test configuration instructions are provided."""
        instructions = WHOOPOAuth.get_configuration_instructions()

        assert 'developer.whoop.com' in instructions
        assert 'WHOOP_CLIENT_ID' in instructions
        assert 'WHOOP_CLIENT_SECRET' in instructions
        assert len(instructions) > 100
