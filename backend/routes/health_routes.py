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
        # Proactively refresh token if it's close to expiry
        # This ensures tokens are kept fresh even when M365 features aren't actively used
        from actions.m365_provider import M365Provider
        from datetime import timedelta

        expires_at = creds.get("expires_at")
        now = datetime.utcnow()

        # Check if token needs refresh (within 5 minutes of expiry)
        if expires_at and now >= (expires_at - timedelta(minutes=5)):
            try:
                logging.info("[HEALTH] M365 token expiring soon, attempting proactive refresh...")
                provider = M365Provider(
                    access_token=creds["access_token"],
                    refresh_token=creds["refresh_token"],
                    expires_at=expires_at,
                    user_id=user["id"],
                    memory_store=memory
                )
                # This will trigger token refresh if needed
                provider._ensure_token_valid()

                # Reload credentials after refresh
                creds = memory.get_m365_credentials(user["id"])
                expires_at = creds.get("expires_at")
                logging.info(f"[HEALTH] Token refreshed successfully. New expiry: {expires_at}")
            except Exception as e:
                logging.error(f"[HEALTH] Proactive token refresh failed: {e}")

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

    # Get WHOOP integration status
    whoop_integration = {"connected": False}
    whoop_creds = memory.get_whoop_credentials(user["id"])

    if whoop_creds:
        # Calculate hours until expiry
        expires_at = whoop_creds.get("expires_at")
        hours_until_expiry = None
        if expires_at:
            delta = expires_at - datetime.utcnow()
            hours_until_expiry = round(delta.total_seconds() / 3600, 1)

        whoop_integration = {
            "connected": True,
            "whoop_user_id": whoop_creds.get("whoop_user_id"),
            "token_valid": whoop_creds.get("is_valid", False),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "hours_until_expiry": hours_until_expiry,
            "last_refreshed_at": whoop_creds.get("last_refreshed_at").isoformat() if whoop_creds.get("last_refreshed_at") else None,
            "last_error": whoop_creds.get("last_error")
        }

    # Get Plex integration status
    plex_integration = {"connected": False}
    plex_creds = memory.get_plex_credentials(user["id"])

    if plex_creds:
        plex_integration = {
            "connected": True,
            "plex_user_id": plex_creds.get("plex_user_id"),
            "plex_username": plex_creds.get("plex_username"),
            "server_name": plex_creds.get("server_name"),
            "server_url": plex_creds.get("server_url"),
            "token_valid": plex_creds.get("is_valid", False),
            "last_error": plex_creds.get("last_error"),
            "updated_at": plex_creds.get("updated_at").isoformat() if plex_creds.get("updated_at") else None
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

    # Get feature providers
    import sqlite3
    db_path = Config.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, provider_type, provider_name, is_enabled, created_at, updated_at
        FROM feature_providers
        WHERE user_id = ?
    """, (str(user["id"]),))

    feature_providers = []
    prefs = memory.get_all(str(user["id"]))

    for row in cursor.fetchall():
        # Check for API key and APP ID
        api_key_name = f"feature_provider_{row['provider_type']}_api_key"
        app_id_name = f"feature_provider_{row['provider_type']}_app_id"

        has_api_key = api_key_name in prefs and bool(prefs[api_key_name])
        has_app_id = app_id_name in prefs and bool(prefs[app_id_name])

        # Get usage statistics from logs
        cursor.execute("""
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_requests,
                AVG(latency_ms) as avg_latency_ms,
                MAX(CASE WHEN success = 1 THEN created_at ELSE NULL END) as last_success_at,
                MAX(CASE WHEN success = 0 THEN created_at ELSE NULL END) as last_failure_at
            FROM feature_provider_usage_logs
            WHERE user_id = ? AND provider_type = ?
        """, (str(user["id"]), row["provider_type"]))

        usage_stats = cursor.fetchone()
        total_requests = usage_stats["total_requests"] or 0
        failed_requests = usage_stats["failed_requests"] or 0
        success_rate = ((total_requests - failed_requests) / total_requests * 100) if total_requests > 0 else 0
        avg_latency_ms = int(usage_stats["avg_latency_ms"]) if usage_stats["avg_latency_ms"] else 0

        # Determine health status based on API key, enabled state, and success rate
        health_status = "unknown"
        if has_api_key and row["is_enabled"]:
            if total_requests == 0:
                health_status = "unknown"
            elif success_rate >= 95:
                health_status = "healthy"
            elif success_rate >= 70:
                health_status = "warning"
            else:
                health_status = "error"
        elif row["is_enabled"]:
            health_status = "warning"  # Enabled but no API key
        else:
            health_status = "disabled"

        feature_providers.append({
            "id": row["id"],
            "provider_type": row["provider_type"],
            "provider_name": row["provider_name"],
            "is_enabled": bool(row["is_enabled"]),
            "health_status": health_status,
            "total_requests": total_requests,
            "failed_requests": failed_requests,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": avg_latency_ms,
            "last_success_at": usage_stats["last_success_at"],
            "last_failure_at": usage_stats["last_failure_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })

    conn.close()

    return jsonify({
        "ai_providers": ai_providers,
        "m365_integration": m365_integration,
        "whoop_integration": whoop_integration,
        "plex_integration": plex_integration,
        "service_providers": service_providers,
        "feature_providers": feature_providers
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
