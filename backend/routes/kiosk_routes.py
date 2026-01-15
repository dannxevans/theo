"""
Kiosk Mode Routes
Handles kiosk mode access validation.
"""
from flask import Blueprint, jsonify, request
from datetime import datetime

kiosk_bp = Blueprint('kiosk', __name__)


@kiosk_bp.route('/api/kiosk/check-access', methods=['GET'])
def check_kiosk_access():
    """
    Check if user can access kiosk mode.
    Only accessible from Personal mode.

    Returns:
        200: Access allowed
        403: Access denied (not in Personal mode)
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check current mode
    mode_config = memory.get_user_mode(user["id"])
    current_mode = mode_config.get("active_mode", "personal")

    if current_mode != "personal":
        return jsonify({
            "allowed": False,
            "reason": "Kiosk mode is only accessible from Personal mode. Please switch to Personal mode first."
        }), 403

    return jsonify({"allowed": True}), 200
