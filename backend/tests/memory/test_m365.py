"""
Tests for M365 operations.

Tests M365 credential storage and management.
"""

import pytest
from datetime import datetime, timedelta


def test_store_m365_credentials(memory, user_fixture):
    """Test store M365 credentials."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="access-token-123",
        refresh_token="refresh-token-123",
        expires_at=expires_at,
        scope="Calendars.ReadWrite Mail.Read",
        tenant_id="tenant-123",
        upn="user@example.com"
    )

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds is not None
    assert creds["access_token"] == "access-token-123"
    assert creds["user_principal_name"] == "user@example.com"


def test_store_m365_credentials_minimal(memory, user_fixture):
    """Test store M365 credentials with minimal fields."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds is not None


def test_store_m365_credentials_update(memory, user_fixture):
    """Test update existing M365 credentials."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # Store initial credentials
    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="old-token",
        refresh_token="old-refresh",
        expires_at=expires_at
    )

    # Update credentials
    new_expires_at = datetime.utcnow() + timedelta(hours=2)
    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="new-token",
        refresh_token="new-refresh",
        expires_at=new_expires_at
    )

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["access_token"] == "new-token"


def test_get_m365_credentials(memory, user_fixture):
    """Test get M365 credentials."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["user_id"] == user_fixture["id"]
    assert creds["is_valid"] is True


def test_get_m365_credentials_nonexistent(memory, user_fixture):
    """Test get M365 credentials when none exist."""
    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds is None


def test_invalidate_m365_credentials(memory, user_fixture):
    """Test invalidate M365 credentials."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    memory.invalidate_m365_credentials(user_fixture["id"], error="Token expired")

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["is_valid"] is False
    assert creds["last_error"] == "Token expired"


def test_delete_m365_credentials(memory, user_fixture):
    """Test delete M365 credentials."""
    expires_at = datetime.utcnow() + timedelta(hours=1)

    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    memory.delete_m365_credentials(user_fixture["id"])

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds is None


def test_m365_credentials_lifecycle(memory, user_fixture):
    """Test complete M365 credentials lifecycle."""
    # Store credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="access-token",
        refresh_token="refresh-token",
        expires_at=expires_at,
        scope="Calendars.ReadWrite",
        upn="user@example.com"
    )

    # Verify stored
    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["is_valid"] is True

    # Invalidate
    memory.invalidate_m365_credentials(user_fixture["id"], error="Auth error")
    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["is_valid"] is False

    # Refresh (store new token)
    new_expires_at = datetime.utcnow() + timedelta(hours=2)
    memory.store_m365_credentials(
        user_id=user_fixture["id"],
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        expires_at=new_expires_at
    )

    creds = memory.get_m365_credentials(user_fixture["id"])
    assert creds["is_valid"] is True
    assert creds["access_token"] == "new-access-token"

    # Delete
    memory.delete_m365_credentials(user_fixture["id"])
    assert memory.get_m365_credentials(user_fixture["id"]) is None
