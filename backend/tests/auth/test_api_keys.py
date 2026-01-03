"""
Unit tests for API key utilities.

Tests key generation, hashing, validation, and expiration checking.
"""
import pytest
from datetime import datetime, timedelta
from auth.api_keys import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    validate_api_key_format,
    is_api_key_expired,
    is_api_key_revoked,
    is_api_key_valid,
    API_KEY_PREFIX,
)


class TestKeyGeneration:
    """Test API key generation."""

    def test_generate_api_key_format(self):
        """Generated key should have correct format."""
        key = generate_api_key()
        assert key.startswith(API_KEY_PREFIX)
        assert len(key) == 69  # theo_ (5) + 64 hex chars

    def test_generate_api_key_uniqueness(self):
        """Each generated key should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100  # All unique

    def test_generate_api_key_valid_format(self):
        """Generated keys should pass format validation."""
        key = generate_api_key()
        assert validate_api_key_format(key)


class TestKeyHashing:
    """Test API key hashing and verification."""

    def test_hash_api_key(self):
        """Hashing should return non-empty string."""
        key = generate_api_key()
        key_hash = hash_api_key(key)
        assert isinstance(key_hash, str)
        assert len(key_hash) > 0
        assert key_hash != key  # Should not be plaintext

    def test_verify_api_key_valid(self):
        """Should verify correct key."""
        key = generate_api_key()
        key_hash = hash_api_key(key)
        assert verify_api_key(key, key_hash)

    def test_verify_api_key_invalid(self):
        """Should reject incorrect key."""
        key1 = generate_api_key()
        key2 = generate_api_key()
        key_hash = hash_api_key(key1)
        assert not verify_api_key(key2, key_hash)

    def test_verify_api_key_wrong_hash(self):
        """Should reject malformed hash."""
        key = generate_api_key()
        assert not verify_api_key(key, "invalid_hash")

    def test_hash_includes_prefix(self):
        """Hash should include the theo_ prefix."""
        key = generate_api_key()
        key_hash = hash_api_key(key)
        # Verify full key including prefix
        assert verify_api_key(key, key_hash)
        # Verify without prefix should fail
        key_without_prefix = key.replace(API_KEY_PREFIX, "")
        assert not verify_api_key(key_without_prefix, key_hash)


class TestFormatValidation:
    """Test API key format validation."""

    def test_validate_valid_format(self):
        """Should accept valid format."""
        key = generate_api_key()
        assert validate_api_key_format(key)

    def test_validate_wrong_prefix(self):
        """Should reject wrong prefix."""
        key = "wrong_" + "a" * 64
        assert not validate_api_key_format(key)

    def test_validate_too_short(self):
        """Should reject too short key."""
        key = "theo_abc123"
        assert not validate_api_key_format(key)

    def test_validate_too_long(self):
        """Should reject too long key."""
        key = "theo_" + "a" * 100
        assert not validate_api_key_format(key)

    def test_validate_invalid_chars(self):
        """Should reject non-hex characters."""
        key = "theo_" + "z" * 64  # z is not a hex char
        assert not validate_api_key_format(key)

    def test_validate_uppercase(self):
        """Should reject uppercase (must be lowercase hex)."""
        key = "theo_" + "A" * 64
        assert not validate_api_key_format(key)

    def test_validate_none(self):
        """Should reject None."""
        assert not validate_api_key_format(None)

    def test_validate_empty_string(self):
        """Should reject empty string."""
        assert not validate_api_key_format("")

    def test_validate_non_string(self):
        """Should reject non-string input."""
        assert not validate_api_key_format(123)
        assert not validate_api_key_format([])


class TestKeyExpiration:
    """Test API key expiration checking."""

    def test_is_expired_future_date(self):
        """Should not be expired if expires_at is in future."""
        record = {
            "expires_at": datetime.utcnow() + timedelta(days=30)
        }
        assert not is_api_key_expired(record)

    def test_is_expired_past_date(self):
        """Should be expired if expires_at is in past."""
        record = {
            "expires_at": datetime.utcnow() - timedelta(days=1)
        }
        assert is_api_key_expired(record)

    def test_is_expired_none(self):
        """Should not be expired if no expiration date."""
        record = {
            "expires_at": None
        }
        assert not is_api_key_expired(record)

    def test_is_expired_missing_key(self):
        """Should not be expired if expires_at key missing."""
        record = {}
        assert not is_api_key_expired(record)

    def test_is_expired_string_date(self):
        """Should handle ISO string dates."""
        future_date = (datetime.utcnow() + timedelta(days=30)).isoformat()
        past_date = (datetime.utcnow() - timedelta(days=1)).isoformat()

        assert not is_api_key_expired({"expires_at": future_date})
        assert is_api_key_expired({"expires_at": past_date})


class TestKeyRevocation:
    """Test API key revocation checking."""

    def test_is_revoked_true(self):
        """Should detect revoked key."""
        record = {"is_revoked": True}
        assert is_api_key_revoked(record)

    def test_is_revoked_false(self):
        """Should detect non-revoked key."""
        record = {"is_revoked": False}
        assert not is_api_key_revoked(record)

    def test_is_revoked_missing(self):
        """Should default to not revoked if field missing."""
        record = {}
        assert not is_api_key_revoked(record)

    def test_is_revoked_truthy_values(self):
        """Should handle truthy values."""
        assert is_api_key_revoked({"is_revoked": 1})
        assert is_api_key_revoked({"is_revoked": "true"})


class TestKeyValidity:
    """Test combined API key validity checking."""

    def test_is_valid_active_key(self):
        """Should be valid if not revoked and not expired."""
        record = {
            "is_revoked": False,
            "expires_at": datetime.utcnow() + timedelta(days=30)
        }
        assert is_api_key_valid(record)

    def test_is_valid_never_expires(self):
        """Should be valid if no expiration date."""
        record = {
            "is_revoked": False,
            "expires_at": None
        }
        assert is_api_key_valid(record)

    def test_is_invalid_revoked(self):
        """Should be invalid if revoked."""
        record = {
            "is_revoked": True,
            "expires_at": datetime.utcnow() + timedelta(days=30)
        }
        assert not is_api_key_valid(record)

    def test_is_invalid_expired(self):
        """Should be invalid if expired."""
        record = {
            "is_revoked": False,
            "expires_at": datetime.utcnow() - timedelta(days=1)
        }
        assert not is_api_key_valid(record)

    def test_is_invalid_revoked_and_expired(self):
        """Should be invalid if both revoked and expired."""
        record = {
            "is_revoked": True,
            "expires_at": datetime.utcnow() - timedelta(days=1)
        }
        assert not is_api_key_valid(record)
