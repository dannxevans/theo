"""
Memory routes.

Provides memory management endpoints for storing, retrieving, and searching
user memories.
"""

from flask import Blueprint, jsonify, request

memory_bp = Blueprint('memory', __name__, url_prefix='/api')


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
        user_id="local",
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
    
    memory.forget("local", data["key"])
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

    memories = memory.get_memories("local", memory_type=memory_type, limit=limit)
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
        user_id="local",
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
    memory.delete_memory("local", memory_id)
    
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
    
    memory.pin_memory("local", memory_id, pinned)
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

    relevant = memory.get_relevant_memories("local", query, max_results=7)
    return jsonify(relevant)
