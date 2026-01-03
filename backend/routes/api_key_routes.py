"""
API Key management routes.

Provides endpoints for creating, listing, and revoking API keys
for programmatic access to THEO.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from auth import (
    generate_api_key,
    hash_api_key,
    require_auth
)

api_key_bp = Blueprint('api_keys', __name__, url_prefix='/api/api-keys')


@api_key_bp.route("", methods=["POST"])
@require_auth(lambda: _get_memory())
def create_key():
    """
    Create a new API key.

    Requires session authentication (not API key auth).

    Request body:
    {
        "name": "My iPhone",           // Optional user-friendly label
        "expires_in_days": 90          // Optional expiration in days
    }

    Returns:
    {
        "id": 1,
        "key": "theo_abc123...",       // ONLY TIME THIS IS SHOWN
        "name": "My iPhone",
        "created_at": "2026-01-03T...",
        "expires_at": "2026-04-03T..." // or null
    }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Only allow session auth for key creation (not API key auth)
    # This prevents an API key from creating more API keys
    if hasattr(request, 'auth_method') and request.auth_method != "session":
        return jsonify({"error": "Session authentication required for API key management"}), 403

    data = request.json or {}
    name = data.get("name", "Untitled Key")
    expires_in_days = data.get("expires_in_days")  # Optional

    # Validate expiration
    expires_at = None
    if expires_in_days is not None:
        try:
            days = int(expires_in_days)
            if days < 1 or days > 3650:  # Max 10 years
                return jsonify({"error": "Expiration must be between 1 and 3650 days"}), 400
            expires_at = datetime.utcnow() + timedelta(days=days)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid expires_in_days value"}), 400

    # Generate API key
    api_key = generate_api_key()  # Returns "theo_<random>"
    key_hash = hash_api_key(api_key)

    # Store in database
    try:
        key_id = memory.create_api_key(
            user_id=request.current_user["id"],
            name=name,
            key_hash=key_hash,
            expires_at=expires_at
        )
    except Exception as e:
        return jsonify({"error": f"Failed to create API key: {str(e)}"}), 500

    # Return the key ONCE (never stored in plaintext)
    return jsonify({
        "id": key_id,
        "key": api_key,  # ONLY TIME THIS IS SHOWN
        "name": name,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None
    }), 201


@api_key_bp.route("", methods=["GET"])
@require_auth(lambda: _get_memory())
def list_keys():
    """
    List all API keys for the authenticated user.

    Returns array of:
    {
        "id": 1,
        "name": "My iPhone",
        "created_at": "2026-01-03T...",
        "last_used_at": "2026-01-03T..." // or null,
        "expires_at": "2026-04-03T..."   // or null,
        "is_revoked": false
    }

    Note: key_hash is never returned for security.
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    try:
        keys = memory.list_user_api_keys(request.current_user["id"])

        # Format dates as ISO strings for JSON
        for key in keys:
            if key["created_at"]:
                key["created_at"] = key["created_at"].isoformat() if isinstance(key["created_at"], datetime) else key["created_at"]
            if key["last_used_at"]:
                key["last_used_at"] = key["last_used_at"].isoformat() if isinstance(key["last_used_at"], datetime) else key["last_used_at"]
            if key["expires_at"]:
                key["expires_at"] = key["expires_at"].isoformat() if isinstance(key["expires_at"], datetime) else key["expires_at"]
            if key["revoked_at"]:
                key["revoked_at"] = key["revoked_at"].isoformat() if isinstance(key["revoked_at"], datetime) else key["revoked_at"]

        return jsonify(keys)
    except Exception as e:
        return jsonify({"error": f"Failed to list API keys: {str(e)}"}), 500


@api_key_bp.route("/<int:key_id>", methods=["DELETE"])
@require_auth(lambda: _get_memory())
def revoke_key(key_id):
    """
    Revoke an API key (soft delete).

    Only the key owner can revoke their keys.

    Returns:
    {
        "status": "ok",
        "message": "API key revoked"
    }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Only allow session auth for key revocation
    if hasattr(request, 'auth_method') and request.auth_method != "session":
        return jsonify({"error": "Session authentication required for API key management"}), 403

    try:
        success = memory.revoke_api_key(key_id, request.current_user["id"])

        if not success:
            return jsonify({"error": "API key not found or access denied"}), 404

        return jsonify({
            "status": "ok",
            "message": "API key revoked successfully"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to revoke API key: {str(e)}"}), 500


@api_key_bp.route("/<int:key_id>", methods=["PATCH"])
@require_auth(lambda: _get_memory())
def update_key(key_id):
    """
    Update an API key's metadata (name only for now).

    Only the key owner can update their keys.

    Request body:
    {
        "name": "New Name"
    }

    Returns:
    {
        "status": "ok",
        "message": "API key updated"
    }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Only allow session auth for key updates
    if hasattr(request, 'auth_method') and request.auth_method != "session":
        return jsonify({"error": "Session authentication required for API key management"}), 403

    data = request.json or {}
    new_name = data.get("name")

    if not new_name:
        return jsonify({"error": "Name is required"}), 400

    try:
        success = memory.update_api_key_name(key_id, request.current_user["id"], new_name)

        if not success:
            return jsonify({"error": "API key not found or access denied"}), 404

        return jsonify({
            "status": "ok",
            "message": "API key updated successfully"
        })
    except Exception as e:
        return jsonify({"error": f"Failed to update API key: {str(e)}"}), 500


def _get_memory():
    """Helper to get MemoryStore instance for require_auth decorator."""
    from core.memory import MemoryStore
    from config import Config
    return MemoryStore(Config.DATABASE_URL)
