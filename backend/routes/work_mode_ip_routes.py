"""
Work Mode IP restriction routes.

Provides endpoints for managing IP-based access control for Work Mode:
- GET /api/work-mode-ip/config - Get IP restriction configuration (admin only)
- POST /api/work-mode-ip/config - Update IP restriction configuration (admin only)
- GET /api/work-mode-ip/check - Check if current IP is allowed
"""

from flask import Blueprint, jsonify, request
from datetime import datetime

work_mode_ip_bp = Blueprint('work_mode_ip', __name__, url_prefix='/api/work-mode-ip')


def require_auth():
    """
    Helper function to validate authentication and return user.

    Returns:
        Tuple of (user_dict, memory_store) or (error_response, status_code)
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return (jsonify({"error": "Unauthorized"}), 401)

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return (jsonify({"error": "Invalid session"}), 401)

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return (jsonify({"error": "User not found"}), 401)

    return (user, memory)


@work_mode_ip_bp.route("/config", methods=["GET"])
def get_ip_config():
    """
    Get IP restriction configuration.
    Requires: Authorization header with bearer token (admin only)
    Returns: { "enabled": bool, "allowed_ranges": list[str] }
    """
    auth_result = require_auth()
    if len(auth_result) == 2 and not isinstance(auth_result[0], dict):  # Error response
        return auth_result

    user, memory = auth_result

    # Check if user is admin
    if not user.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Get configuration
    config = memory.get_work_mode_ip_config()

    return jsonify(config)


@work_mode_ip_bp.route("/config", methods=["POST"])
def update_ip_config():
    """
    Update IP restriction configuration.
    Requires: Authorization header with bearer token (admin only)
    Request body: { "enabled": bool, "allowed_ranges": list[str] }
    Returns: { "enabled": bool, "allowed_ranges": list[str] }
    """
    auth_result = require_auth()
    if len(auth_result) == 2 and not isinstance(auth_result[0], dict):  # Error response
        return auth_result

    user, memory = auth_result

    # Check if user is admin
    if not user.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403

    # Get request data
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Missing request body"}), 400

    enabled = data.get("enabled")
    allowed_ranges = data.get("allowed_ranges", [])

    # Validate types
    if not isinstance(enabled, bool):
        return jsonify({"error": "enabled must be a boolean"}), 400

    if not isinstance(allowed_ranges, list):
        return jsonify({"error": "allowed_ranges must be a list"}), 400

    # Validate CIDR ranges
    try:
        config = memory.update_work_mode_ip_config(enabled, allowed_ranges)
        return jsonify(config)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to update configuration: {str(e)}"}), 500


@work_mode_ip_bp.route("/check", methods=["GET"])
def check_ip():
    """
    Check if current IP is allowed for Work Mode access.
    Requires: Authorization header with bearer token
    Returns: { "allowed": bool, "current_ip": str, "reason": str }
    """
    auth_result = require_auth()
    if len(auth_result) == 2 and not isinstance(auth_result[0], dict):  # Error response
        return auth_result

    user, memory = auth_result

    # Get client IP
    from core.request_utils import get_client_ip
    client_ip = get_client_ip(request)

    # Check if IP is allowed
    is_allowed, reason = memory.is_ip_allowed_for_work_mode(client_ip)

    return jsonify({
        "allowed": is_allowed,
        "current_ip": client_ip,
        "reason": reason
    })
