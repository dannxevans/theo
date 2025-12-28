"""
Mode routes.

Provides mode management endpoints for switching between work and personal modes,
managing mode settings, and configuring work subtabs.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import json as json_module

mode_bp = Blueprint('mode', __name__, url_prefix='/api/mode')


@mode_bp.route("", methods=["GET"])
def get_mode():
    """
    Get user's current mode.
    Requires: Authorization header with bearer token
    Returns: { "active_mode": "work"|"personal" }
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

    # Get mode
    mode_config = memory.get_user_mode(user["id"])
    return jsonify(mode_config)


@mode_bp.route("", methods=["POST"])
def set_mode():
    """
    Set user's current mode.
    Requires: Authorization header with bearer token
    Request body: { "mode": "work"|"personal" }
    Returns: { "status": "ok", "mode": "..." }
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

    # Get requested mode
    data = request.json
    mode = data.get("mode")

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Set mode
    memory.set_user_mode(user["id"], mode)
    return jsonify({"status": "ok", "mode": mode})


@mode_bp.route("/settings", methods=["GET"])
def get_mode_settings_endpoint():
    """
    Get all mode settings for the user.
    Requires: Authorization header with bearer token
    Returns: Object with all mode settings
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

    # Get all mode settings
    settings = memory.get_all_mode_settings(user["id"])
    return jsonify(settings)


@mode_bp.route("/settings/<mode>", methods=["GET"])
def get_mode_setting(mode):
    """
    Get settings for a specific mode.
    Requires: Authorization header with bearer token
    Returns: Mode settings object
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

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Get mode settings
    settings = memory.get_mode_settings(user["id"], mode)
    return jsonify(settings if settings else {})


@mode_bp.route("/settings/<mode>", methods=["POST"])
def update_mode_settings(mode):
    """
    Update settings for a specific mode.
    Requires: Authorization header with bearer token
    Request body: { "system_prompt_override": "...", "preferred_provider_id": N, "tone": "..." }
    Returns: { "status": "ok" }
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

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Get settings from request
    data = request.json
    system_prompt_override = data.get("system_prompt_override")
    preferred_provider_id = data.get("preferred_provider_id")
    tone = data.get("tone")

    # Update settings
    memory.create_or_update_mode_settings(
        user["id"],
        mode,
        system_prompt_override=system_prompt_override,
        preferred_provider_id=preferred_provider_id,
        tone=tone
    )

    return jsonify({"status": "ok"})


@mode_bp.route("/work/subtab/<subtab>", methods=["GET"])
def get_work_subtab(subtab):
    """
    Get configuration for a specific work subtab.
    Requires: Authorization header with bearer token
    Returns: Subtab configuration object
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

    if subtab not in ["conversation", "email", "code"]:
        return jsonify({"error": "Subtab must be 'conversation', 'email', or 'code'"}), 400

    # Get subtab config
    config = memory.get_work_subtab_config(user["id"], subtab)
    return jsonify(config if config else {})


@mode_bp.route("/work/subtab/<subtab>", methods=["POST"])
def update_work_subtab(subtab):
    """
    Update configuration for a specific work subtab.
    Requires: Authorization header with bearer token
    Request body: Configuration object (varies by subtab)
    Returns: { "status": "ok" }
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

    if subtab not in ["conversation", "email", "code"]:
        return jsonify({"error": "Subtab must be 'conversation', 'email', or 'code'"}), 400

    # Get config from request
    data = request.json
    config_json = json_module.dumps(data)

    # Update subtab config
    memory.update_work_subtab_config(user["id"], subtab, config_json)
    return jsonify({"status": "ok"})


@mode_bp.route("/work/subtabs", methods=["GET"])
def get_all_work_subtabs():
    """
    Get all work subtab configurations.
    Requires: Authorization header with bearer token
    Returns: Object with all subtab configurations
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

    # Get all subtab configs
    configs = memory.get_all_work_subtab_configs(user["id"])
    return jsonify(configs)
