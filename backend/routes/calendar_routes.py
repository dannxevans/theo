"""
Calendar routes.

Provides calendar query endpoint for natural language calendar interactions.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

calendar_bp = Blueprint('calendar', __name__, url_prefix='/api/calendar')


@calendar_bp.route("/query", methods=["POST"])
def query_calendar():
    """
    Query calendar using natural language.
    
    Request body: { "text": "What's on my calendar tomorrow?", "session_id": "..." }
    Returns: Calendar events or error message
    """
    from app import memory, context_manager, provider_registry
    from core.router import route_request

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

    # Get request data
    payload = request.json
    text = payload.get("text", "")
    session_id = payload.get("session_id", "default")

    if not text:
        return jsonify({"error": "No query text provided"}), 400

    # Build context for router
    context = {
        "text": text,
        "session_id": session_id,
        "user_id": user["id"],
        "memory": memory,
    }

    # Route through main router (will detect calendar intent and route to ActionRouter)
    try:
        result = route_request(context)

        # Log to conversation history
        context_manager.update(session_id, text, result, provider_registry)

        return jsonify(result)

    except Exception as e:
        logging.error(f"[API] Calendar query failed: {e}")
        return jsonify({
            "error": "Calendar query failed",
            "details": str(e)
        }), 500
