"""
Service provider routes.

Provides service provider management endpoints for external services
like calendars, email providers, etc.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

service_provider_bp = Blueprint('service_provider', __name__, url_prefix='/api/service-providers')


@service_provider_bp.route("", methods=["GET"])
def get_service_providers():
    """
    Get all service providers for the authenticated user.
    Query params: category (optional filter)
    Returns: { "providers": [...] }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

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

    # Get optional category filter
    category = request.args.get("category")

    # Get service providers
    providers = memory.get_service_providers(user["id"], category=category)

    return jsonify({"providers": providers})


@service_provider_bp.route("", methods=["POST"])
def create_service_provider():
    """
    Create a new service provider.
    Request body: { "name": "...", "category": "...", "provider_type": "...", ... }
    Returns: { "success": true, "provider_id": N, "message": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

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
    data = request.get_json()

    # Required fields
    name = data.get("name")
    category = data.get("category")
    provider_type = data.get("provider_type")

    if not name or not category or not provider_type:
        return jsonify({"error": "Missing required fields: name, category, provider_type"}), 400

    # Create service provider
    try:
        provider_id = memory.store_service_provider(
            user_id=user["id"],
            name=name,
            category=category,
            provider_type=provider_type,
            capabilities=data.get("capabilities"),
            api_base_url=data.get("api_base_url"),
            auth_method=data.get("auth_method"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            token_expires_at=data.get("token_expires_at"),
            trust_level=data.get("trust_level", "manual"),
            booking_method=data.get("booking_method"),
            preferred_for_category=data.get("preferred_for_category", False),
            additional_metadata=data.get("additional_metadata")
        )

        logging.info(f"[API] Service provider created: {provider_id} for user {user['id']}")

        return jsonify({
            "success": True,
            "provider_id": provider_id,
            "message": f"Service provider '{name}' created successfully"
        }), 201

    except Exception as e:
        logging.error(f"[API] Failed to create service provider: {e}")
        return jsonify({"error": f"Failed to create service provider: {str(e)}"}), 500


@service_provider_bp.route("/<int:provider_id>", methods=["GET"])
def get_service_provider(provider_id):
    """
    Get a single service provider by ID.
    Returns: { "provider": {...} }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

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

    # Get service provider
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({"provider": provider})


@service_provider_bp.route("/<int:provider_id>", methods=["PUT"])
def update_service_provider(provider_id):
    """
    Update a service provider.
    Request body: Fields to update
    Returns: { "success": true, "message": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

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

    # Get existing provider
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    # Get update data
    data = request.get_json()

    # Update service provider
    try:
        memory.update_service_provider(
            provider_id=provider_id,
            name=data.get("name"),
            category=data.get("category"),
            provider_type=data.get("provider_type"),
            capabilities=data.get("capabilities"),
            api_base_url=data.get("api_base_url"),
            auth_method=data.get("auth_method"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            token_expires_at=data.get("token_expires_at"),
            trust_level=data.get("trust_level"),
            booking_method=data.get("booking_method"),
            preferred_for_category=data.get("preferred_for_category"),
            additional_metadata=data.get("additional_metadata"),
            is_enabled=data.get("is_enabled")
        )

        logging.info(f"[API] Service provider {provider_id} updated by user {user['id']}")

        return jsonify({
            "success": True,
            "message": "Service provider updated successfully"
        })

    except Exception as e:
        logging.error(f"[API] Failed to update service provider: {e}")
        return jsonify({"error": f"Failed to update service provider: {str(e)}"}), 500


@service_provider_bp.route("/<int:provider_id>", methods=["DELETE"])
def delete_service_provider_endpoint(provider_id):
    """
    Delete a service provider.
    Returns: { "success": true, "message": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

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

    # Get provider to verify ownership
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    # Delete service provider
    try:
        memory.delete_service_provider(provider_id, user["id"])

        logging.info(f"[API] Service provider {provider_id} deleted by user {user['id']}")

        return jsonify({
            "success": True,
            "message": "Service provider deleted successfully"
        })

    except Exception as e:
        logging.error(f"[API] Failed to delete service provider: {e}")
        return jsonify({"error": f"Failed to delete service provider: {str(e)}"}), 500
