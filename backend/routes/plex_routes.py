"""
Plex routes.

Provides Plex PIN-based OAuth authentication and integration management endpoints.
All endpoints require Personal Mode - Work Mode returns 403 errors.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import json

plex_bp = Blueprint("plex", __name__, url_prefix="/api/plex")

logger = logging.getLogger(__name__)


def _get_authenticated_user(memory):
    """
    Helper to get authenticated user from request.

    Returns:
        tuple: (user_dict, error_response) or (user_dict, None)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Unauthorized"}), 401)

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return None, (jsonify({"error": "Invalid session"}), 401)

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return None, (jsonify({"error": "User not found"}), 401)

    return user, None


def _is_personal_mode(memory, user_id):
    """
    Check if user is in Personal Mode.

    Returns:
        bool: True if in Personal Mode
    """
    mode_config = memory.get_user_mode(user_id)
    if isinstance(mode_config, dict):
        return mode_config.get("active_mode") == "personal"
    return mode_config == "personal"  # Fallback for old return format


@plex_bp.route("/auth/start", methods=["POST"])
def start_plex_auth():
    """
    Initiate Plex PIN-based OAuth flow.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: {
        "pin_id": 123456,
        "code": "ABCD",
        "auth_url": "https://app.plex.tv/auth#?clientID=...&code=ABCD"
    }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.plex_oauth import PlexOAuth

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        # Request PIN from Plex
        pin_data = PlexOAuth.request_pin()

        if not pin_data:
            logger.error(f"[PLEX] Failed to request PIN for user {user['id']}")
            return jsonify({
                "error": "Failed to request PIN from Plex",
                "message": "Please try again later."
            }), 500

        # Store PIN ID temporarily for polling (5-minute expiry)
        memory.set_user_preference(user["id"], "plex_pin_id", str(pin_data["id"]))
        memory.set_user_preference(
            user["id"],
            "plex_pin_expires",
            (datetime.utcnow().timestamp() + 300)  # 5 minutes
        )

        logger.info(f"[PLEX] PIN requested for user {user['id']}: {pin_data['code']}")

        return jsonify({
            "pin_id": pin_data["id"],
            "code": pin_data["code"],
            "auth_url": pin_data["auth_url"],
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error starting auth for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/auth/poll", methods=["POST"])
def poll_plex_auth():
    """
    Poll Plex API to check if user has authorized the PIN.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Body: { "pin_id": 123456 }
    Returns:
        - Pending: { "status": "pending" }
        - Authorized: {
            "status": "authorized",
            "connected": true,
            "server_name": "...",
            "plex_username": "..."
          }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.plex_oauth import PlexOAuth

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        data = request.get_json()
        pin_id = data.get("pin_id")

        if not pin_id:
            return jsonify({"error": "Missing pin_id"}), 400

        # Verify this PIN belongs to this user
        stored_pin_id = memory.get_user_preference(user["id"], "plex_pin_id")
        if not stored_pin_id or str(stored_pin_id) != str(pin_id):
            return jsonify({"error": "Invalid PIN ID"}), 400

        # Check if PIN expired
        pin_expires = memory.get_user_preference(user["id"], "plex_pin_expires")
        if pin_expires and datetime.utcnow().timestamp() > float(pin_expires):
            # Clean up
            memory.delete_user_preference(user["id"], "plex_pin_id")
            memory.delete_user_preference(user["id"], "plex_pin_expires")
            return jsonify({"error": "PIN expired"}), 400

        # Check PIN status with Plex
        auth_token = PlexOAuth.check_pin_status(pin_id)

        if not auth_token:
            # Still pending or error
            return jsonify({"status": "pending"}), 200

        # PIN authorized! Complete setup
        logger.info(f"[PLEX] PIN authorized for user {user['id']}")

        # Fetch user info
        user_info = PlexOAuth.get_user_info(auth_token)
        if not user_info:
            logger.error(f"[PLEX] Failed to fetch user info for user {user['id']}")
            return jsonify({
                "error": "Failed to fetch Plex user profile"
            }), 500

        # Fetch primary server
        server_info = PlexOAuth.get_primary_server(auth_token)
        if not server_info:
            logger.error(f"[PLEX] No servers found for user {user['id']}")
            return jsonify({
                "error": "No Plex servers found",
                "message": "Please ensure you have access to a Plex Media Server."
            }), 400

        # Store credentials
        memory.store_plex_credentials(
            user_id=user["id"],
            access_token=auth_token,
            plex_user_id=user_info["id"],
            plex_username=user_info["username"],
            server_url=server_info["url"],
            server_name=server_info["name"],
            server_version=server_info["version"],
        )

        # Create service provider entry
        memory.store_service_provider(
            user_id=user["id"],
            name="Plex Media Server",
            category="media",
            provider_type="plex",
            capabilities=json.dumps([
                "read_library",
                "get_recently_watched",
                "get_on_deck",
                "get_new_releases",
            ]),
            auth_method="oauth2",
            trust_level="auto",
            additional_metadata=json.dumps({
                "server_name": server_info["name"],
                "server_url": server_info["url"],
                "plex_user_id": user_info["id"],
            }),
        )

        # Clean up temporary data
        memory.delete_user_preference(user["id"], "plex_pin_id")
        memory.delete_user_preference(user["id"], "plex_pin_expires")

        logger.info(
            f"[PLEX] User {user['id']} connected to server '{server_info['name']}'"
        )

        return jsonify({
            "status": "authorized",
            "connected": True,
            "server_name": server_info["name"],
            "plex_username": user_info["username"],
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error polling auth for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/status", methods=["GET"])
def get_plex_status():
    """
    Get Plex connection status.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: {
        "connected": true/false,
        "server_name": "...",
        "server_url": "...",
        "plex_username": "...",
        "is_valid": true/false
    }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        credentials = memory.get_plex_credentials(user["id"])

        if not credentials:
            return jsonify({"connected": False}), 200

        return jsonify({
            "connected": True,
            "server_name": credentials["server_name"],
            "server_url": credentials["server_url"],
            "plex_username": credentials["plex_username"],
            "is_valid": credentials["is_valid"],
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error fetching status for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/disconnect", methods=["DELETE"])
def disconnect_plex():
    """
    Disconnect Plex account.

    Deletes credentials, settings, and tracking data.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: { "success": true }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        # Delete all Plex data
        memory.delete_plex_credentials(user["id"])
        memory.delete_plex_settings(user["id"])
        memory.delete_all_plex_tracking(user["id"])

        # Remove service provider entries
        providers = memory.get_service_providers_by_type(user["id"], "plex")
        for provider in providers:
            memory.delete_service_provider(provider["id"])

        logger.info(f"[PLEX] User {user['id']} disconnected")

        return jsonify({
            "success": True,
            "message": "Plex account disconnected successfully"
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error disconnecting user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/settings", methods=["GET"])
def get_plex_settings():
    """
    Get Plex notification settings.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: {
        "new_episode_notifications_enabled": false,
        "new_season_notifications_enabled": false,
        "new_movie_notifications_enabled": false,
        "check_frequency_minutes": 15,
        "quiet_hours_start": null,
        "quiet_hours_end": null
    }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        settings = memory.get_plex_settings(user["id"])

        return jsonify({
            "new_episode_notifications_enabled": settings["new_episode_notifications_enabled"],
            "new_season_notifications_enabled": settings["new_season_notifications_enabled"],
            "new_movie_notifications_enabled": settings["new_movie_notifications_enabled"],
            "check_frequency_minutes": settings["check_frequency_minutes"],
            "quiet_hours_start": settings["quiet_hours_start"],
            "quiet_hours_end": settings["quiet_hours_end"],
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error fetching settings for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/settings", methods=["PUT"])
def update_plex_settings():
    """
    Update Plex notification settings.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Body: {
        "new_episode_notifications_enabled": true,
        "new_season_notifications_enabled": false,
        "new_movie_notifications_enabled": false,
        "check_frequency_minutes": 30,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00"
    }
    Returns: { "success": true, "settings": {...} }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        data = request.get_json()

        # Validate check_frequency_minutes
        if "check_frequency_minutes" in data:
            freq = data["check_frequency_minutes"]
            if not isinstance(freq, int) or freq < 5 or freq > 120:
                return jsonify({
                    "error": "check_frequency_minutes must be between 5 and 120"
                }), 400

        # Update settings
        memory.update_plex_settings(user["id"], **data)

        # Return updated settings
        settings = memory.get_plex_settings(user["id"])

        logger.info(f"[PLEX] Settings updated for user {user['id']}")

        return jsonify({
            "success": True,
            "settings": settings,
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error updating settings for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/server-url", methods=["PUT"])
def update_server_url():
    """
    Update Plex server URL manually.

    Useful when auto-discovered URL doesn't work (e.g., relay URLs that can't resolve).

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Body: {
        "server_url": "http://192.168.1.100:32400" or "http://193.237.209.39:32400"
    }
    Returns: { "success": true, "server_url": "..." }
    """
    from core.memory import MemoryStore
    from config import Config
    from services.plex_client import PlexClient

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        data = request.get_json()
        new_url = data.get("server_url", "").strip()

        if not new_url:
            return jsonify({"error": "server_url is required"}), 400

        # Validate URL format
        if not (new_url.startswith("http://") or new_url.startswith("https://")):
            return jsonify({"error": "server_url must start with http:// or https://"}), 400

        # Get current credentials
        credentials = memory.get_plex_credentials(user["id"])
        if not credentials:
            return jsonify({"error": "Plex not connected"}), 400

        # Test connection with new URL
        client = PlexClient(credentials["access_token"], new_url)
        if not client.test_connection():
            return jsonify({
                "error": "Failed to connect to Plex server at provided URL",
                "message": "Please verify the URL is correct and the server is accessible"
            }), 400

        # Update server URL in database
        memory.update_plex_server_url(user["id"], new_url)

        logger.info(f"[PLEX] Server URL updated for user {user['id']}: {new_url}")

        return jsonify({
            "success": True,
            "server_url": new_url,
        }), 200

    except Exception as e:
        logger.error(f"[PLEX] Error updating server URL for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/library/recent", methods=["GET"])
def get_recently_watched():
    """
    Get recently watched items.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Query params: ?limit=10
    Returns: { "items": [...] }
    """
    from core.memory import MemoryStore
    from config import Config
    from services.plex_client import PlexClient

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        credentials = memory.get_plex_credentials(user["id"])

        if not credentials or not credentials["is_valid"]:
            return jsonify({
                "error": "Plex not connected or credentials invalid"
            }), 400

        # Get limit from query params
        limit = request.args.get("limit", default=10, type=int)
        if limit < 1 or limit > 50:
            limit = 10

        # Fetch from Plex
        client = PlexClient(credentials["access_token"], credentials["server_url"])
        items = client.get_recently_watched(limit=limit)

        return jsonify({"items": items}), 200

    except Exception as e:
        logger.error(f"[PLEX] Error fetching recently watched for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/library/on-deck", methods=["GET"])
def get_on_deck():
    """
    Get "On Deck" items (next to watch).

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: { "items": [...] }
    """
    from core.memory import MemoryStore
    from config import Config
    from services.plex_client import PlexClient

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        credentials = memory.get_plex_credentials(user["id"])

        if not credentials or not credentials["is_valid"]:
            return jsonify({
                "error": "Plex not connected or credentials invalid"
            }), 400

        # Fetch from Plex
        client = PlexClient(credentials["access_token"], credentials["server_url"])
        items = client.get_on_deck()

        return jsonify({"items": items}), 200

    except Exception as e:
        logger.error(f"[PLEX] Error fetching On Deck for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


@plex_bp.route("/library/currently-playing", methods=["GET"])
def get_currently_playing():
    """
    Get currently playing sessions.

    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: { "sessions": [...] }
    """
    from core.memory import MemoryStore
    from config import Config
    from services.plex_client import PlexClient

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Plex integration is only available in Personal Mode"
        }), 403

    try:
        credentials = memory.get_plex_credentials(user["id"])

        if not credentials or not credentials["is_valid"]:
            return jsonify({
                "error": "Plex not connected or credentials invalid"
            }), 400

        # Fetch from Plex
        client = PlexClient(credentials["access_token"], credentials["server_url"])
        sessions = client.get_currently_playing()

        return jsonify({"sessions": sessions}), 200

    except Exception as e:
        logger.error(f"[PLEX] Error fetching currently playing for user {user['id']}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500
