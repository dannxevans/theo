"""
Authentication routes.

Provides login, logout, session verification, and password management endpoints.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from auth import verify_password, hash_password, generate_session_token
from auth.password_utils import validate_password_strength

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login endpoint.
    Expects: { "username": "...", "password": "..." }
    Returns: { "token": "..." } on success
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    # Get user
    user = memory.get_user_by_username(username)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # Check if user is enabled
    if not user["is_enabled"]:
        return jsonify({"error": "Account disabled"}), 401

    # Verify password
    if not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create session token
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=Config.SESSION_EXPIRY_DAYS)

    memory.create_auth_session(token, user["id"], expires_at)

    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """
    Logout endpoint.
    Expects: Authorization: Bearer <token>
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "No token provided"}), 400

    token = auth_header.split(" ")[1]
    memory.delete_auth_session(token)

    return jsonify({"status": "ok"})


@auth_bp.route("/verify", methods=["GET"])
def verify_session():
    """
    Verify if current session is valid.
    Expects: Authorization: Bearer <token>
    Returns: { "valid": true, "user": {...} } or { "valid": false }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"valid": False})

    token = auth_header.split(" ")[1]

    # Get session
    session = memory.get_auth_session(token)
    if not session:
        return jsonify({"valid": False})

    now = datetime.utcnow()

    # Check absolute expiration
    if session["expires_at"] < now:
        memory.delete_auth_session(token)
        return jsonify({"valid": False})

    # Check inactivity timeout
    # Get user's session timeout preference (defaults to 8 hours)
    user_id = session["user_id"]
    timeout_hours_str = memory.get_user_preference(user_id, "session_timeout", str(Config.DEFAULT_SESSION_INACTIVITY_HOURS))
    try:
        timeout_hours = int(timeout_hours_str)
    except (ValueError, TypeError):
        timeout_hours = Config.DEFAULT_SESSION_INACTIVITY_HOURS

    last_activity = session.get("last_activity_at") or session.get("created_at")
    inactivity_threshold = timedelta(hours=timeout_hours)
    if last_activity and (now - last_activity) > inactivity_threshold:
        memory.delete_auth_session(token)
        return jsonify({"valid": False, "reason": "inactivity_timeout"})

    # Get user
    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"valid": False})

    # Update last activity timestamp
    memory.update_session_activity(token)

    return jsonify({
        "valid": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }
    })


@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    """
    Change password endpoint.
    Expects: Authorization: Bearer <token>
    Body: { "current_password": "...", "new_password": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Verify session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get passwords from request
    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"error": "Current and new password required"}), 400

    # Verify current password
    if not verify_password(current_password, user["password_hash"]):
        return jsonify({"error": "Current password incorrect"}), 401

    # Validate new password strength
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        return jsonify({"error": error_msg}), 400

    # Update password
    new_hash = hash_password(new_password)
    memory.update_user_password(user["id"], new_hash)

    return jsonify({"status": "ok"})
