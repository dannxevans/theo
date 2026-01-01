"""
Settings routes.

Provides application settings endpoints for debug mode and system prompt configuration.
"""

from flask import Blueprint, jsonify, request

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route("/debug", methods=["GET"])
def get_debug_setting():
    """
    Get debug mode setting.
    Returns: { "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Read from preferences, not routing
    prefs = memory.get_all("local")
    value = prefs.get("debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@settings_bp.route("/debug", methods=["POST"])
def set_debug_setting():
    """
    Set debug mode setting.
    Request body: { "enabled": bool }
    Returns: { "status": "ok", "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    memory.remember(
        user_id="local",
        key="debug_enabled",
        value=str(enabled).lower()
    )

    return jsonify({"status": "ok", "enabled": enabled})


@settings_bp.route("/message-debug", methods=["GET"])
def get_message_debug_setting():
    """
    Get message debug mode setting.
    Returns: { "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = "local"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    # Read from preferences
    prefs = memory.get_all(user_id)
    value = prefs.get("message_debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@settings_bp.route("/message-debug", methods=["POST"])
def set_message_debug_setting():
    """
    Set message debug mode setting.
    Request body: { "enabled": bool }
    Returns: { "status": "ok", "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = "local"
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    import logging
    logging.info(f"[MESSAGE_DEBUG_POST] Saving preference for user_id={user_id}, enabled={enabled}")
    memory.remember(
        user_id=user_id,
        key="message_debug_enabled",
        value=str(enabled).lower()
    )

    # Verify it was saved
    prefs_check = memory.get_all(user_id)
    logging.info(f"[MESSAGE_DEBUG_POST] After save, prefs for user_id={user_id}: {prefs_check}")

    return jsonify({"status": "ok", "enabled": enabled})


@settings_bp.route("/system-prompt", methods=["GET"])
def get_system_prompt_settings():
    """
    Get system prompt configuration.
    Returns: System prompt config object
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    config = memory.get_system_prompt_config("local")
    
    return jsonify(config)


@settings_bp.route("/system-prompt", methods=["POST"])
def update_system_prompt_settings():
    """
    Update system prompt configuration.
    Request body: { "persona_name": "...", "tone": "...", "style_rules": "...", "custom_instructions": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json

    # Only allow updating specific fields
    allowed_fields = ["persona_name", "tone", "style_rules", "custom_instructions"]
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    memory.update_system_prompt_config("local", **updates)
    return jsonify({"status": "ok"})


@settings_bp.route("/preference/<key>", methods=["GET"])
def get_user_preference(key):
    """
    Get a user preference value.
    Returns: { "value": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # For now, using "local" as user_id (will be replaced with actual auth later)
    value = memory.get_user_preference("local", key)

    return jsonify({"value": value})


@settings_bp.route("/preference/<key>", methods=["POST"])
def set_user_preference(key):
    """
    Set a user preference value.
    Request body: { "value": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    value = data.get("value")

    if value is None:
        return jsonify({"error": "Value is required"}), 400

    # For now, using "local" as user_id
    memory.set_user_preference("local", key, str(value))

    return jsonify({"status": "ok"})
