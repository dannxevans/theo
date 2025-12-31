"""
Intent routes.

Provides intent management endpoints for creating, reading, updating,
and deleting user-defined intents.
"""

from flask import Blueprint, jsonify, request

intent_bp = Blueprint('intent', __name__, url_prefix='/api/intents')


@intent_bp.route("", methods=["GET"])
def list_intents():
    """
    Get all user-defined intents.
    Returns: Array of intent objects
    """
    from core.memory import MemoryStore
    from config import Config
    from flask import g

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = str(getattr(g, 'user_id', 'local'))
    intents = memory.list_intents(user_id)

    return jsonify(intents)


@intent_bp.route("/<intent_id>", methods=["GET"])
def get_intent(intent_id):
    """
    Get a single intent by ID.
    Returns: Intent object or 404
    """
    from core.memory import MemoryStore
    from config import Config
    from flask import g

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = str(getattr(g, 'user_id', 'local'))
    intent = memory.get_intent(user_id, intent_id)

    if not intent:
        return jsonify({"error": "Intent not found"}), 404

    return jsonify(intent)


@intent_bp.route("", methods=["POST"])
def create_intent():
    """
    Create a new intent.
    Request body: { "id": "...", "name": "...", "description": "...", "keywords": "...", "priority": N, "enabled": bool }
    Returns: { "status": "ok", "intent_id": "..." }
    """
    from core.memory import MemoryStore
    from config import Config
    from flask import g

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = str(getattr(g, 'user_id', 'local'))
    data = request.json

    intent_id = data.get("id")
    name = data.get("name")
    description = data.get("description", "")
    keywords = data.get("keywords", "")
    priority = data.get("priority", 0)
    enabled = data.get("enabled", True)

    if not intent_id or not name:
        return jsonify({"error": "id and name are required"}), 400

    try:
        memory.create_intent(
            user_id=user_id,
            intent_id=intent_id,
            name=name,
            description=description,
            keywords=keywords,
            priority=priority,
            enabled=enabled,
        )
        return jsonify({"status": "ok", "intent_id": intent_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@intent_bp.route("/<intent_id>", methods=["PUT"])
def update_intent(intent_id):
    """
    Update an existing intent.
    Request body: Fields to update (name, description, keywords, priority, enabled)
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config
    from flask import g

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = str(getattr(g, 'user_id', 'local'))
    data = request.json
    updates = {}

    # Only include fields that are present in the request
    if "name" in data:
        updates["name"] = data["name"]
    if "description" in data:
        updates["description"] = data["description"]
    if "keywords" in data:
        updates["keywords"] = data["keywords"]
    if "priority" in data:
        updates["priority"] = data["priority"]
    if "enabled" in data:
        updates["enabled"] = data["enabled"]

    try:
        memory.update_intent(user_id, intent_id, **updates)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@intent_bp.route("/<intent_id>", methods=["DELETE"])
def delete_intent(intent_id):
    """
    Delete an intent.
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config
    from flask import g

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = str(getattr(g, 'user_id', 'local'))

    try:
        memory.delete_intent(user_id, intent_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
