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

# Seed default intents if none exist
memory.seed_default_intents("local")

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

    # Pass the full result object so metadata can be extracted
    context_manager.update(session_id, text, result, provider_registry)
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
            router_context["session_id"] = session_id
            router_context["memory"] = memory
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

            # Pass the full result object so metadata can be extracted
            context_manager.update(session_id, text, result, provider_registry)

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
# Step 3: Provider Intelligence APIs
# =============================

@app.route("/api/providers/health", methods=["GET"])
def get_provider_health():
    """Get health summary for all providers"""
    summary = memory.get_provider_health_summary()
    return jsonify(summary)

@app.route("/api/providers/<provider_id>/metadata", methods=["GET"])
def get_provider_metadata_endpoint(provider_id):
    """Get metadata for a specific provider"""
    metadata = memory.get_provider_metadata(provider_id)
    if not metadata:
        return jsonify({"error": "Provider not found"}), 404
    return jsonify(metadata)

@app.route("/api/providers/<provider_id>/metadata", methods=["POST"])
def update_provider_metadata_endpoint(provider_id):
    """Update cost metadata for a provider"""
    data = request.json
    memory.init_provider_metadata(
        provider_id,
        cost_per_1k_input=data.get("cost_per_1k_input", 0),
        cost_per_1k_output=data.get("cost_per_1k_output", 0),
    )
    return jsonify({"status": "ok"})

# =============================
# Routing Preferences APIs
# =============================

# =============================
# Intent Management APIs
# =============================

@app.route("/api/intents", methods=["GET"])
def list_intents():
    """Get all user-defined intents."""
    intents = memory.list_intents("local")
    return jsonify(intents)

@app.route("/api/intents/<intent_id>", methods=["GET"])
def get_intent(intent_id):
    """Get a single intent by ID."""
    intent = memory.get_intent("local", intent_id)
    if not intent:
        return jsonify({"error": "Intent not found"}), 404
    return jsonify(intent)

@app.route("/api/intents", methods=["POST"])
def create_intent():
    """Create a new intent."""
    data = request.json
    intent_id = data.get("id")
    name = data.get("name")
    description = data.get("description", "")
    keywords = data.get("keywords", "")
    priority = data.get("priority", 0)
    enabled = data.get("enabled", True)

    if not intent_id or not name:
        return jsonify({"error": "id and name are required"}), 400

    try:
        memory.create_intent(
            user_id="local",
            intent_id=intent_id,
            name=name,
            description=description,
            keywords=keywords,
            priority=priority,
            enabled=enabled,
        )
        return jsonify({"status": "ok", "intent_id": intent_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/intents/<intent_id>", methods=["PUT"])
def update_intent(intent_id):
    """Update an existing intent."""
    data = request.json
    updates = {}

    # Only include fields that are present in the request
    if "name" in data:
        updates["name"] = data["name"]
    if "description" in data:
        updates["description"] = data["description"]
    if "keywords" in data:
        updates["keywords"] = data["keywords"]
    if "priority" in data:
        updates["priority"] = data["priority"]
    if "enabled" in data:
        updates["enabled"] = data["enabled"]

    try:
        memory.update_intent("local", intent_id, **updates)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/intents/<intent_id>", methods=["DELETE"])
def delete_intent(intent_id):
    """Delete an intent."""
    try:
        memory.delete_intent("local", intent_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
            "provider": t.get("provider_id"),
            "model": t.get("model"),
            "task_type": t.get("intent"),
        }
        for t in turns
    ])

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    memory.delete_session(session_id)
    return jsonify({"status": "ok"})

@app.route("/api/sessions/<session_id>/export", methods=["GET"])
def export_session(session_id):
    """
    Export a conversation in JSON or Markdown format.
    Query param: format=json|markdown (default: json)
    """
    export_format = request.args.get("format", "json").lower()

    # Get session metadata
    session_data = memory.list_sessions()
    session = next((s for s in session_data if s["id"] == session_id), None)

    # Get all messages
    turns = memory.get_recent_turns(session_id, limit=10000)

    if export_format == "markdown":
        # Generate markdown format
        lines = []
        if session:
            lines.append(f"# {session.get('title', 'Conversation')}")
            lines.append(f"\n**Session ID:** {session_id}")
            lines.append(f"**Created:** {session.get('created_at', 'Unknown')}")
            if session.get('summary'):
                lines.append(f"\n**Summary:** {session['summary']}")
            lines.append("\n---\n")

        for turn in turns:
            role = turn["role"].upper()
            content = turn["content"]
            timestamp = turn.get("created_at", "")

            if role == "USER":
                lines.append(f"## 👤 User")
            else:
                lines.append(f"## 🤖 Assistant")

            if timestamp:
                lines.append(f"*{timestamp}*\n")

            lines.append(content)
            lines.append("\n---\n")

        markdown_text = "\n".join(lines)

        return Response(
            markdown_text,
            mimetype="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=conversation_{session_id}.md"
            }
        )
    else:
        # JSON format
        export_data = {
            "session_id": session_id,
            "title": session.get("title") if session else None,
            "summary": session.get("summary") if session else None,
            "created_at": session.get("created_at").isoformat() if session and session.get("created_at") else None,
            "messages": [
                {
                    "role": t["role"],
                    "content": t["content"],
                    "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                }
                for t in turns
            ]
        }

        return Response(
            json.dumps(export_data, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=conversation_{session_id}.json"
            }
        )

@app.route("/api/sessions/<session_id>/fork", methods=["POST"])
def fork_session(session_id):
    """
    Create a new session as a fork/branch of the current one.
    Copies all messages up to an optional turn_index (or all if not specified).
    Request body (optional): { "turn_index": 5, "title": "Forked conversation" }
    """
    data = request.json or {}
    turn_index = data.get("turn_index")
    new_title = data.get("title")

    # Generate new session ID
    import uuid
    new_session_id = str(uuid.uuid4())

    # Get original messages
    original_turns = memory.get_recent_turns(session_id, limit=10000)

    # If turn_index specified, only copy up to that point
    if turn_index is not None:
        turns_to_copy = original_turns[:turn_index + 1]
    else:
        turns_to_copy = original_turns

    # Create new session and copy turns
    for turn in turns_to_copy:
        memory.save_turn(
            new_session_id,
            turn["role"],
            turn["content"]
        )

    # Set title for new session
    if new_title:
        memory.save_session_title(new_session_id, new_title)
    elif len(turns_to_copy) > 0:
        # Copy title from original session
        session_data = memory.list_sessions()
        original = next((s for s in session_data if s["id"] == session_id), None)
        if original and original.get("title"):
            memory.save_session_title(new_session_id, f"{original['title']} (fork)")

    return jsonify({
        "session_id": new_session_id,
        "status": "ok",
        "messages_copied": len(turns_to_copy)
    })

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

    # Initialize metadata for new providers
    memory.init_provider_metadata(data["id"])

    return jsonify({"status": "ok"})

@app.route("/api/providers/<provider_id>", methods=["DELETE"])
def delete_provider(provider_id):
    provider_registry.delete(provider_id)

    # Clean up metadata and request logs for deleted provider
    memory.delete_provider_metadata(provider_id)

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