"""
Tests for user_utils module (User ID Normalization)
"""

import pytest
import logging
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from core.user_utils import (
    normalize_user_id,
    ensure_user_exists,
    get_user_id_from_token,
    DEFAULT_USER_ID,
)


class TestNormalizeUserId:
    """Tests for normalize_user_id function"""

    def test_integer_passthrough(self):
        """Integer user_ids should pass through unchanged"""
        assert normalize_user_id(1) == 1
        assert normalize_user_id(42) == 42
        assert normalize_user_id(999) == 999

    def test_legacy_local_string(self):
        """'local' string should convert to DEFAULT_USER_ID"""
        assert normalize_user_id("local") == DEFAULT_USER_ID
        assert normalize_user_id("LOCAL") == DEFAULT_USER_ID  # Case insensitive
        assert normalize_user_id("  local  ") == DEFAULT_USER_ID  # With whitespace

    def test_string_integer_parsing(self):
        """String integers should be parsed to int"""
        assert normalize_user_id("1") == 1
        assert normalize_user_id("42") == 42
        assert normalize_user_id("999") == 999
        assert normalize_user_id("  123  ") == 123  # With whitespace

    def test_none_uses_default(self):
        """None should use the default value"""
        assert normalize_user_id(None) == DEFAULT_USER_ID
        assert normalize_user_id(None, default=5) == 5

    def test_empty_string_uses_default(self):
        """Empty string should use the default value"""
        assert normalize_user_id("") == DEFAULT_USER_ID
        assert normalize_user_id("   ") == DEFAULT_USER_ID  # Whitespace only
        assert normalize_user_id("", default=10) == 10

    def test_invalid_string_uses_default(self, caplog):
        """Invalid string should log warning and use default"""
        with caplog.at_level(logging.WARNING):
            result = normalize_user_id("not_a_number")
            assert result == DEFAULT_USER_ID
            assert "Invalid string user_id" in caplog.text

    def test_invalid_type_uses_default(self, caplog):
        """Invalid types should log warning and use default"""
        with caplog.at_level(logging.WARNING):
            # Test with list
            result = normalize_user_id([1, 2, 3])
            assert result == DEFAULT_USER_ID
            assert "Unexpected type" in caplog.text

        caplog.clear()

        with caplog.at_level(logging.WARNING):
            # Test with dict
            result = normalize_user_id({"id": 1})
            assert result == DEFAULT_USER_ID
            assert "Unexpected type" in caplog.text

    def test_custom_default(self):
        """Custom default should be respected"""
        assert normalize_user_id(None, default=5) == 5
        assert normalize_user_id("", default=10) == 10
        assert normalize_user_id("invalid", default=99) == 99

    def test_debug_logging(self, caplog):
        """Function should log debug messages for conversions"""
        with caplog.at_level(logging.DEBUG):
            normalize_user_id(1)
            assert "Integer passthrough" in caplog.text

        caplog.clear()

        with caplog.at_level(logging.DEBUG):
            normalize_user_id("local")
            assert "'local'" in caplog.text

        caplog.clear()

        with caplog.at_level(logging.DEBUG):
            normalize_user_id(None)
            assert "None" in caplog.text

    def test_zero_user_id(self):
        """Zero should be valid (though unlikely in practice)"""
        assert normalize_user_id(0) == 0
        assert normalize_user_id("0") == 0

    def test_negative_user_id(self):
        """Negative IDs should be parsed (though invalid in practice)"""
        # The function doesn't validate that user_id is positive,
        # only that it can be converted to int
        assert normalize_user_id(-1) == -1
        assert normalize_user_id("-5") == -5


class TestEnsureUserExists:
    """Tests for ensure_user_exists function"""

    def test_database_error(self, caplog):
        """Should return False and log error on database exception"""
        mock_memory = MagicMock()
        mock_memory.engine.connect.side_effect = Exception("Database error")

        with caplog.at_level(logging.ERROR):
            result = ensure_user_exists(mock_memory, 1)
            assert result is False
            assert "Error checking user existence" in caplog.text

    # Note: Full database interaction tests are in TestUserUtilsIntegration
    # These require actual database fixtures and will be validated during
    # the full test suite run after migration


class TestGetUserIdFromToken:
    """Tests for get_user_id_from_token function"""

    def test_no_token_returns_default(self, caplog):
        """Should return DEFAULT_USER_ID when no token provided"""
        mock_memory = MagicMock()

        with caplog.at_level(logging.DEBUG):
            result = get_user_id_from_token(mock_memory, None)
            assert result == DEFAULT_USER_ID
            assert "No token provided" in caplog.text

    def test_valid_token_returns_user_id(self, caplog):
        """Should extract user_id from valid token"""
        mock_memory = MagicMock()
        future_time = datetime.utcnow() + timedelta(hours=1)

        mock_memory.get_auth_session.return_value = {
            "user_id": 42,
            "expires_at": future_time,
        }

        with caplog.at_level(logging.DEBUG):
            result = get_user_id_from_token(mock_memory, "valid_token_123")
            assert result == 42
            assert "Valid token for user_id: 42" in caplog.text

    def test_expired_token_returns_default(self, caplog):
        """Should return DEFAULT_USER_ID for expired token"""
        mock_memory = MagicMock()
        past_time = datetime.utcnow() - timedelta(hours=1)

        mock_memory.get_auth_session.return_value = {
            "user_id": 42,
            "expires_at": past_time,
        }

        with caplog.at_level(logging.DEBUG):
            result = get_user_id_from_token(mock_memory, "expired_token")
            assert result == DEFAULT_USER_ID
            assert "Token expired" in caplog.text

    def test_invalid_session_returns_default(self, caplog):
        """Should return DEFAULT_USER_ID for invalid session"""
        mock_memory = MagicMock()
        mock_memory.get_auth_session.return_value = None

        with caplog.at_level(logging.DEBUG):
            result = get_user_id_from_token(mock_memory, "invalid_token")
            assert result == DEFAULT_USER_ID
            assert "Invalid session" in caplog.text

    def test_session_without_user_id(self, caplog):
        """Should return DEFAULT_USER_ID if session lacks user_id"""
        mock_memory = MagicMock()
        future_time = datetime.utcnow() + timedelta(hours=1)

        mock_memory.get_auth_session.return_value = {
            "expires_at": future_time,
            # Missing user_id
        }

        result = get_user_id_from_token(mock_memory, "token_without_user")
        assert result == DEFAULT_USER_ID

    def test_session_with_string_user_id(self, caplog):
        """Should normalize string user_id from session"""
        mock_memory = MagicMock()
        future_time = datetime.utcnow() + timedelta(hours=1)

        mock_memory.get_auth_session.return_value = {
            "user_id": "42",  # String instead of int
            "expires_at": future_time,
        }

        with caplog.at_level(logging.DEBUG):
            result = get_user_id_from_token(mock_memory, "token_with_string_id")
            assert result == 42
            assert isinstance(result, int)

    def test_session_with_local_user_id(self, caplog):
        """Should convert 'local' user_id to DEFAULT_USER_ID"""
        mock_memory = MagicMock()
        future_time = datetime.utcnow() + timedelta(hours=1)

        mock_memory.get_auth_session.return_value = {
            "user_id": "local",
            "expires_at": future_time,
        }

        result = get_user_id_from_token(mock_memory, "token_with_local")
        assert result == DEFAULT_USER_ID

    def test_exception_handling(self, caplog):
        """Should handle exceptions gracefully and return DEFAULT_USER_ID"""
        mock_memory = MagicMock()
        mock_memory.get_auth_session.side_effect = Exception("Database error")

        with caplog.at_level(logging.ERROR):
            result = get_user_id_from_token(mock_memory, "problematic_token")
            assert result == DEFAULT_USER_ID
            assert "Error extracting user_id from token" in caplog.text


class TestConstants:
    """Tests for module constants"""

    def test_default_user_id_is_one(self):
        """DEFAULT_USER_ID should be 1 (the admin/local user)"""
        assert DEFAULT_USER_ID == 1


# Integration test (optional, requires actual database)
@pytest.mark.integration
class TestUserUtilsIntegration:
    """Integration tests with actual database (optional)"""

    @pytest.fixture
    def populated_memory(self):
        """Create a temporary in-memory database for integration tests"""
        from core.memory.store import MemoryStore
        from auth import hash_password
        import tempfile
        import os

        # Create temporary database
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            # MemoryStore takes db_url, not db_path
            db_url = f"sqlite:///{db_path}"
            memory = MemoryStore(db_url=db_url)

            # Create test user with id=1
            memory.create_user("admin", hash_password("test123"), is_admin=True)

            yield memory
        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_normalize_and_verify_user(self, populated_memory):
        """Test normalization with actual database verification"""
        user_id = normalize_user_id("local")
        assert user_id == 1

        # Verify user exists in database
        exists = ensure_user_exists(populated_memory, user_id)
        assert exists is True

    def test_verify_nonexistent_user(self, populated_memory):
        """Test verification fails for nonexistent user"""
        exists = ensure_user_exists(populated_memory, 99999)
        assert exists is False
