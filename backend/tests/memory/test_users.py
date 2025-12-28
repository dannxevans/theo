"""
Tests for user operations.

Tests user management, authentication sessions, and debug settings.
"""

import pytest
from datetime import datetime, timedelta


def test_create_user(memory):
    """Test create new user."""
    from auth import hash_password

    password_hash = hash_password("password123")
    user_id = memory.create_user("testuser", password_hash, is_admin=False)

    assert user_id is not None

    user = memory.get_user_by_id(user_id)
    assert user["username"] == "testuser"
    assert user["is_admin"] is False


def test_create_user_admin(memory):
    """Test create admin user."""
    from auth import hash_password

    password_hash = hash_password("adminpass")
    user_id = memory.create_user("admin", password_hash, is_admin=True)

    user = memory.get_user_by_id(user_id)
    assert user["is_admin"] is True


def test_get_user_by_username(memory):
    """Test get user by username."""
    from auth import hash_password

    password_hash = hash_password("password")
    memory.create_user("findme", password_hash)

    user = memory.get_user_by_username("findme")
    assert user is not None
    assert user["username"] == "findme"


def test_get_user_by_username_nonexistent(memory):
    """Test get nonexistent user by username."""
    user = memory.get_user_by_username("nonexistent")
    assert user is None


def test_get_user_by_id(memory):
    """Test get user by ID."""
    from auth import hash_password

    password_hash = hash_password("password")
    user_id = memory.create_user("test", password_hash)

    user = memory.get_user_by_id(user_id)
    assert user is not None
    assert user["id"] == user_id


def test_get_user_by_id_nonexistent(memory):
    """Test get nonexistent user by ID."""
    user = memory.get_user_by_id(99999)
    assert user is None


def test_update_user_password(memory):
    """Test update user password."""
    from auth import hash_password, verify_password

    old_hash = hash_password("oldpass")
    user_id = memory.create_user("test", old_hash)

    new_hash = hash_password("newpass")
    memory.update_user_password(user_id, new_hash)

    user = memory.get_user_by_id(user_id)
    assert verify_password("newpass", user["password_hash"])


def test_disable_user(memory):
    """Test disable user account."""
    from auth import hash_password

    password_hash = hash_password("password")
    user_id = memory.create_user("test", password_hash)

    memory.disable_user(user_id)

    user = memory.get_user_by_id(user_id)
    assert user["is_enabled"] is False


def test_create_auth_session(memory, user_fixture):
    """Test create authentication session."""
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)

    memory.create_auth_session(token, user_fixture["id"], expires_at)

    session = memory.get_auth_session(token)
    assert session is not None
    assert session["user_id"] == user_fixture["id"]


def test_get_auth_session(memory, user_fixture):
    """Test get authentication session."""
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, user_fixture["id"], expires_at)

    session = memory.get_auth_session(token)
    assert session["id"] == token
    assert session["expires_at"] > datetime.utcnow()


def test_get_auth_session_nonexistent(memory):
    """Test get nonexistent session."""
    session = memory.get_auth_session("invalid-token")
    assert session is None


def test_delete_auth_session(memory, user_fixture):
    """Test delete authentication session."""
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, user_fixture["id"], expires_at)

    memory.delete_auth_session(token)

    session = memory.get_auth_session(token)
    assert session is None


def test_cleanup_expired_sessions(memory, user_fixture):
    """Test cleanup expired sessions."""
    from auth import generate_session_token

    # Create expired session
    expired_token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(expired_token, user_fixture["id"], expires_at)

    # Create valid session
    valid_token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(valid_token, user_fixture["id"], expires_at)

    # Cleanup
    memory.cleanup_expired_sessions()

    # Expired should be gone
    assert memory.get_auth_session(expired_token) is None

    # Valid should remain
    assert memory.get_auth_session(valid_token) is not None


def test_set_debug_enabled(memory, user_fixture):
    """Test set debug enabled."""
    memory.set_debug_enabled(user_fixture["id"], True)

    enabled = memory.is_debug_enabled(user_fixture["id"])
    assert enabled is True


def test_set_debug_disabled(memory, user_fixture):
    """Test set debug disabled."""
    memory.set_debug_enabled(user_fixture["id"], False)

    enabled = memory.is_debug_enabled(user_fixture["id"])
    assert enabled is False


def test_is_debug_enabled_default(memory, user_fixture):
    """Test debug is disabled by default."""
    enabled = memory.is_debug_enabled(user_fixture["id"])
    assert enabled is False


def test_user_authentication_flow(memory):
    """Test complete user authentication flow."""
    from auth import hash_password, verify_password, generate_session_token

    # Create user
    password = "securepassword"
    password_hash = hash_password(password)
    user_id = memory.create_user("authtest", password_hash)

    # Verify password
    user = memory.get_user_by_username("authtest")
    assert verify_password(password, user["password_hash"])

    # Create session
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, user_id, expires_at)

    # Verify session
    session = memory.get_auth_session(token)
    assert session["user_id"] == user_id

    # Logout (delete session)
    memory.delete_auth_session(token)
    assert memory.get_auth_session(token) is None
