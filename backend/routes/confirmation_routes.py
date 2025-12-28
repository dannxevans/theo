"""
Confirmation routes.

Provides confirmation management endpoints for user action approvals.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

confirmation_bp = Blueprint('confirmation', __name__, url_prefix='/api/confirmations')


@confirmation_bp.route("/pending", methods=["GET"])
def get_pending_confirmations():
    """
    Get all pending confirmations for the authenticated user.
    Returns: { "confirmations": [...], "count": N }
    """
    from core.memory import MemoryStore
    from config import Config
    from core.confirmation_manager import ConfirmationManager

    memory = MemoryStore(Config.DATABASE_URL)
    confirmation_manager = ConfirmationManager(memory)

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

    # Get pending confirmations
    try:
        confirmations = confirmation_manager.get_pending_confirmations(user["id"])

        # Format for frontend
        formatted_confirmations = []
        for conf in confirmations:
            formatted_confirmations.append({
                "confirmation_id": conf.get("id"),
                "action_id": conf.get("action_id"),
                "message": conf.get("confirmation_message"),
                "action_type": conf.get("action_type"),
                "category": conf.get("category"),
                "created_at": conf.get("created_at").isoformat() if conf.get("created_at") else None,
                "expires_at": conf.get("expires_at").isoformat() if conf.get("expires_at") else None,
            })

        return jsonify({
            "confirmations": formatted_confirmations,
            "count": len(formatted_confirmations)
        })

    except Exception as e:
        logging.error(f"[API] Get pending confirmations failed: {e}")
        return jsonify({
            "error": "Failed to get confirmations",
            "details": str(e)
        }), 500


@confirmation_bp.route("/<int:confirmation_id>/approve", methods=["POST"])
def approve_confirmation(confirmation_id):
    """
    Approve a confirmation and execute the action.
    Returns: { "status": "approved", "message": "...", "action_result": {...} }
    """
    from core.memory import MemoryStore
    from config import Config
    from core.confirmation_manager import ConfirmationManager

    memory = MemoryStore(Config.DATABASE_URL)
    confirmation_manager = ConfirmationManager(memory)

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

    # Approve confirmation
    try:
        result = confirmation_manager.approve_confirmation(confirmation_id, user["id"])

        if result["status"] == "success":
            return jsonify({
                "status": "approved",
                "message": result["message"],
                "action_result": result.get("action_result")
            })
        else:
            return jsonify({
                "status": "error",
                "message": result["message"]
            }), 400

    except Exception as e:
        logging.error(f"[API] Approve confirmation failed: {e}")
        return jsonify({
            "error": "Failed to approve confirmation",
            "details": str(e)
        }), 500


@confirmation_bp.route("/<int:confirmation_id>/reject", methods=["POST"])
def reject_confirmation(confirmation_id):
    """
    Reject a confirmation request.
    Request body (optional): { "reason": "User's reason for rejection" }
    Returns: { "status": "rejected", "message": "..." }
    """
    from core.memory import MemoryStore
    from config import Config
    from core.confirmation_manager import ConfirmationManager

    memory = MemoryStore(Config.DATABASE_URL)
    confirmation_manager = ConfirmationManager(memory)

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

    # Get reason if provided
    payload = request.json or {}
    reason = payload.get("reason")

    # Reject confirmation
    try:
        result = confirmation_manager.reject_confirmation(confirmation_id, user["id"], reason)

        if result["status"] == "success":
            return jsonify({
                "status": "rejected",
                "message": result["message"]
            })
        else:
            return jsonify({
                "status": "error",
                "message": result["message"]
            }), 400

    except Exception as e:
        logging.error(f"[API] Reject confirmation failed: {e}")
        return jsonify({
            "error": "Failed to reject confirmation",
            "details": str(e)
        }), 500
