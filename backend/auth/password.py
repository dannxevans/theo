"""
Authentication module for THEO.
Handles password hashing, session management, and user initialization.
"""
import bcrypt
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify


def hash_password(password):
    """
    Hash a password using bcrypt.
    Returns: bcrypt hash as string
    """
    # Convert password to bytes if it's a string
    if isinstance(password, str):
        password = password.encode('utf-8')

    # Generate salt and hash
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password, salt)

    # Return as string for database storage
    return password_hash.decode('utf-8')


def verify_password(password, stored_hash):
    """
    Verify a password against a bcrypt hash.
    Supports both legacy SHA-256 hashes and new bcrypt hashes for migration.
    """
    try:
        # Convert password to bytes if it's a string
        if isinstance(password, str):
            password = password.encode('utf-8')

        # Convert stored hash to bytes if it's a string
        if isinstance(stored_hash, str):
            # Check if this is a legacy SHA-256 hash (contains colon separator)
            if ':' in stored_hash:
                # Legacy SHA-256 verification for backward compatibility
                import hashlib
                salt, password_hash = stored_hash.split(":")
                test_hash = hashlib.sha256((password.decode('utf-8') + salt).encode()).hexdigest()
                return test_hash == password_hash

            stored_hash = stored_hash.encode('utf-8')

        # Bcrypt verification
        return bcrypt.checkpw(password, stored_hash)
    except (ValueError, AttributeError):
        return False


def generate_session_token():
    """
    Generate a secure random session token.
    """
    return secrets.token_urlsafe(32)


def init_default_user(memory):
    """
    Initialize the default admin user if no users exist.
    Username: admin
    Password: admin
    """
    # Check if any users exist
    with memory.engine.begin() as conn:
        from sqlalchemy import select, func
        user_count = conn.execute(
            select(func.count()).select_from(memory.users)
        ).scalar()

        if user_count == 0:
            # Create default admin user
            password_hash = hash_password("admin")
            memory.create_user("admin", password_hash, is_admin=True)
            print("[AUTH] Created default admin user (username: admin, password: admin)")
            print("[AUTH] IMPORTANT: Change the admin password immediately after login!")


def require_auth(memory):
    """
    Decorator to protect routes with authentication.
    Supports both session tokens and API keys in Authorization header.

    Session format: Authorization: Bearer <session_token>
    API key format: Authorization: Bearer theo_<random>

    Args:
        memory: MemoryStore instance or callable that returns MemoryStore instance
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Unauthorized"}), 401

            token = auth_header.split(" ")[1]

            # Resolve memory if it's a callable (for lazy loading)
            memory_store = memory() if callable(memory) else memory

            # Check if this is an API key (starts with "theo_")
            if token.startswith("theo_"):
                user = _validate_api_key_auth(memory_store, token)
                if not user:
                    return jsonify({"error": "Invalid or expired API key"}), 401
                request.auth_method = "api_key"
            else:
                # Session-based authentication (existing logic)
                user = _validate_session_auth(memory_store, token)
                if not user:
                    return jsonify({"error": "Invalid or expired session"}), 401
                request.auth_method = "session"

            # Attach user to request
            request.current_user = user

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def _validate_session_auth(memory, token):
    """
    Validate session-based authentication.

    Args:
        memory: MemoryStore instance
        token: Session token

    Returns:
        User dictionary if valid, None otherwise
    """
    # Validate session
    session = memory.get_auth_session(token)
    if not session:
        return None

    # Check if session expired
    if session["expires_at"] < datetime.utcnow():
        memory.delete_auth_session(token)
        return None

    # Get user
    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return None

    return user


def _validate_api_key_auth(memory, api_key):
    """
    Validate API key authentication.

    Args:
        memory: MemoryStore instance
        api_key: API key (format: theo_<random>)

    Returns:
        User dictionary if valid, None otherwise
    """
    from .api_keys import validate_api_key_format, verify_api_key, is_api_key_valid

    # Validate format
    if not validate_api_key_format(api_key):
        return None

    # We need to iterate through all API keys to find a match
    # This is necessary because we can't reverse the bcrypt hash
    # Note: In production, consider caching or optimizing this lookup
    with memory.engine.connect() as conn:
        from sqlalchemy import select
        rows = conn.execute(
            select(memory.api_keys)
        ).fetchall()

        for row in rows:
            # Check if this key hash matches the provided API key
            if verify_api_key(api_key, row.key_hash):
                # Found matching key, now validate it
                key_record = dict(row._mapping)

                # Check if key is valid (not revoked, not expired)
                if not is_api_key_valid(key_record):
                    return None

                # Get the user
                user = memory.get_user_by_id(key_record["user_id"])
                if not user or not user["is_enabled"]:
                    return None

                # Update last used timestamp
                memory.update_api_key_last_used(key_record["id"])

                return user

    # No matching key found
    return None
