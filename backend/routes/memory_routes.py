"""
Memory routes.

Provides memory management endpoints for storing, retrieving, and searching
user memories.
"""

from flask import Blueprint, jsonify, request
from core.user_utils import DEFAULT_USER_ID

memory_bp = Blueprint('memory', __name__, url_prefix='/api')



def get_user_id_from_request():
    """Extract user_id from auth token or use default."""
    # For now, just use DEFAULT_USER_ID since we don't have auth implemented in routes yet
    # TODO: Extract from Authorization header when authentication is fully implemented
    return DEFAULT_USER_ID


@memory_bp.route("/memory/remember", methods=["POST"])
def remember():
    """
    Legacy memory endpoint (kept for backwards compatibility).
    Request body: { "key": "...", "value": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    
    memory.remember(
        user_id=get_user_id_from_request(),
        key=data["key"],
        value=data["value"]
    )
    return jsonify({"status": "ok"})


@memory_bp.route("/memory/forget", methods=["POST"])
def forget():
    """
    Legacy memory endpoint (kept for backwards compatibility).
    Request body: { "key": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    
    memory.forget(get_user_id_from_request(), data["key"])
    return jsonify({"status": "ok"})


@memory_bp.route("/memories", methods=["GET"])
def list_memories():
    """
    Get all structured memories for the user.
    Optional query params:
    - type: filter by memory type (fact, preference, goal, context)
    - limit: max results
    Returns: Array of memory objects
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    memory_type = request.args.get("type")
    limit = request.args.get("limit", type=int)

    memories = memory.get_memories(get_user_id_from_request(), memory_type=memory_type, limit=limit)
    return jsonify(memories)


@memory_bp.route("/memories", methods=["POST"])
def create_memory():
    """
    Store a new structured memory.
    Request body: { "type": "...", "key": "...", "value": "...", "pinned": bool }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    
    memory.store_memory(
        user_id=get_user_id_from_request(),
        memory_type=data.get("type", "fact"),
        key=data["key"],
        value=data["value"],
        pinned=data.get("pinned", False),
    )
    return jsonify({"status": "ok"})


@memory_bp.route("/memories/<int:memory_id>", methods=["DELETE"])
def delete_memory_endpoint(memory_id):
    """
    Delete a memory by ID.
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    memory.delete_memory(get_user_id_from_request(), memory_id)

    return jsonify({"status": "ok"})


@memory_bp.route("/memories/<int:memory_id>", methods=["PUT"])
def update_memory_endpoint(memory_id):
    """
    Update a memory by ID.
    Request body: { "type": "...", "key": "...", "value": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json

    memory.update_memory(
        user_id=get_user_id_from_request(),
        memory_id=memory_id,
        memory_type=data.get("type"),
        key=data.get("key"),
        value=data.get("value"),
    )
    return jsonify({"status": "ok"})


@memory_bp.route("/memories/<int:memory_id>/pin", methods=["POST"])
def pin_memory_endpoint(memory_id):
    """
    Pin or unpin a memory.
    Request body: { "pinned": bool }
    Returns: { "status": "ok", "pinned": bool }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    pinned = data.get("pinned", True)
    
    memory.pin_memory(get_user_id_from_request(), memory_id, pinned)
    return jsonify({"status": "ok", "pinned": pinned})


@memory_bp.route("/memories/relevant", methods=["GET"])
def get_relevant_memories():
    """
    Get memories relevant to a query.
    Query param: q (query text)
    Returns: Array of relevant memory objects
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    query = request.args.get("q", "")
    
    if not query:
        return jsonify([])

    relevant = memory.get_relevant_memories(get_user_id_from_request(), query, max_results=7)
    return jsonify(relevant)
