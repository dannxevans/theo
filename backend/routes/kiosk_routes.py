"""
Kiosk Mode Routes
Handles kiosk mode access validation and dashboard data.
"""
from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging
import concurrent.futures
from typing import Optional, Dict, Any

kiosk_bp = Blueprint('kiosk', __name__)
logger = logging.getLogger(__name__)


@kiosk_bp.route('/api/kiosk/check-access', methods=['GET'])
def check_kiosk_access():
    """
    Check if user can access kiosk mode.
    Only accessible from Personal mode.

    Returns:
        200: Access allowed
        403: Access denied (not in Personal mode)
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check current mode
    mode_config = memory.get_user_mode(user["id"])
    current_mode = mode_config.get("active_mode", "personal")

    if current_mode != "personal":
        return jsonify({
            "allowed": False,
            "reason": "Kiosk mode is only accessible from Personal mode. Please switch to Personal mode first."
        }), 403

    return jsonify({"allowed": True}), 200


def _get_authenticated_user(memory):
    """
    Helper to get authenticated user from request.

    Returns:
        tuple: (user_dict, error_response) or (user_dict, None)
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Unauthorized"}), 401)

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return None, (jsonify({"error": "Invalid session"}), 401)

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return None, (jsonify({"error": "User not found"}), 401)

    return user, None


def _is_personal_mode(memory, user_id):
    """
    Check if user is in Personal Mode.

    Returns:
        bool: True if in Personal Mode
    """
    mode_config = memory.get_user_mode(user_id)
    if isinstance(mode_config, dict):
        return mode_config.get("active_mode") == "personal"
    return mode_config == "personal"


def _fetch_sleep_data(user_id, memory) -> Optional[Dict[str, Any]]:
    """Fetch latest WHOOP sleep data."""
    try:
        from services.whoop_client import WHOOPClient

        # Get WHOOP credentials
        creds = memory.get_whoop_credentials(user_id)
        if not creds or not creds.get("is_valid"):
            logger.debug(f"[KIOSK] WHOOP credentials not valid for user {user_id}")
            return None

        # Create client and fetch latest sleep
        client = WHOOPClient(creds["access_token"])
        sleep_data = client.get_latest_sleep()

        if not sleep_data:
            return None

        # Extract relevant fields (same logic as whoop_handlers.py)
        score = sleep_data.get("score", {})

        # Duration can be in score or at top level - use total_in_bed_time_milli
        duration_ms = score.get('total_in_bed_time_milli') or sleep_data.get('total_in_bed_time_milli', 0)
        if not duration_ms:
            # Try calculating from start/end times
            start = sleep_data.get('start')
            end = sleep_data.get('end')
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                except:
                    duration_ms = 0

        duration_hours = duration_ms / 1000 / 60 / 60 if duration_ms else 0

        return {
            "hours": round(duration_hours, 1),
            "quality": score.get("sleep_performance_percentage", 0),
            "date": sleep_data.get("end", "")[:10],  # YYYY-MM-DD
            "efficiency": score.get("sleep_efficiency_percentage", 0)
        }
    except Exception as e:
        logger.warning(f"[KIOSK] Failed to fetch sleep data: {e}")
        return None


def _fetch_workout_data(user_id, memory) -> Optional[Dict[str, Any]]:
    """Fetch latest WHOOP workout data."""
    try:
        from services.whoop_client import WHOOPClient

        # Get WHOOP credentials
        creds = memory.get_whoop_credentials(user_id)
        if not creds or not creds.get("is_valid"):
            logger.debug(f"[KIOSK] WHOOP credentials not valid for user {user_id}")
            return None

        # Create client and fetch latest workout
        client = WHOOPClient(creds["access_token"])
        workout_data = client.get_latest_workout()

        if not workout_data:
            return None

        # Calculate time ago
        end_time = datetime.fromisoformat(workout_data.get("end", "").replace("Z", "+00:00"))
        time_diff = datetime.now(end_time.tzinfo) - end_time
        hours_ago = int(time_diff.total_seconds() / 3600)

        if hours_ago < 1:
            time_ago = f"{int(time_diff.total_seconds() / 60)} minutes ago"
        elif hours_ago < 24:
            time_ago = f"{hours_ago} hours ago"
        else:
            days_ago = hours_ago // 24
            time_ago = f"{days_ago} day{'s' if days_ago > 1 else ''} ago"

        # Extract relevant fields (same logic as whoop_handlers.py)
        score = workout_data.get("score", {})

        # Duration can be in score or at top level
        duration_ms = score.get('duration_milli') or workout_data.get('duration_milli', 0)

        return {
            "type": workout_data.get("sport_name", "Workout"),
            "duration_minutes": round(duration_ms / (1000 * 60)) if duration_ms else 0,
            "strain": score.get("strain", 0),
            "time_ago": time_ago
        }
    except Exception as e:
        logger.warning(f"[KIOSK] Failed to fetch workout data: {e}")
        return None


def _fetch_weather_data(user_id, memory) -> Optional[Dict[str, Any]]:
    """Fetch weather data for home location."""
    try:
        from core.weather_service import WeatherService
        from core.user_utils import DEFAULT_USER_ID

        # Get weather API key (same way as planning_service)
        prefs = memory.get_all(str(user_id))
        weather_api_key = prefs.get("feature_provider_openweather_api_key")

        if not weather_api_key:
            logger.info(f"[KIOSK] OpenWeather API key not configured for user {user_id}")
            return None

        # Get home location from memory facts (same approach as planning_service)
        home_location = None
        try:
            memories = memory.get_memories(DEFAULT_USER_ID, memory_type='fact')
            for mem in memories:
                if mem.get('key', '').lower() == 'home location':
                    home_location = mem.get('value')
                    logger.info(f"[KIOSK] Found home location in facts: {home_location}")
                    break
        except Exception as e:
            logger.warning(f"[KIOSK] Failed to get home location from facts: {e}")

        if not home_location:
            logger.info(f"[KIOSK] No home location found in memory facts for user {user_id}")
            return None

        # Extract city from full address (e.g., "8 Harefields Way, Wirral. CH494SB" -> "Wirral,GB")
        # Split by comma/period and find the city name (usually second part)
        city_name = home_location
        if ',' in home_location or '.' in home_location:
            parts = home_location.replace('.', ',').split(',')
            # Get second part (city) and clean it
            if len(parts) >= 2:
                city_name = parts[1].strip()
                # Add GB for OpenWeather API (UK doesn't work, needs GB)
                if city_name and 'GB' not in city_name.upper() and 'UK' not in city_name.upper():
                    city_name = f"{city_name},GB"

        logger.info(f"[KIOSK] Extracted city '{city_name}' from location '{home_location}'")

        # Fetch weather
        service = WeatherService(weather_api_key)
        weather_data = service.get_weather(city_name, units="metric")

        if not weather_data:
            logger.debug(f"[KIOSK] Weather service returned no data for location: {home_location}")
            return None

        return {
            "location": weather_data["location"].split(",")[0],  # Just city name
            "temperature": round(weather_data["temperature"]),
            "condition": weather_data["description"].title(),
            "icon": weather_data["description"].lower().replace(" ", "-"),
            "units": "metric"
        }
    except Exception as e:
        logger.warning(f"[KIOSK] Failed to fetch weather data: {e}")
        return None


def _fetch_calendar_data(user_id, memory) -> Optional[Dict[str, Any]]:
    """Fetch upcoming M365 calendar events."""
    try:
        import requests

        # Get M365 credentials
        creds = memory.get_m365_credentials(user_id)
        if not creds or not creds.get("is_valid"):
            logger.debug(f"[KIOSK] M365 credentials not valid for user {user_id}")
            return None

        # Ensure token is valid (refresh if needed)
        from actions.m365_provider import M365Provider
        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user_id,
            memory_store=memory
        )
        provider._ensure_token_valid()

        # Fetch calendar events for next 48 hours
        now = datetime.utcnow()
        end_time = now + timedelta(hours=48)

        url = f"https://graph.microsoft.com/v1.0/me/calendar/calendarView"
        params = {
            "startDateTime": now.isoformat() + "Z",
            "endDateTime": end_time.isoformat() + "Z",
            "$orderby": "start/dateTime",
            "$top": 10
        }
        headers = {"Authorization": f"Bearer {provider.access_token}"}

        logger.info(f"[KIOSK] Fetching calendar events from {now.isoformat()}Z to {end_time.isoformat()}Z")
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        events = response.json().get("value", [])
        logger.info(f"[KIOSK] Calendar returned {len(events)} events")

        if not events:
            return {
                "count": 0,
                "next_event": None,
                "upcoming": []
            }

        # Get next event
        next_event = events[0]

        # Handle Microsoft's 7-decimal fractional seconds (Python expects max 6)
        datetime_str = next_event["start"]["dateTime"]
        if '.' in datetime_str:
            parts = datetime_str.split('.')
            if len(parts[1]) > 6:
                # Truncate to 6 decimal places
                datetime_str = f"{parts[0]}.{parts[1][:6]}"

        start_dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        time_diff = start_dt.replace(tzinfo=None) - datetime.utcnow()

        minutes = int(time_diff.total_seconds() / 60)
        if minutes < 60:
            relative = f"in {minutes} minutes"
        elif minutes < 1440:
            hours = minutes // 60
            relative = f"in {hours} hour{'s' if hours > 1 else ''}"
        else:
            days = minutes // 1440
            relative = f"in {days} day{'s' if days > 1 else ''}"

        return {
            "count": len(events),
            "next_event": {
                "title": next_event.get("subject", "Untitled"),
                "start": next_event["start"]["dateTime"],
                "relative": relative
            },
            "upcoming": [
                {
                    "title": evt.get("subject", "Untitled"),
                    "start": evt["start"]["dateTime"]
                }
                for evt in events[:5]
            ]
        }
    except Exception as e:
        logger.warning(f"[KIOSK] Failed to fetch calendar data: {e}")
        return None


def _fetch_email_count(user_id, memory) -> Optional[Dict[str, Any]]:
    """Fetch unread email count from M365."""
    try:
        import requests

        # Get M365 credentials
        creds = memory.get_m365_credentials(user_id)
        if not creds or not creds.get("is_valid"):
            return None

        # Ensure token is valid
        from actions.m365_provider import M365Provider
        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user_id,
            memory_store=memory
        )
        provider._ensure_token_valid()

        # Fetch unread count
        url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox"
        headers = {"Authorization": f"Bearer {provider.access_token}"}

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        return {
            "unread_count": data.get("unreadItemCount", 0)
        }
    except Exception as e:
        logger.warning(f"[KIOSK] Failed to fetch email count: {e}")
        return None


@kiosk_bp.route('/api/kiosk/dashboard-data', methods=['GET'])
def get_dashboard_data():
    """
    Get aggregated dashboard data for kiosk mode.
    Fetches data from multiple services in parallel.

    Returns:
        200: Dashboard data with all widget information
        401: Unauthorized
        403: Not in Personal mode
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user
    user, error = _get_authenticated_user(memory)
    if error:
        return error

    # Check Personal Mode
    if not _is_personal_mode(memory, user["id"]):
        return jsonify({
            "error": "Kiosk mode is only available in Personal Mode"
        }), 403

    # Fetch all data in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            "sleep": executor.submit(_fetch_sleep_data, user["id"], memory),
            "workout": executor.submit(_fetch_workout_data, user["id"], memory),
            "weather": executor.submit(_fetch_weather_data, user["id"], memory),
            "calendar": executor.submit(_fetch_calendar_data, user["id"], memory),
            "email": executor.submit(_fetch_email_count, user["id"], memory)
        }

        # Wait for all futures with timeout
        results = {}
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=8)  # 8 second timeout per service
            except concurrent.futures.TimeoutError:
                logger.warning(f"[KIOSK] Timeout fetching {key} data")
                results[key] = None
            except Exception as e:
                logger.error(f"[KIOSK] Error fetching {key} data: {e}")
                results[key] = None

    # Build response with current time
    now = datetime.now()

    dashboard_data = {
        "time": {
            "current": now.isoformat(),
            "formatted": now.strftime("%I:%M %p").lstrip("0"),
            "date": now.strftime("%A, %d %B %Y")
        },
        "sleep": results.get("sleep"),
        "workout": results.get("workout"),
        "weather": results.get("weather"),
        "calendar": results.get("calendar"),
        "email": results.get("email")
    }

    logger.info(f"[KIOSK] Dashboard data fetched for user {user['id']}")
    return jsonify(dashboard_data), 200
