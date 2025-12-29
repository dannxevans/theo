"""
Session routes.

Provides session management endpoints including listing, retrieval, deletion,
export, forking, and title generation.
"""

from flask import Blueprint, jsonify, request, Response
import json
import logging
import uuid

session_bp = Blueprint('session', __name__, url_prefix='/api')


@session_bp.route("/session/<session_id>", methods=["GET"])
def get_session(session_id):
    """
    Get session summary.
    Returns: { "session_id": "...", "summary": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    summary = memory.get_session_summary(session_id)
    
    return {
        "session_id": session_id,
        "summary": summary
    }


@session_bp.route("/sessions", methods=["GET"])
def list_sessions():
    """
    List all sessions for the current user, filtered by current mode.
    Returns: [{ "id": "...", "title": "...", "mode": "...", "summary": "..." }, ...]
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id and current mode from auth token
    user_id = None
    current_mode = None

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]
            # Get current mode
            mode_config = memory.get_user_mode(user_id)
            if mode_config:
                current_mode = mode_config.get("active_mode", "personal")

    # Filter sessions by user_id and current mode
    sessions = memory.list_sessions(user_id=user_id, mode=current_mode)

    response = []
    for s in sessions:
        response.append({
            "id": s["id"],
            "title": s.get("title"),
            "mode": s.get("mode", "personal"),
            "summary": s.get("summary"),
        })

    return jsonify(response)


@session_bp.route("/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    """
    Fetch all messages for a session.
    Returns normalized message array for frontend.
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    
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
            "metadata": t.get("metadata"),
        }
        for t in turns
    ])


@session_bp.route("/sessions/<session_id>/mode", methods=["GET"])
def get_session_mode(session_id):
    """
    Get the mode for a specific session.
    Returns: { "mode": "work" | "personal" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    mode = memory.get_session_mode(session_id)

    if mode is None:
        return jsonify({"error": "Session not found"}), 404

    return jsonify({"mode": mode})


@session_bp.route("/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    """
    Delete a session and all its messages.
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    memory.delete_session(session_id)

    return jsonify({"status": "ok"})


@session_bp.route("/sessions/<session_id>/export", methods=["GET"])
def export_session(session_id):
    """
    Export a conversation in JSON or Markdown format.
    Query param: format=json|markdown (default: json)
    Returns: File download with conversation data.
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
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


@session_bp.route("/sessions/<session_id>/fork", methods=["POST"])
def fork_session(session_id):
    """
    Create a new session as a fork/branch of the current one.
    Copies all messages up to an optional turn_index (or all if not specified).
    Request body (optional): { "turn_index": 5, "title": "Forked conversation" }
    Returns: { "session_id": "...", "status": "ok", "messages_copied": N }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    
    data = request.json or {}
    turn_index = data.get("turn_index")
    new_title = data.get("title")

    # Generate new session ID
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


@session_bp.route("/sessions/<session_id>/generate-title", methods=["POST"])
def generate_session_title(session_id):
    """
    Generate an AI-powered title for a session based on its first few messages.
    Returns: { "title": "Generated title" }
    """
    from core.memory import MemoryStore
    from config import Config
    from core.router import route_request

    memory = MemoryStore(Config.DATABASE_URL)
    
    # Get first few turns to understand the conversation topic
    turns = memory.get_recent_turns(session_id, limit=6)

    if not turns or len(turns) == 0:
        return jsonify({"title": "New chat"}), 200

    # Build a concise summary of the conversation start
    conversation_text = ""
    for turn in turns[:4]:  # Use first 2 exchanges (4 turns max)
        role = "User" if turn["role"] == "user" else "Assistant"
        content = turn["content"][:200]  # Limit content length
        conversation_text += f"{role}: {content}\n"

    # Use a provider to generate the title
    try:
        # Build minimal context for title generation
        title_prompt = f"""Based on this conversation, generate a concise, descriptive title.

Requirements:
- Maximum 50 characters
- Be specific and informative
- Use proper capitalization
- Do NOT include quotes or punctuation at the end
- Respond ONLY with the title, nothing else

Conversation:
{conversation_text}

Title:"""

        router_context = {
            "text": title_prompt,
            "session_id": session_id,
            "memory": memory,
            "forced_provider": None,  # Let router pick best provider
            "force_intent": "general"  # Force general intent to avoid action routing
        }

        result = route_request(router_context)
        generated_title = result.get("text", "New chat").strip()

        # Clean up the title
        # Remove quotes if present
        generated_title = generated_title.strip('"').strip("'").strip()

        # Remove trailing punctuation except for necessary ones
        while generated_title and generated_title[-1] in '.,:;!?':
            generated_title = generated_title[:-1].strip()

        # Limit length intelligently - if too long, truncate at word boundary
        if len(generated_title) > 50:
            # Try to truncate at last complete word before 47 chars
            truncated = generated_title[:47]
            last_space = truncated.rfind(' ')
            if last_space > 30:  # Only truncate at word if we keep enough
                generated_title = truncated[:last_space] + "..."
            else:
                generated_title = truncated + "..."

        # Save the title
        memory.save_session_title(session_id, generated_title)

        return jsonify({"title": generated_title})

    except Exception as e:
        logging.error(f"Failed to generate title: {e}")
        # Fallback to first user message as title
        first_user = next((t for t in turns if t["role"] == "user"), None)
        if first_user:
            fallback_title = first_user["content"][:60]
            if len(first_user["content"]) > 60:
                fallback_title += "..."
            memory.save_session_title(session_id, fallback_title)
            return jsonify({"title": fallback_title})
        
        return jsonify({"title": "New chat"})
