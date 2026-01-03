"""
API Key authentication utilities for THEO.

Provides functions for generating, hashing, and validating API keys
for programmatic access (Siri Shortcuts, iOS automation, external tools).
"""
import secrets
import re
from datetime import datetime
from .password import hash_password, verify_password


# API Key format: theo_<64 hex characters>
# Total length: 5 (prefix) + 64 (random) = 69 characters
# Entropy: 256 bits (32 bytes)
API_KEY_PREFIX = "theo_"
API_KEY_RANDOM_BYTES = 32  # 256 bits of entropy
API_KEY_PATTERN = re.compile(r"^theo_[a-f0-9]{64}$")


def generate_api_key() -> str:
    """
    Generate a cryptographically secure API key.

    Format: theo_<64-hex-chars>
    Example: theo_a1b2c3d4e5f6...

    Returns:
        str: A new API key with format theo_<random>

    Example:
        >>> key = generate_api_key()
        >>> print(key[:10])
        theo_a1b2c
        >>> len(key)
        69
    """
    random_hex = secrets.token_hex(API_KEY_RANDOM_BYTES)
    return f"{API_KEY_PREFIX}{random_hex}"


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt (same as passwords).

    The full API key (including theo_ prefix) is hashed for storage.
    Never store API keys in plaintext.

    Args:
        api_key: The API key to hash (format: theo_<random>)

    Returns:
        str: Bcrypt hash (format: salt:hash)

    Example:
        >>> key = generate_api_key()
        >>> key_hash = hash_api_key(key)
        >>> print(len(key_hash) > 40)
        True
    """
    return hash_password(api_key)


def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify an API key against a stored hash.

    Args:
        api_key: The API key to verify (format: theo_<random>)
        stored_hash: The bcrypt hash from database

    Returns:
        bool: True if key matches hash, False otherwise

    Example:
        >>> key = generate_api_key()
        >>> key_hash = hash_api_key(key)
        >>> verify_api_key(key, key_hash)
        True
        >>> verify_api_key("wrong_key", key_hash)
        False
    """
    return verify_password(api_key, stored_hash)


def validate_api_key_format(api_key: str) -> bool:
    """
    Validate that an API key matches the expected format.

    Format: theo_<64 lowercase hex characters>
    Total length: 69 characters

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if format is valid, False otherwise

    Example:
        >>> validate_api_key_format("theo_" + "a" * 64)
        True
        >>> validate_api_key_format("invalid")
        False
        >>> validate_api_key_format("theo_short")
        False
    """
    if not api_key or not isinstance(api_key, str):
        return False

    return bool(API_KEY_PATTERN.match(api_key))


def is_api_key_expired(api_key_record: dict) -> bool:
    """
    Check if an API key has expired.

    Args:
        api_key_record: Dictionary with 'expires_at' field (datetime or None)

    Returns:
        bool: True if expired, False if still valid or no expiration

    Example:
        >>> from datetime import datetime, timedelta
        >>> # Expired key
        >>> record = {"expires_at": datetime.utcnow() - timedelta(days=1)}
        >>> is_api_key_expired(record)
        True
        >>> # Valid key
        >>> record = {"expires_at": datetime.utcnow() + timedelta(days=30)}
        >>> is_api_key_expired(record)
        False
        >>> # Never expires
        >>> record = {"expires_at": None}
        >>> is_api_key_expired(record)
        False
    """
    expires_at = api_key_record.get("expires_at")

    if not expires_at:
        # No expiration date means key never expires
        return False

    # Handle both datetime objects and string timestamps
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # If we can't parse the date, assume not expired (safe default)
            return False

    return expires_at < datetime.utcnow()


def is_api_key_revoked(api_key_record: dict) -> bool:
    """
    Check if an API key has been revoked.

    Args:
        api_key_record: Dictionary with 'is_revoked' field

    Returns:
        bool: True if revoked, False otherwise

    Example:
        >>> record = {"is_revoked": True}
        >>> is_api_key_revoked(record)
        True
        >>> record = {"is_revoked": False}
        >>> is_api_key_revoked(record)
        False
    """
    return bool(api_key_record.get("is_revoked", False))


def is_api_key_valid(api_key_record: dict) -> bool:
    """
    Check if an API key is valid (not expired and not revoked).

    Args:
        api_key_record: Dictionary with key metadata

    Returns:
        bool: True if valid, False otherwise

    Example:
        >>> from datetime import datetime, timedelta
        >>> # Valid key
        >>> record = {
        ...     "is_revoked": False,
        ...     "expires_at": datetime.utcnow() + timedelta(days=30)
        ... }
        >>> is_api_key_valid(record)
        True
        >>> # Revoked key
        >>> record = {"is_revoked": True, "expires_at": None}
        >>> is_api_key_valid(record)
        False
    """
    if is_api_key_revoked(api_key_record):
        return False

    if is_api_key_expired(api_key_record):
        return False

    return True
