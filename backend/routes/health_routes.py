"""
Health monitoring routes.

Provides health check endpoints for system monitoring and M365 integration status.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging
import json
import time

health_bp = Blueprint('health', __name__)


@health_bp.route("/health")
def health():
    """Simple health check endpoint."""
    return {"status": "ok", "service": "THEO-Backend"}, 200


@health_bp.route("/api/health")
def api_health():
    """API health check endpoint."""
    return {"status": "ok", "service": "THEO"}


@health_bp.route("/api/health/overview", methods=["GET"])
def get_health_overview():
    """
    Get comprehensive health overview of all system components.

    Returns AI providers, M365 integration, and service providers health status.
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

    # Get AI providers with metadata
    providers = memory.list_providers()
    ai_providers = []

    for provider in providers:
        metadata = memory.get_provider_metadata(provider["id"])

        # Handle case where metadata doesn't exist yet
        if not metadata:
            metadata = {
                "total_requests": 0,
                "failed_requests": 0,
                "health_status": "unknown",
                "circuit_breaker_open": False,
                "avg_latency_ms": 0,
                "last_success_at": None,
                "last_failure_at": None
            }

        # Calculate success rate
        total = metadata.get("total_requests", 0)
        failed = metadata.get("failed_requests", 0)
        success_rate = ((total - failed) / total * 100) if total > 0 else 0

        ai_providers.append({
            "id": provider["id"],
            "name": provider["name"],
            "type": provider["type"],
            "model": provider.get("model"),
            "enabled": provider["enabled"],
            "health_status": metadata.get("health_status", "unknown"),
            "circuit_breaker_open": metadata.get("circuit_breaker_open", False),
            "total_requests": total,
            "failed_requests": failed,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": metadata.get("avg_latency_ms", 0),
            "last_success_at": metadata.get("last_success_at").isoformat() if metadata.get("last_success_at") else None,
            "last_failure_at": metadata.get("last_failure_at").isoformat() if metadata.get("last_failure_at") else None
        })

    # Get M365 integration status
    m365_integration = {"connected": False}
    creds = memory.get_m365_credentials(user["id"])

    if creds:
        expires_at = creds.get("expires_at")
        now = datetime.utcnow()

        # Calculate hours until expiry
        hours_until_expiry = None
        if expires_at:
            delta = expires_at - now
            hours_until_expiry = round(delta.total_seconds() / 3600, 1)

        # Parse scopes
        scopes = []
        if creds.get("scope"):
            scopes = creds["scope"].split(" ")

        m365_integration = {
            "connected": True,
            "account": creds.get("user_principal_name"),
            "token_valid": creds.get("is_valid", False),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "hours_until_expiry": hours_until_expiry,
            "last_refreshed_at": creds.get("last_refreshed_at").isoformat() if creds.get("last_refreshed_at") else None,
            "last_error": creds.get("last_error"),
            "scopes": scopes
        }

    # Get service providers
    service_providers_list = memory.get_service_providers(user["id"])
    service_providers = []

    for sp in service_providers_list:
        # Parse booking URL from metadata
        booking_url = None
        try:
            if sp.get("additional_metadata"):
                metadata = json.loads(sp["additional_metadata"])
                booking_url = metadata.get("booking_url")
        except:
            pass

        service_providers.append({
            "id": sp["id"],
            "name": sp["name"],
            "category": sp["category"],
            "provider_type": sp["provider_type"],
            "is_enabled": sp.get("is_enabled", True),
            "health_status": sp.get("health_status", "unknown"),
            "last_synced_at": sp.get("last_synced_at").isoformat() if sp.get("last_synced_at") else None,
            "booking_url": booking_url
        })

    return jsonify({
        "ai_providers": ai_providers,
        "m365_integration": m365_integration,
        "service_providers": service_providers
    })


@health_bp.route("/api/health/test-m365", methods=["POST"])
def test_m365_health():
    """
    Perform live health check on M365 integration.
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

    # Check if M365 is connected
    creds = memory.get_m365_credentials(user["id"])

    if not creds:
        return jsonify({
            "healthy": False,
            "status": "not_connected",
            "error": "Microsoft 365 account not connected"
        })

    # Perform health check
    try:
        from actions.m365_provider import M365Provider

        start_time = time.time()

        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user["id"],
            memory_store=memory
        )

        health = provider.check_health()

        response_time_ms = int((time.time() - start_time) * 1000)
        health["response_time_ms"] = response_time_ms

        return jsonify(health)

    except Exception as e:
        logging.error(f"[API] M365 health check failed: {e}")
        return jsonify({
            "healthy": False,
            "status": "error",
            "last_check": datetime.utcnow().isoformat(),
            "error": str(e)
        })
