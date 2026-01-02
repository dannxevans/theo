"""
Routine routes.

Provides endpoints for managing user-defined routines.
"""

from flask import Blueprint, jsonify, request, g
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime
import json
import logging

routine_bp = Blueprint('routine', __name__, url_prefix='/api')


@routine_bp.route("/routines", methods=["GET"])
def get_routines():
    """
    Get all routines for the authenticated user.
    All routines are user-defined and editable.
    """
    from app import memory

    # Get authenticated user
    user_id = g.get('user_id')
    if not user_id:
        user_id = DEFAULT_USER_ID  # Default user for non-authenticated requests

    try:
        # Get user-defined routines from database
        user_routines = memory.get_user_routines(user_id)

        # Convert user routines to API format
        routines_list = []
        for routine in user_routines:
            routines_list.append({
                "id": routine["id"],
                "name": routine["name"],
                "trigger": json.loads(routine["triggers"])[0] if routine["triggers"] else "",
                "triggers": json.loads(routine["triggers"]),
                "actions": json.loads(routine["actions"]),
                "consolidation_prompt": routine.get("consolidation_prompt", ""),
                "enabled": bool(routine["enabled"]),
                "editable": True
            })

        return jsonify({"routines": routines_list})

    except Exception as e:
        logging.error(f"[ROUTINES] Failed to get routines: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routines", methods=["POST"])
def create_routine():
    """
    Create a new user-defined routine.
    Request body: { "name", "triggers", "actions", "consolidation_prompt" }
    """
    from app import memory

    # Get authenticated user
    user_id = g.get('user_id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    try:
        data = request.json
        name = data.get("name")
        triggers = data.get("triggers", [])
        actions = data.get("actions", [])
        consolidation_prompt = data.get("consolidation_prompt", "")

        if not name:
            return jsonify({"error": "Routine name is required"}), 400

        if not triggers or len(triggers) == 0:
            return jsonify({"error": "At least one trigger is required"}), 400

        if not actions or len(actions) == 0:
            return jsonify({"error": "At least one action is required"}), 400

        # Create routine
        routine_id = memory.create_user_routine(
            user_id=user_id,
            name=name,
            triggers=triggers,
            actions=actions,
            consolidation_prompt=consolidation_prompt
        )

        return jsonify({
            "success": True,
            "routine_id": routine_id,
            "message": "Routine created successfully"
        })

    except Exception as e:
        logging.error(f"[ROUTINES] Failed to create routine: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routines/<int:routine_id>", methods=["PUT"])
def update_routine(routine_id):
    """
    Update an existing user-defined routine.
    Request body: { "name", "triggers", "actions", "consolidation_prompt", "enabled" }
    """
    from app import memory

    # Get authenticated user
    user_id = g.get('user_id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    try:
        data = request.json

        # Verify routine belongs to user
        routine = memory.get_user_routine(routine_id, user_id)
        if not routine:
            return jsonify({"error": "Routine not found"}), 404

        # Update routine
        memory.update_user_routine(
            routine_id=routine_id,
            user_id=user_id,
            name=data.get("name"),
            triggers=data.get("triggers"),
            actions=data.get("actions"),
            consolidation_prompt=data.get("consolidation_prompt"),
            enabled=data.get("enabled")
        )

        return jsonify({
            "success": True,
            "message": "Routine updated successfully"
        })

    except Exception as e:
        logging.error(f"[ROUTINES] Failed to update routine: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@routine_bp.route("/routines/<int:routine_id>", methods=["DELETE"])
def delete_routine(routine_id):
    """
    Delete a user-defined routine.
    """
    from app import memory

    # Get authenticated user
    user_id = g.get('user_id')
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Verify routine belongs to user
        routine = memory.get_user_routine(routine_id, user_id)
        if not routine:
            return jsonify({"error": "Routine not found"}), 404

        # Delete routine
        memory.delete_user_routine(routine_id, user_id)

        return jsonify({
            "success": True,
            "message": "Routine deleted successfully"
        })

    except Exception as e:
        logging.error(f"[ROUTINES] Failed to delete routine: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
