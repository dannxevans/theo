"""
Authentication module for THEO.
Handles password hashing, session management, and user initialization.
"""
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify


def hash_password(password):
    """
    Hash a password using SHA-256 with a salt.
    Returns: salted_hash
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"


def verify_password(password, stored_hash):
    """
    Verify a password against a stored hash.
    """
    try:
        salt, password_hash = stored_hash.split(":")
        test_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return test_hash == password_hash
    except ValueError:
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
    Checks for valid session token in Authorization header.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Unauthorized"}), 401

            token = auth_header.split(" ")[1]

            # Validate session
            session = memory.get_auth_session(token)
            if not session:
                return jsonify({"error": "Invalid session"}), 401

            # Check if session expired
            if session["expires_at"] < datetime.utcnow():
                memory.delete_auth_session(token)
                return jsonify({"error": "Session expired"}), 401

            # Get user
            user = memory.get_user_by_id(session["user_id"])
            if not user or not user["is_enabled"]:
                return jsonify({"error": "User disabled"}), 401

            # Attach user to request
            request.current_user = user

            return f(*args, **kwargs)

        return decorated_function
    return decorator
