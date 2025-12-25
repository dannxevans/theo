# import eventlet
# eventlet.monkey_patch()
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.router import route_request, set_provider_registry, set_context_manager
from core.context import ContextManager
from core.memory import MemoryStore
from config import Config
from core.provider_registry import ProviderRegistry
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Response, stream_with_context
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

app = Flask(__name__)
# Wrap app with ProxyFix to correctly handle X-Forwarded headers from ALB (Application Load Balancer)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_SECURE"] = True

ALLOWED_ORIGINS = [
    # Local DEV
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.10.25:5173",
    "https://dev.theoai.uk",

    # Primary CloudFront domains
    "https://theoai.uk",
    "https://www.theoai.uk",
    "https://app.theoai.uk",

    # Secondary CloudFront domain
    "https://duckyfuzz.uk",
    "https://app.duckyfuzz.uk",
    "https://ai.duckyfuzz.uk",

    # (Optional but useful for debugging)
    "http://theo-alb-306035510.eu-west-2.elb.amazonaws.com"
]

CORS(
    app,
    resources={
        r"/api/*": {"origins": ALLOWED_ORIGINS},
    },
    supports_credentials=True,
)

@app.route("/health")
def health():
    return {"status": "ok", "service": "THEO-Backend"} , 200

memory = MemoryStore(Config.DATABASE_URL)
context_manager = ContextManager(memory)
provider_registry = ProviderRegistry(memory)
set_context_manager(context_manager)

# Inject provider registry into router
set_provider_registry(provider_registry)

@app.route("/api/health")
def api_health():
    return {"status": "ok", "service": "THEO"}

@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json
    session_id = payload.get("session_id", "default")
    text = payload.get("text", "")

    context = context_manager.build_context(session_id, text)
    result = route_request(context)

    context_manager.update(session_id, text, result["text"])
    return jsonify(result)

@app.route("/api/stream/<session_id>")
def stream_chat_sse(session_id):
    text = request.args.get("text", "")
    forced_provider = request.args.get("forced_provider")

    def event_stream():
        try:
            context = context_manager.build_context(session_id, text)

            router_context = dict(context)
            router_context["text"] = text
            if forced_provider:
                router_context["forced_provider"] = forced_provider

            # Route request (non-streaming, we chunk manually)
            result = route_request(router_context)

            full_text = result.get("text", "")
            chunk_size = 32

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            
            # Send metadata at end of stream
            end_payload = {
                "provider": result.get("provider"),
                "model": result.get("model"),
                "task_type": result.get("task_type"),
                "fallback_reason": result.get("fallback_reason"),
                "routing": result.get("routing"),
            }

            yield "event: end\n"
            yield f"data: {json.dumps(end_payload)}\n\n"

            context_manager.update(session_id, text, full_text)

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        },
    )

@app.route("/api/memory/remember", methods=["POST"])
def remember():
    """Legacy memory endpoint (kept for backwards compatibility)"""
    data = request.json
    memory.remember(
        user_id="local",
        key=data["key"],
        value=data["value"]
    )
    return jsonify({"status": "ok"})

@app.route("/api/memory/forget", methods=["POST"])
def forget():
    """Legacy memory endpoint (kept for backwards compatibility)"""
    data = request.json
    memory.forget("local", data["key"])
    return jsonify({"status": "ok"})

# =============================
# Step 2: Structured Memory APIs
# =============================

@app.route("/api/memories", methods=["GET"])
def list_memories():
    """
    Get all structured memories for the user.
    Optional query params:
    - type: filter by memory type (fact, preference, goal, context)
    - limit: max results
    """
    memory_type = request.args.get("type")
    limit = request.args.get("limit", type=int)

    memories = memory.get_memories("local", memory_type=memory_type, limit=limit)
    return jsonify(memories)

@app.route("/api/memories", methods=["POST"])
def create_memory():
    """
    Store a new structured memory.
    Body: {type, key, value, pinned}
    """
    data = request.json
    memory.store_memory(
        user_id="local",
        memory_type=data.get("type", "fact"),
        key=data["key"],
        value=data["value"],
        pinned=data.get("pinned", False),
    )
    return jsonify({"status": "ok"})

@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def delete_memory_endpoint(memory_id):
    """Delete a memory by ID"""
    memory.delete_memory("local", memory_id)
    return jsonify({"status": "ok"})

@app.route("/api/memories/<int:memory_id>/pin", methods=["POST"])
def pin_memory_endpoint(memory_id):
    """Pin or unpin a memory"""
    data = request.json
    pinned = data.get("pinned", True)
    memory.pin_memory("local", memory_id, pinned)
    return jsonify({"status": "ok", "pinned": pinned})

@app.route("/api/memories/relevant", methods=["GET"])
def get_relevant_memories():
    """
    Get memories relevant to a query.
    Query param: q (query text)
    """
    query = request.args.get("q", "")
    if not query:
        return jsonify([])

    relevant = memory.get_relevant_memories("local", query, max_results=7)
    return jsonify(relevant)

# =============================
# Routing Preferences APIs
# =============================

@app.route("/api/routing", methods=["GET"])
def get_routing_preferences():
    prefs = memory.get_routing_preferences("local")
    return jsonify(prefs)

@app.route("/api/routing", methods=["POST"])
def set_routing_preference():
    data = request.json
    memory.set_routing_preference(
        user_id="local",
        intent=data["intent"],
        provider_id=data["provider_id"],
    )
    return jsonify({"status": "ok"})

@app.route("/api/routing/<intent>", methods=["DELETE"])
def delete_routing_preference(intent):
    memory.delete_routing_preference("local", intent)
    return jsonify({"status": "ok"})

@app.route("/api/session/<session_id>", methods=["GET"])
def get_session(session_id):
    summary = memory.get_session_summary(session_id)
    return {
        "session_id": session_id,
        "summary": summary
    }


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = memory.list_sessions()

    response = []
    for s in sessions:
        response.append({
            "id": s["id"],
            "title": s.get("title"),
            "summary": s.get("summary"),
        })

    return jsonify(response)

# New route: fetch messages for a session
@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    # Load all conversation turns for this session
    turns = memory.get_recent_turns(session_id, limit=1000)

    # Normalise shape for frontend
    return jsonify([
        {
            "role": t["role"],
            "content": t["content"],
            "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
        }
        for t in turns
    ])

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    memory.delete_session(session_id)
    return jsonify({"status": "ok"})

# Provider Management APIs

@app.route("/api/providers", methods=["GET"])
def list_providers():
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

@app.route("/api/providers", methods=["POST"])
def upsert_provider():
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

    return jsonify({"status": "ok"})

@app.route("/api/providers/<provider_id>", methods=["DELETE"])
def delete_provider(provider_id):
    provider_registry.delete(provider_id)
    return jsonify({"status": "ok"})

# =============================
# Debug Settings API
# =============================

@app.route("/api/settings/debug", methods=["GET"])
def get_debug_setting():
    # Read from preferences, not routing
    prefs = memory.get_all("local")
    value = prefs.get("debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@app.route("/api/settings/debug", methods=["POST"])
def set_debug_setting():
    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    memory.remember(
        user_id="local",
        key="debug_enabled",
        value=str(enabled).lower()
    )

    return jsonify({"status": "ok", "enabled": enabled})

def debug_log(message):
    try:
        prefs = memory.get_all("local")
        enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"
        if enabled:
            logging.info(f"[DEBUG] {message}")
    except Exception as e:
        logging.warning(f"[DEBUG-LOGGING-ERROR] {e}")

        

if __name__ == "__main__":
    print("THEO backend starting on port 1066")
    app.run(host="0.0.0.0", port=1066, debug=True)