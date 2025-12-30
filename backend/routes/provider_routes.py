"""
Provider routes.

Provides AI provider management endpoints including CRUD operations,
health monitoring, and metadata management.
"""

from flask import Blueprint, jsonify, request

provider_bp = Blueprint('provider', __name__, url_prefix='/api/providers')


@provider_bp.route("", methods=["GET"])
def list_providers():
    """
    List all AI providers.
    Returns: Array of provider objects (without API keys for security)
    """
    from app import provider_registry

    providers = provider_registry.list()

    # Never expose API keys
    safe = []
    for p in providers:
        safe.append({
            "id": p["id"],
            "name": p["name"],
            "type": p["type"],
            "base_url": p.get("base_url"),
            "model": p.get("model"),
            "enabled": p.get("enabled", True),
        })

    return jsonify(safe)


@provider_bp.route("", methods=["POST"])
def upsert_provider():
    """
    Create or update an AI provider.
    Request body: { "id": "...", "name": "...", "type": "...", "model": "...", "api_key": "...", ... }
    Returns: { "status": "ok" }
    """
    from app import provider_registry, memory

    data = request.json

    provider_registry.upsert({
        "id": data["id"],
        "name": data["name"],
        "type": data["type"],
        "base_url": data.get("base_url"),
        "model": data.get("model"),
        "api_key": data.get("api_key"),
        "enabled": data.get("enabled", True),
    })

    # Initialize metadata for new providers
    memory.init_provider_metadata(data["id"])

    return jsonify({"status": "ok"})


@provider_bp.route("/<provider_id>", methods=["DELETE"])
def delete_provider(provider_id):
    """
    Delete an AI provider.
    Returns: { "status": "ok" }
    """
    from app import provider_registry, memory

    provider_registry.delete(provider_id)

    # Clean up metadata and request logs for deleted provider
    memory.delete_provider_metadata(provider_id)

    return jsonify({"status": "ok"})


@provider_bp.route("/health", methods=["GET"])
def get_provider_health():
    """
    Get health summary for all providers.
    Returns: Health summary object with provider metrics
    """
    from app import memory

    summary = memory.get_provider_health_summary()
    
    return jsonify(summary)


@provider_bp.route("/<provider_id>/metadata", methods=["GET"])
def get_provider_metadata_endpoint(provider_id):
    """
    Get metadata for a specific provider.
    Returns: Provider metadata object
    """
    from app import memory

    metadata = memory.get_provider_metadata(provider_id)
    
    if not metadata:
        return jsonify({"error": "Provider not found"}), 404
    
    return jsonify(metadata)


@provider_bp.route("/<provider_id>/metadata", methods=["POST"])
def update_provider_metadata_endpoint(provider_id):
    """
    Update cost metadata for a provider.
    Request body: { "cost_per_1k_input": N, "cost_per_1k_output": N }
    Returns: { "status": "ok" }
    """
    from app import memory

    data = request.json

    memory.init_provider_metadata(
        provider_id,
        cost_per_1k_input=data.get("cost_per_1k_input", 0),
        cost_per_1k_output=data.get("cost_per_1k_output", 0),
    )

    return jsonify({"status": "ok"})


@provider_bp.route("/<provider_id>/health/reset", methods=["POST"])
def reset_provider_health(provider_id):
    """
    Reset health metrics for a provider.
    Clears all failure counts and circuit breaker status.
    Returns: { "status": "ok" }
    """
    from app import memory

    # Reset health metrics to healthy state
    memory.reset_provider_health(provider_id)

    return jsonify({"status": "ok"})


@provider_bp.route("/costs", methods=["GET"])
def get_provider_costs():
    """
    Get cost summary for all providers.
    Query params:
        - days: Number of days to look back (7, 30, 90, or omit for all-time)
    Returns: {
        "providers": [...],
        "total_cost_usd": float,
        "period_days": int or null
    }
    """
    from app import memory

    days_param = request.args.get("days")
    days = None if days_param is None else int(days_param)

    costs = memory.get_provider_costs(days)
    return jsonify(costs)


@provider_bp.route("/voice-costs", methods=["GET"])
def get_voice_costs():
    """
    Get cost summary for voice services (TTS/STT).
    Query params:
        - days: Number of days to look back (7, 30, 90, or omit for all-time)
    Returns: {
        "services": [...],
        "total_cost_usd": float,
        "total_requests": int,
        "period_days": int or null
    }
    """
    from app import memory

    days_param = request.args.get("days")
    days = None if days_param is None else int(days_param)

    costs = memory.get_voice_costs(days)
    return jsonify(costs)
