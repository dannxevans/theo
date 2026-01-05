"""
WHOOP routes.

Provides WHOOP OAuth authentication and integration management endpoints.
All endpoints require Personal Mode - Work Mode returns 403 errors.
"""

from flask import Blueprint, jsonify, request, g, redirect
from datetime import datetime, timedelta
import logging
import secrets
import json

whoop_bp = Blueprint('whoop', __name__, url_prefix='/api/whoop')

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


@whoop_bp.route("/auth/start", methods=["POST"])
def start_whoop_auth():
    """
    Initiate WHOOP OAuth flow.
    Requires: Authorization header with bearer token
    Requires: Personal Mode
    Returns: { "authorization_url": "...", "state": "..." }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.whoop_oauth import WHOOPOAuth

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    # Check if configured
    if not WHOOPOAuth.is_configured():
        return jsonify({
            "error": "WHOOP not configured",
            "instructions": WHOOPOAuth.get_configuration_instructions()
        }), 500

    try:
        # Generate state token for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in preferences for verification on callback
        # Use short TTL (5 minutes)
        memory.set_user_preference(user["id"], f"whoop_oauth_state", state)
        memory.set_user_preference(user["id"], f"whoop_oauth_state_expires",
                                   (datetime.utcnow() + timedelta(minutes=5)).isoformat())

        # Get authorization URL
        auth_data = WHOOPOAuth.get_authorization_url(state)

        logger.info(f"[WHOOP] Starting OAuth flow for user {user['id']}")

        return jsonify(auth_data)

    except Exception as e:
        logger.error(f"[WHOOP] Auth start failed: {e}")
        return jsonify({"error": str(e)}), 500


@whoop_bp.route("/auth/callback", methods=["GET"])
def whoop_auth_callback():
    """
    Handle WHOOP OAuth callback.

    This endpoint receives the authorization code from WHOOP after user authorizes.
    Query params: code, state

    Returns:
        - HTML page that closes popup and notifies parent window (success)
        - Error page (failure)
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.whoop_oauth import WHOOPOAuth
    import requests

    memory = MemoryStore(Config.DATABASE_URL)

    # Get code and state from query params
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        error_msg = "Missing code or state parameter"
        logger.error(f"[WHOOP] Callback failed: {error_msg}")
        return f"""
        <html>
            <body>
                <h1>WHOOP Connection Failed</h1>
                <p>{error_msg}</p>
                <p><a href="javascript:window.close()">Close this window</a></p>
            </body>
        </html>
        """, 400

    # Note: We can't use bearer token auth here since this is a redirect from WHOOP
    # Instead, we need to identify the user by the state token
    # This is a security tradeoff - state tokens should be short-lived

    # For now, we'll return a simple success page and let the frontend poll for status
    # A more secure approach would be to use session cookies

    try:
        # Exchange code for token
        token_data = WHOOPOAuth.exchange_code_for_token(code)

        if not token_data:
            raise Exception("Failed to exchange code for token")

        # Fetch user profile to get WHOOP user ID
        # Make API call to WHOOP /user/profile/basic
        profile_response = requests.get(
            "https://api.prod.whoop.com/developer/v1/user/profile/basic",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
            timeout=10
        )

        if profile_response.status_code != 200:
            raise Exception("Failed to fetch WHOOP user profile")

        profile = profile_response.json()
        whoop_user_id = profile.get("user_id")

        if not whoop_user_id:
            raise Exception("WHOOP user ID not found in profile")

        # Store credentials
        # Note: We need to find the user by state token
        # This is a simplified implementation - production should use session cookies

        # For now, return success and let frontend handle via status polling
        logger.info(f"[WHOOP] OAuth callback successful, WHOOP user: {whoop_user_id}")

        # Return HTML that posts message to opener and closes
        return f"""
        <html>
            <head>
                <title>WHOOP Connected</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }}
                    .container {{
                        text-align: center;
                        padding: 40px;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    h1 {{ color: #2e7d32; margin-bottom: 16px; }}
                    p {{ color: #666; margin-bottom: 24px; }}
                    button {{
                        background: #2196f3;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 6px;
                        font-size: 16px;
                        cursor: pointer;
                    }}
                    button:hover {{ background: #1976d2; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✓ WHOOP Connected Successfully!</h1>
                    <p>Your WHOOP account has been connected to THEO.</p>
                    <p>This window will close automatically...</p>
                    <button onclick="window.close()">Close Window</button>
                </div>
                <script>
                    // Store credentials and notify parent
                    const credentials = {{
                        access_token: "{token_data['access_token']}",
                        refresh_token: "{token_data['refresh_token']}",
                        expires_at: "{token_data['expires_at'].isoformat()}",
                        whoop_user_id: "{whoop_user_id}",
                        state: "{state}"
                    }};

                    // Try to post message to opener
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'whoop_auth_success',
                            credentials: credentials
                        }}, '*');
                    }}

                    // Auto-close after 2 seconds
                    setTimeout(() => {{
                        window.close();
                    }}, 2000);
                </script>
            </body>
        </html>
        """

    except Exception as e:
        logger.error(f"[WHOOP] Callback processing failed: {e}")
        return f"""
        <html>
            <head>
                <title>WHOOP Connection Failed</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }}
                    .container {{
                        text-align: center;
                        padding: 40px;
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    h1 {{ color: #c62828; margin-bottom: 16px; }}
                    p {{ color: #666; margin-bottom: 8px; }}
                    button {{
                        background: #2196f3;
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 6px;
                        font-size: 16px;
                        cursor: pointer;
                        margin-top: 16px;
                    }}
                    button:hover {{ background: #1976d2; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✗ WHOOP Connection Failed</h1>
                    <p>There was an error connecting your WHOOP account.</p>
                    <p class="error">Error: {str(e)}</p>
                    <button onclick="window.close()">Close Window</button>
                </div>
                <script>
                    // Notify parent of failure
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'whoop_auth_error',
                            error: "{str(e)}"
                        }}, '*');
                    }}
                </script>
            </body>
        </html>
        """, 500


@whoop_bp.route("/auth/complete", methods=["POST"])
def complete_whoop_auth():
    """
    Complete WHOOP authentication by storing credentials.
    Called by frontend after receiving callback message.

    Request body: {
        "access_token": "...",
        "refresh_token": "...",
        "expires_at": "...",
        "whoop_user_id": "...",
        "state": "..."
    }

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
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    data = request.json

    # Verify required fields
    required = ["access_token", "refresh_token", "expires_at", "whoop_user_id", "state"]
    if not all(field in data for field in required):
        return jsonify({"error": "Missing required fields"}), 400

    # Verify state token
    stored_state = memory.get_user_preference(user["id"], "whoop_oauth_state")
    state_expires = memory.get_user_preference(user["id"], "whoop_oauth_state_expires")

    if not stored_state or stored_state != data["state"]:
        return jsonify({"error": "Invalid state token"}), 400

    if state_expires and datetime.fromisoformat(state_expires) < datetime.utcnow():
        return jsonify({"error": "State token expired"}), 400

    try:
        # Parse expires_at
        expires_at = datetime.fromisoformat(data["expires_at"])

        # Store credentials
        memory.store_whoop_credentials(
            user_id=user["id"],
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=expires_at,
            whoop_user_id=data["whoop_user_id"],
            token_type=data.get("token_type", "Bearer")
        )

        # Clean up state tokens
        memory.set_user_preference(user["id"], "whoop_oauth_state", "")
        memory.set_user_preference(user["id"], "whoop_oauth_state_expires", "")

        # Create service provider entry (for consistency with M365)
        service_providers = memory.get_service_providers(user["id"], category="health")
        whoop_exists = any(sp["name"] == "WHOOP" for sp in service_providers)

        if not whoop_exists:
            memory.store_service_provider(
                user_id=user["id"],
                name="WHOOP",
                category="health",
                provider_type="whoop",
                auth_method="oauth2",
                additional_metadata=json.dumps({"whoop_user_id": data["whoop_user_id"]})
            )

        logger.info(f"[WHOOP] Connected successfully for user {user['id']}")

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"[WHOOP] Failed to complete auth: {e}")
        return jsonify({"error": str(e)}), 500


@whoop_bp.route("/status", methods=["GET"])
def get_whoop_status():
    """
    Get WHOOP connection status.
    Requires: Authorization header with bearer token
    Returns: { "connected": bool, "is_valid": bool, "expires_at": "...", "whoop_user_id": "..." }
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
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    # Check for WHOOP credentials
    creds = memory.get_whoop_credentials(user["id"])

    if not creds:
        return jsonify({"connected": False})

    return jsonify({
        "connected": True,
        "is_valid": creds.get("is_valid"),
        "expires_at": creds.get("expires_at").isoformat() if creds.get("expires_at") else None,
        "whoop_user_id": creds.get("whoop_user_id"),
        "token_expires_soon": (
            creds.get("expires_at") < datetime.utcnow() + timedelta(minutes=10)
            if creds.get("expires_at") else True
        )
    })


@whoop_bp.route("/disconnect", methods=["POST"])
def disconnect_whoop():
    """
    Disconnect WHOOP account.
    Requires: Authorization header with bearer token
    Returns: { "success": true }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.whoop_oauth import WHOOPOAuth

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    try:
        # Get credentials to revoke token
        creds = memory.get_whoop_credentials(user["id"])

        if creds and creds.get("access_token"):
            # Attempt to revoke token (don't fail disconnect if this fails)
            try:
                WHOOPOAuth.revoke_token(creds["access_token"])
            except Exception as e:
                logger.warning(f"[WHOOP] Token revocation failed for user {user['id']}: {e}")

        # Delete all WHOOP data (credentials, settings, tracking)
        memory.delete_all_whoop_data(user["id"])

        # Remove WHOOP service providers
        service_providers = memory.get_service_providers(user["id"], category="health")
        for sp in service_providers:
            if sp["name"] == "WHOOP":
                memory.delete_service_provider(sp["id"], user["id"])

        logger.info(f"[WHOOP] Disconnected successfully for user {user['id']}")

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"[WHOOP] Disconnect failed: {e}")
        return jsonify({"error": str(e)}), 500


@whoop_bp.route("/settings", methods=["GET"])
def get_whoop_settings():
    """
    Get WHOOP notification settings.
    Requires: Authorization header with bearer token
    Returns: { "sleep_notifications_enabled": bool, "workout_notifications_enabled": bool, ... }
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
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    settings = memory.get_whoop_settings(user["id"])
    return jsonify(settings)


@whoop_bp.route("/settings", methods=["POST"])
def update_whoop_settings():
    """
    Update WHOOP notification settings.
    Requires: Authorization header with bearer token
    Request body: { "sleep_notifications_enabled": bool, ... }
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
            "error": "WHOOP integration is only available in Personal Mode"
        }), 403

    data = request.json

    # Validate check_frequency_minutes if provided
    if "check_frequency_minutes" in data:
        freq = data["check_frequency_minutes"]
        if not isinstance(freq, int) or freq < 15 or freq > 120:
            return jsonify({
                "error": "check_frequency_minutes must be between 15 and 120"
            }), 400

    try:
        memory.update_whoop_settings(user["id"], data)

        # TODO: Reschedule proactive jobs when scheduler is integrated
        # from core.scheduler import scheduler
        # scheduler.schedule_whoop_notifications(user["id"])

        logger.info(f"[WHOOP] Settings updated for user {user['id']}")

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"[WHOOP] Settings update failed: {e}")
        return jsonify({"error": str(e)}), 500
