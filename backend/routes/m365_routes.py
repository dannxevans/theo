"""
M365 routes.

Provides Microsoft 365 OAuth authentication and integration management endpoints.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging
import json as json_module

m365_bp = Blueprint('m365', __name__, url_prefix='/api/m365')


@m365_bp.route("/auth/start", methods=["POST"])
def start_m365_auth():
    """
    Initiate M365 OAuth device flow.
    Requires: Authorization header with bearer token
    Returns: { "user_code": "...", "verification_url": "...", "device_code": "...", ... }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.m365_oauth import M365OAuth

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check if configured
    if not M365OAuth.is_configured():
        return jsonify({
            "error": "M365 not configured",
            "instructions": M365OAuth.get_configuration_instructions()
        }), 500

    try:
        # Initiate device flow
        device_info = M365OAuth.initiate_device_flow()

        return jsonify({
            "user_code": device_info["user_code"],
            "verification_url": device_info["verification_url"],
            "message": device_info["message"],
            "expires_in": device_info["expires_in"],
            "interval": device_info["interval"],
            "device_code": device_info["device_code"]  # Frontend will need this for polling
        })

    except Exception as e:
        logging.error(f"[API] M365 auth start failed: {e}")
        return jsonify({"error": str(e)}), 500


@m365_bp.route("/auth/poll", methods=["POST"])
def poll_m365_auth():
    """
    Poll for M365 OAuth token completion.
    Requires: Authorization header with bearer token
    Request body: { "device_code": "..." }
    Returns: { "status": "success"|"pending"|"declined"|"expired"|"error", ... }
    """
    from core.memory import MemoryStore
    from config import Config
    from auth.m365_oauth import M365OAuth
    import requests

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    data = request.json
    device_code = data.get("device_code")

    if not device_code:
        return jsonify({"error": "device_code required"}), 400

    try:
        # Poll for token (single attempt)
        payload = {
            "client_id": M365OAuth.CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code
        }

        response = requests.post(M365OAuth.TOKEN_URL, data=payload, timeout=10)

        if response.status_code == 200:
            # Success! Store credentials
            token_data = response.json()

            memory.store_m365_credentials(
                user_id=user["id"],
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"]),
                scope=token_data.get("scope")
            )

            # Create M365 service provider entry
            provider_id = memory.store_service_provider(
                user_id=user["id"],
                name="Microsoft 365",
                category="calendar",
                provider_type="m365",
                capabilities=json_module.dumps([
                    "read_calendar",
                    "create_calendar_event",
                    "update_calendar_event",
                    "delete_calendar_event",
                    "read_email",
                    "send_email",
                    "draft_email"
                ]),
                auth_method="oauth2",
                trust_level="confirm"
            )

            logging.info(f"[API] M365 connected successfully for user {user['id']}")

            return jsonify({
                "status": "success",
                "message": "M365 connected successfully",
                "provider_id": provider_id
            })

        # Check error
        error_data = response.json()
        error = error_data.get("error")

        if error == "authorization_pending":
            # Still waiting
            return jsonify({"status": "pending"}), 202
        elif error == "authorization_declined":
            return jsonify({"status": "declined", "error": "User declined authorization"}), 400
        elif error == "expired_token":
            return jsonify({"status": "expired", "error": "Device code expired"}), 400
        else:
            logging.error(f"[API] M365 auth error: {error}")
            return jsonify({"status": "error", "error": error}), 400

    except Exception as e:
        logging.error(f"[API] M365 auth poll failed: {e}")
        return jsonify({"error": str(e)}), 500


@m365_bp.route("/status", methods=["GET"])
def get_m365_status():
    """
    Get M365 connection status.
    Requires: Authorization header with bearer token
    Returns: { "connected": bool, "is_valid": bool, "expires_at": "...", ... }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check for M365 credentials
    creds = memory.get_m365_credentials(user["id"])

    if not creds:
        return jsonify({"connected": False})

    return jsonify({
        "connected": True,
        "is_valid": creds.get("is_valid"),
        "expires_at": creds.get("expires_at").isoformat() if creds.get("expires_at") else None,
        "user_principal_name": creds.get("user_principal_name"),
        "token_expires_soon": (
            creds.get("expires_at") < datetime.utcnow() + timedelta(minutes=10)
            if creds.get("expires_at") else True
        )
    })


@m365_bp.route("/disconnect", methods=["POST"])
def disconnect_m365():
    """
    Disconnect M365 account.
    Requires: Authorization header with bearer token
    Returns: { "status": "disconnected" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Delete M365 credentials (not just invalidate)
    memory.delete_m365_credentials(user["id"])

    # Remove M365 service providers
    providers = memory.get_service_providers(user["id"])
    for provider in providers:
        if provider.get("provider_type") == "m365":
            memory.delete_service_provider(provider["id"], user["id"])

    logging.info(f"[API] M365 disconnected for user {user['id']}")

    return jsonify({"status": "disconnected"})
