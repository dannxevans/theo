"""
Planning routes.

Provides REST API endpoints for context-aware planning:
- POST /api/planning/analyze - Analyze activity and get enriched context
- GET /api/planning/calendar-enriched - Get calendar events with weather/traffic
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging

from core.planning_service import PlanningService

planning_bp = Blueprint('planning', __name__)


@planning_bp.route("/api/planning/analyze", methods=["POST"])
def analyze_activity():
    """
    Analyze user activity and return enriched context.

    Request body:
        {
            "text": "I'm going shopping at Westfield tomorrow at 2pm",
            "session_id": "session-123",
            "user_id": 1
        }

    Returns:
        {
            "activity": {
                "type": "shopping",
                "location": "Westfield",
                "time": "2024-01-15T14:00:00"
            },
            "context": {
                "weather": {...},
                "traffic": {...},
                "calendar_conflicts": [...],
                "recommendations": [...]
            }
        }
    """
    from core.memory import MemoryStore
    from config import Config

    data = request.get_json()

    if not data or not data.get("text"):
        return jsonify({"error": "Missing 'text' field"}), 400

    user_text = data["text"]
    session_id = data.get("session_id", "")
    user_id = data.get("user_id", 1)

    try:
        memory = MemoryStore(Config.DATABASE_URL)
        planning_service = PlanningService(memory)

        # Analyze activity
        activity_data = planning_service.analyze_activity(
            user_text, session_id, str(user_id)
        )

        if not activity_data or not activity_data.get("has_planning_intent"):
            return jsonify({
                "has_planning_intent": False,
                "message": "No planning intent detected. Please include location and/or time."
            })

        # Get enriched context
        context_data = planning_service.get_context_for_activity(
            activity_data, str(user_id)
        )

        return jsonify({
            "has_planning_intent": True,
            "activity": {
                "type": activity_data.get("activity_type"),
                "location": activity_data.get("location"),
                "time": activity_data.get("time")
            },
            "context": {
                "weather": context_data.get("weather"),
                "traffic": context_data.get("traffic"),
                "calendar_conflicts": context_data.get("calendar_conflicts"),
                "recommendations": context_data.get("recommendations")
            }
        })

    except Exception as e:
        logging.error(f"[PLANNING API] Error analyzing activity: {e}")
        return jsonify({"error": str(e)}), 500


@planning_bp.route("/api/planning/calendar-enriched", methods=["GET"])
def get_enriched_calendar():
    """
    Get calendar events enriched with weather and traffic data.

    Query parameters:
        - start_date: ISO format date (default: today)
        - end_date: ISO format date (default: 7 days from start)
        - user_id: User ID (default: 1)

    Returns:
        {
            "events": [
                {
                    "id": "event-1",
                    "subject": "Meeting",
                    "start": "2024-01-15T14:00:00",
                    "end": "2024-01-15T15:00:00",
                    "location": "London",
                    "weather": {
                        "temperature": 15,
                        "description": "cloudy",
                        "icon": "☁️"
                    }
                }
            ]
        }
    """
    from core.memory import MemoryStore
    from config import Config
    from actions.m365_provider import M365Provider

    user_id = request.args.get("user_id", 1, type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    # Default to today + 7 days
    if not start_date:
        start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = start.isoformat()
    else:
        start = datetime.fromisoformat(start_date)

    if not end_date:
        end = start + timedelta(days=7)
        end_date = end.isoformat()

    try:
        memory = MemoryStore(Config.DATABASE_URL)

        # Check if M365 is connected
        creds = memory.get_m365_credentials(user_id)
        if not creds:
            return jsonify({
                "error": "Microsoft 365 not connected",
                "events": []
            }), 401

        # Get calendar events
        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user_id,
            memory_store=memory
        )

        events = provider.list_calendar_events(
            start_time=start_date,
            end_time=end_date
        )

        # Enrich events with weather/traffic
        planning_service = PlanningService(memory)
        enriched_events = planning_service.enrich_calendar_view(events, str(user_id))

        return jsonify({
            "events": enriched_events,
            "start_date": start_date,
            "end_date": end_date
        })

    except Exception as e:
        logging.error(f"[PLANNING API] Error enriching calendar: {e}")
        return jsonify({"error": str(e)}), 500
