"""
Routing routes.

Provides routing preference management for mapping intents to specific providers.
"""

from flask import Blueprint, jsonify, request

routing_bp = Blueprint('routing', __name__, url_prefix='/api/routing')


@routing_bp.route("", methods=["GET"])
def get_routing_preferences():
    """
    Get all routing preferences.
    Returns: Array of routing preference objects
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    prefs = memory.get_routing_preferences("local")
    
    return jsonify(prefs)


@routing_bp.route("", methods=["POST"])
def set_routing_preference():
    """
    Set a routing preference for an intent.
    Request body: { "intent": "...", "provider_id": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    
    memory.set_routing_preference(
        user_id="local",
        intent=data["intent"],
        provider_id=data["provider_id"],
    )
    
    return jsonify({"status": "ok"})


@routing_bp.route("/<intent>", methods=["DELETE"])
def delete_routing_preference(intent):
    """
    Delete a routing preference for an intent.
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    memory.delete_routing_preference("local", intent)
    
    return jsonify({"status": "ok"})
