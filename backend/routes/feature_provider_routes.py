"""
Feature Provider routes.

Manages API keys and configuration for external feature providers
(weather, traffic, etc.)
"""

from flask import Blueprint, jsonify, request
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime

feature_provider_bp = Blueprint('feature_providers', __name__, url_prefix='/api/feature-providers')


@feature_provider_bp.route("", methods=["GET"])
def get_feature_providers():
    """
    Get all feature providers for the authenticated user.
    Returns: List of feature provider configurations
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = DEFAULT_USER_ID
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    # Get all feature providers from database
    import sqlite3
    from config import Config

    # Strip sqlite:/// prefix if present
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, provider_type, provider_name, is_enabled, created_at, updated_at
        FROM feature_providers
        WHERE user_id = ?
    """, (str(user_id),))

    providers = []
    for row in cursor.fetchall():
        providers.append({
            "id": row["id"],
            "provider_type": row["provider_type"],
            "provider_name": row["provider_name"],
            "is_enabled": bool(row["is_enabled"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    conn.close()

    # Get API keys from preferences (stored separately for security)
    prefs = memory.get_all(str(user_id))

    # Add API key, APP ID, and wake word status (whether they exist, not the actual values)
    for provider in providers:
        key_name = f"feature_provider_{provider['provider_type']}_api_key"
        provider["has_api_key"] = key_name in prefs and bool(prefs[key_name])

        app_id_name = f"feature_provider_{provider['provider_type']}_app_id"
        provider["has_app_id"] = app_id_name in prefs and bool(prefs[app_id_name])

        wake_word_name = f"feature_provider_{provider['provider_type']}_wake_word"
        provider["has_wake_word"] = wake_word_name in prefs and bool(prefs[wake_word_name])

    return jsonify(providers)


@feature_provider_bp.route("/<provider_type>", methods=["GET"])
def get_feature_provider(provider_type):
    """
    Get a specific feature provider configuration.
    Returns: Feature provider config or 404 if not found
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = DEFAULT_USER_ID
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    import sqlite3
    from config import Config

    # Strip sqlite:/// prefix if present
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, provider_type, provider_name, is_enabled, created_at, updated_at
        FROM feature_providers
        WHERE user_id = ? AND provider_type = ?
    """, (str(user_id), provider_type))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Provider not found"}), 404

    provider = {
        "id": row["id"],
        "provider_type": row["provider_type"],
        "provider_name": row["provider_name"],
        "is_enabled": bool(row["is_enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    }

    # Get API key, APP ID, and wake word status from preferences
    prefs = memory.get_all(str(user_id))
    key_name = f"feature_provider_{provider_type}_api_key"
    provider["has_api_key"] = key_name in prefs and bool(prefs[key_name])

    app_id_name = f"feature_provider_{provider_type}_app_id"
    provider["has_app_id"] = app_id_name in prefs and bool(prefs[app_id_name])

    wake_word_name = f"feature_provider_{provider_type}_wake_word"
    provider["has_wake_word"] = wake_word_name in prefs and bool(prefs[wake_word_name])

    # Optionally include actual API key if include_key=true query param
    # This allows kiosk mode to retrieve the key for wake-word detection
    include_key = request.args.get("include_key") == "true"
    if include_key and key_name in prefs:
        provider["api_key"] = prefs[key_name]

    if include_key and app_id_name in prefs:
        provider["app_id"] = prefs[app_id_name]

    if include_key and wake_word_name in prefs:
        provider["wake_word"] = prefs[wake_word_name]

    return jsonify(provider)


@feature_provider_bp.route("/<provider_type>", methods=["POST"])
def configure_feature_provider(provider_type):
    """
    Configure or update a feature provider.
    Request body: { "provider_name": "...", "api_key": "...", "app_id": "...", "wake_word": "...", "is_enabled": bool }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = DEFAULT_USER_ID
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    data = request.json
    provider_name = data.get("provider_name")
    api_key = data.get("api_key")
    app_id = data.get("app_id")
    wake_word = data.get("wake_word")
    is_enabled = data.get("is_enabled", True)

    if not provider_name:
        return jsonify({"error": "provider_name is required"}), 400

    import sqlite3
    from config import Config

    # Strip sqlite:/// prefix if present
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if provider already exists
    cursor.execute("""
        SELECT id FROM feature_providers
        WHERE user_id = ? AND provider_type = ?
    """, (str(user_id), provider_type))

    existing = cursor.fetchone()

    if existing:
        # Update existing provider
        cursor.execute("""
            UPDATE feature_providers
            SET provider_name = ?, is_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND provider_type = ?
        """, (provider_name, int(is_enabled), str(user_id), provider_type))
    else:
        # Insert new provider
        cursor.execute("""
            INSERT INTO feature_providers (user_id, provider_type, provider_name, is_enabled)
            VALUES (?, ?, ?, ?)
        """, (str(user_id), provider_type, provider_name, int(is_enabled)))

    conn.commit()
    conn.close()

    # Store API key in preferences if provided
    if api_key:
        key_name = f"feature_provider_{provider_type}_api_key"
        memory.remember(str(user_id), key_name, api_key)

    # Store APP ID in preferences if provided
    if app_id:
        app_id_name = f"feature_provider_{provider_type}_app_id"
        memory.remember(str(user_id), app_id_name, app_id)

    # Store wake word in preferences if provided
    if wake_word:
        wake_word_name = f"feature_provider_{provider_type}_wake_word"
        memory.remember(str(user_id), wake_word_name, wake_word)

    return jsonify({"status": "ok"})


@feature_provider_bp.route("/<provider_type>", methods=["DELETE"])
def delete_feature_provider(provider_type):
    """
    Delete a feature provider and its API key.
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use "local" for unauthenticated
    user_id = DEFAULT_USER_ID
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    import sqlite3
    from config import Config

    # Strip sqlite:/// prefix if present
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Delete provider from database
    cursor.execute("""
        DELETE FROM feature_providers
        WHERE user_id = ? AND provider_type = ?
    """, (str(user_id), provider_type))

    conn.commit()
    conn.close()

    # Delete API key, APP ID, and wake word from preferences
    key_name = f"feature_provider_{provider_type}_api_key"
    app_id_name = f"feature_provider_{provider_type}_app_id"
    wake_word_name = f"feature_provider_{provider_type}_wake_word"

    # Use direct SQL to delete from preferences since there's no delete method in MemoryStore
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM preferences
        WHERE user_id = ? AND key IN (?, ?, ?)
    """, (str(user_id), key_name, app_id_name, wake_word_name))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})
