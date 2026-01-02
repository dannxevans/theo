"""
Action helper functions.

Provides utility functions for:
- Date and time parsing
- Event formatting
- LLM-based extraction
- Service detection
"""

from typing import Optional, Tuple, Dict
from datetime import datetime, timedelta
import logging
import re


def parse_date_range(text: str) -> Optional[Tuple[datetime, datetime]]:
    """
    Parse natural language date references.

    Supported formats:
    - "tomorrow"
    - "this Tuesday", "next Tuesday"
    - "this week", "next week"
    - "today"
    - "Monday", "Tuesday", etc.

    Args:
        text: User input text

    Returns:
        Tuple of (start_date, end_date) or None if no date found

    Examples:
        >>> start, end = parse_date_range("What's on Tuesday?")
        >>> print(start.strftime("%A"))
        "Tuesday"
    """
    text_l = text.lower()
    now = datetime.now()

    # "today"
    if "today" in text_l:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        return (start, end)

    # "tomorrow"
    if "tomorrow" in text_l:
        tomorrow = now + timedelta(days=1)
        start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        return (start, end)

    # Day of week (Monday, Tuesday, etc.)
    days_of_week = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6
    }

    for day_name, day_num in days_of_week.items():
        if day_name in text_l:
            # Calculate next occurrence of this day
            days_ahead = day_num - now.weekday()
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7

            # Check for "next" modifier
            if "next" in text_l:
                days_ahead += 7

            target_date = now + timedelta(days=days_ahead)
            start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59)
            return (start, end)

    # "this week"
    if "this week" in text_l:
        # Monday to Sunday of current week
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return (start, end)

    # "next week"
    if "next week" in text_l:
        # Monday to Sunday of next week
        start = now - timedelta(days=now.weekday()) + timedelta(weeks=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
        return (start, end)

    # Default: next 7 days
    start = now
    end = now + timedelta(days=7)
    return (start, end)


def format_date_range(start_date: datetime, end_date: datetime) -> str:
    """
    Format date range for human-readable output.

    Args:
        start_date: Start of range
        end_date: End of range

    Returns:
        Formatted string like "on Tuesday, Dec 26" or "from Dec 26-28"

    Examples:
        >>> start = datetime(2025, 12, 26)
        >>> end = datetime(2025, 12, 26, 23, 59, 59)
        >>> print(format_date_range(start, end))
        "on Friday, December 26"
    """
    # Same day
    if start_date.date() == end_date.date():
        return f"on {start_date.strftime('%A, %B %d').replace(' 0', ' ')}"

    # Multiple days in same month
    if start_date.month == end_date.month:
        start_fmt = start_date.strftime('%B %d').replace(' 0', ' ')
        end_day = end_date.strftime('%d').lstrip('0')
        return f"from {start_fmt} to {end_day}"

    # Different months
    start_fmt = start_date.strftime('%B %d').replace(' 0', ' ')
    end_fmt = end_date.strftime('%B %d').replace(' 0', ' ')
    return f"from {start_fmt} to {end_fmt}"


def format_event_list(events: list, show_date: bool = False) -> str:
    """
    Format a list of events for display.

    Args:
        events: List of event dictionaries
        show_date: If True, include day and date for each event (for multi-day ranges)

    Returns:
        Formatted string with event details

    Example:
        >>> events = [
        ...     {"subject": "Meeting", "start_time": "2025-12-26T09:00:00", "location": "Office"}
        ... ]
        >>> print(format_event_list(events))
        "• Meeting\n  9:00 AM • Office"
    """
    formatted = []

    for event in events:
        # Parse start time
        start_time_str = event.get("start_time", "")
        time_str = "Time TBD"
        start_time = None

        logging.info(f"[HELPERS] Formatting event: {event.get('subject')}, start_time='{start_time_str}', type={type(start_time_str)}")

        if start_time_str:
            try:
                # Handle both ISO format with and without timezone
                if isinstance(start_time_str, str):
                    # Microsoft Graph API returns fractional seconds with 7 digits, but Python only supports 6
                    # e.g., "2025-12-27T15:00:00.0000000" -> "2025-12-27T15:00:00.000000"
                    time_str_cleaned = re.sub(r'\.(\d{6})\d+', r'.\1', start_time_str)
                    time_str_cleaned = time_str_cleaned.replace("Z", "+00:00")

                    start_time = datetime.fromisoformat(time_str_cleaned)
                    time_str = start_time.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
                    logging.info(f"[HELPERS] Parsed time successfully: {time_str}")
            except Exception as e:
                logging.warning(f"[HELPERS] Failed to parse start time '{start_time_str}': {e}")

        # Build event line - keep subject and time on same line
        subject = event.get("subject", "Untitled Event")
        location = event.get("location")

        # Format: • Subject at Time • Location
        # If show_date=True (multi-day range), prepend day and date
        if show_date and start_time:
            day_date = start_time.strftime("%A, %B %d")  # e.g., "Monday, December 27"
            event_line = f"**{day_date}**\n• {subject}"
        else:
            event_line = f"• {subject}"

        if time_str != "Time TBD":
            event_line += f" at {time_str}"

        if location:
            event_line += f" • {location}"

        # Add weather information if available
        weather = event.get("weather")
        if weather:
            temp = weather.get("temperature")
            icon = weather.get("icon", "")
            desc = weather.get("description", "")
            if temp is not None:
                event_line += f" {icon} {temp}°C"

        # Add traffic information if available
        traffic = event.get("traffic")
        if traffic:
            duration = traffic.get("duration_in_traffic_minutes", traffic.get("duration_minutes"))
            if duration:
                event_line += f" 🚗 {int(duration)} mins"

        # Add attendees on next line if present
        attendees = event.get("attendees", [])
        if attendees and len(attendees) > 0:
            attendee_count = len(attendees)
            event_line += f"\n  {attendee_count} attendee{'s' if attendee_count > 1 else ''}"

        formatted.append(event_line)

    return "\n\n".join(formatted)


def parse_event_details(text: str) -> Optional[Dict]:
    """
    Parse event details from natural language.

    Extracts:
    - subject: Event title/description
    - start_time: When the event starts
    - end_time: When the event ends (defaults to 1 hour after start)
    - location: Optional location

    Examples:
    - "add lunch with Sean at 1pm today"
      → {"subject": "lunch with Sean", "start_time": today@13:00, "end_time": today@14:00}
    - "schedule meeting tomorrow at 3pm for 2 hours"
      → {"subject": "meeting", "start_time": tomorrow@15:00, "end_time": tomorrow@17:00}

    Args:
        text: User input text

    Returns:
        Dictionary with event details or None if parsing fails
    """
    text_l = text.lower()
    now = datetime.now()

    # Parse time first
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_l)
    if not time_match:
        # Try to find "at" followed by time words
        return None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    meridiem = time_match.group(3)

    # Convert to 24-hour format
    if meridiem == 'pm' and hour != 12:
        hour += 12
    elif meridiem == 'am' and hour == 12:
        hour = 0
    elif not meridiem and hour < 12:
        # Assume PM for times like "1:00" without AM/PM
        hour += 12

    # Validate hour and minute are in valid range
    if not (0 <= hour <= 23):
        logging.warning(f"[HELPERS] Invalid hour value {hour}, cannot parse event")
        return None
    if not (0 <= minute <= 59):
        logging.warning(f"[HELPERS] Invalid minute value {minute}, cannot parse event")
        return None

    # Parse date (today, tomorrow, specific day)
    date_base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if "tomorrow" in text_l:
        date_base = date_base + timedelta(days=1)
    elif "today" not in text_l:
        # Check for day of week
        days_of_week = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        for day_name, day_num in days_of_week.items():
            if day_name in text_l:
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                date_base = date_base + timedelta(days=days_ahead)
                break

    start_time = date_base

    # Parse duration (defaults to 1 hour)
    duration_hours = 1
    duration_match = re.search(r'for (\d+)\s*(hour|hr)', text_l)
    if duration_match:
        duration_hours = int(duration_match.group(1))

    end_time = start_time + timedelta(hours=duration_hours)

    # Parse subject - extract text before time indicators
    # Remove common action words
    subject_text = text
    for pattern in ['add', 'create', 'schedule', 'book', 'set up', 'make an?']:
        subject_text = re.sub(f'\\b{pattern}\\b', '', subject_text, flags=re.IGNORECASE)

    # Remove time references
    subject_text = re.sub(r'\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?', '', subject_text, flags=re.IGNORECASE)
    subject_text = re.sub(r'\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', subject_text, flags=re.IGNORECASE)
    subject_text = re.sub(r'\bto my calendar\b', '', subject_text, flags=re.IGNORECASE)
    subject_text = re.sub(r'\bfor \d+\s*(hour|hr)s?\b', '', subject_text, flags=re.IGNORECASE)

    # Clean up whitespace
    subject = ' '.join(subject_text.split()).strip()

    if not subject:
        subject = "Event"

    return {
        "subject": subject,
        "start_time": start_time,
        "end_time": end_time,
    }


def extract_event_with_llm(user_text: str, user_id: int, memory_store) -> Optional[Dict]:
    """
    Use LLM to extract structured event details from natural language.

    Args:
        user_text: User's natural language request
        user_id: User ID for context
        memory_store: MemoryStore instance for provider access

    Returns:
        Dictionary with parsed event details or None if extraction fails
    """
    from providers.openai import OpenAIProvider
    from core.provider_registry import ProviderRegistry
    import json

    # Get system provider for lightweight tasks (configurable)
    try:
        registry = ProviderRegistry(memory_store)

        # First check for "system" routing preference
        system_provider_id = memory_store.get_routing_provider(user_id, "system") if memory_store else None
        provider_cfg = None

        if system_provider_id:
            # Use configured system provider
            provider_cfg = registry.get(system_provider_id)
            logging.info(f"[HELPERS] Using configured system provider: {system_provider_id}")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Fallback to OpenAI provider
            provider_cfg = registry.get_by_type("openai")
            logging.info("[HELPERS] Using fallback OpenAI provider for calendar extraction")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Fallback to basic parsing if no LLM available
            logging.warning("[HELPERS] No LLM provider available, using basic parsing")
            return parse_event_details(user_text)

        # Instantiate appropriate provider based on type
        provider_type = provider_cfg.get("type", "openai")
        if provider_type == "openai":
            provider = OpenAIProvider(
                api_key=provider_cfg["api_key"],
                base_url=provider_cfg.get("base_url"),
                model=provider_cfg.get("model") or "gpt-4o-mini"
            )
        else:
            # For now, only OpenAI is supported for lightweight tasks
            logging.warning(f"[HELPERS] Provider type {provider_type} not supported for calendar extraction, using basic parsing")
            return parse_event_details(user_text)

        # Construct extraction prompt
        system_prompt = """You are a calendar event parser. Extract structured event information from user requests.

Return ONLY a JSON object with these fields:
- subject: Short, clear event title (e.g., "Lunch with Sean", "Team Meeting")
- start_time: ISO datetime string (e.g., "2025-12-27T13:00:00")
- end_time: ISO datetime string (1 hour after start if not specified)
- location: Optional location string
- description: Optional additional details

Rules:
1. Make the subject concise and professional
2. Use the current date/time as reference for relative times
3. Default duration is 1 hour unless specified
4. Return ONLY valid JSON, no other text"""

        current_time = datetime.now().isoformat()
        user_prompt = f"Current time: {current_time}\n\nUser request: {user_text}\n\nExtract event details as JSON:"

        response = provider.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Parse LLM response (OpenAI provider returns string directly)
        response_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

        # Try to extract JSON from response (LLM might add markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        event_data = json.loads(response_text)

        # Convert ISO strings to datetime objects
        if "start_time" in event_data:
            event_data["start_time"] = datetime.fromisoformat(event_data["start_time"])
        if "end_time" in event_data:
            event_data["end_time"] = datetime.fromisoformat(event_data["end_time"])

        logging.info(f"[HELPERS] LLM extracted event: {event_data.get('subject')}")
        return event_data

    except Exception as e:
        logging.error(f"[HELPERS] LLM extraction failed: {e}")
        # Fallback to basic parsing
        return parse_event_details(user_text)


def detect_service_category(user_text: str) -> str:
    """
    Detect if user is requesting a service booking (haircut, doctor, etc.).

    Args:
        user_text: User's input text

    Returns:
        Service category (haircut, doctor, dentist) or empty string if none detected
    """
    text_lower = user_text.lower()

    # Service keywords mapping
    service_patterns = {
        "haircut": ["haircut", "hair cut", "barber", "salon", "trim", "hairstyle"],
        "doctor": ["doctor", "physician", "gp", "medical appointment", "checkup"],
        "dentist": ["dentist", "dental", "teeth cleaning", "tooth"],
        "massage": ["massage", "spa", "therapist"],
        "gym": ["gym", "personal trainer", "fitness", "workout session"]
    }

    for category, keywords in service_patterns.items():
        if any(keyword in text_lower for keyword in keywords):
            return category

    return ""


def find_optimal_slots(
    calendar_events: list,
    start_date: datetime,
    end_date: datetime,
    duration_minutes: int = 60,
    preferred_hours: tuple = (9, 18)  # 9am to 6pm
) -> list:
    """
    Find optimal free time slots in the user's calendar.

    Args:
        calendar_events: List of existing calendar events
        start_date: Start of search range
        end_date: End of search range
        duration_minutes: Required duration for slot
        preferred_hours: Tuple of (start_hour, end_hour) for preferred times

    Returns:
        List of datetime objects representing optimal start times
    """
    from datetime import timedelta

    free_slots = []
    current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

    while current_date <= end_date:
        # Skip past dates
        if current_date.date() < datetime.now().date():
            current_date += timedelta(days=1)
            continue

        # Only check weekdays (Monday=0, Sunday=6)
        if current_date.weekday() >= 5:  # Saturday or Sunday
            current_date += timedelta(days=1)
            continue

        # Check each hour in preferred range
        for hour in range(preferred_hours[0], preferred_hours[1]):
            slot_start = current_date.replace(hour=hour, minute=0)
            slot_end = slot_start + timedelta(minutes=duration_minutes)

            # Check if slot conflicts with any event
            is_free = True
            for event in calendar_events:
                event_start = event.get("start_time")
                event_end = event.get("end_time")

                if isinstance(event_start, str):
                    # Normalize M365 datetime format (handle 7-digit microseconds)
                    event_start = parse_m365_datetime(event_start)
                if isinstance(event_end, str):
                    event_end = parse_m365_datetime(event_end)

                # Check for overlap
                if (slot_start < event_end and slot_end > event_start):
                    is_free = False
                    break

            if is_free and slot_start > datetime.now():
                free_slots.append(slot_start)

        current_date += timedelta(days=1)

    # Sort by closeness to preferred times (favor early afternoon)
    def time_score(dt):
        # Prefer 1pm-3pm (13-15)
        hour = dt.hour
        if 13 <= hour < 15:
            return 0  # Best
        elif 15 <= hour < 17:
            return 1  # Good
        elif 11 <= hour < 13:
            return 2  # Morning
        else:
            return 3  # Other

    free_slots.sort(key=time_score)
    return free_slots


def format_free_slots(slots: list) -> str:
    """
    Format free time slots for display.

    Args:
        slots: List of datetime objects

    Returns:
        Formatted string with suggested times
    """
    if not slots:
        return "No free slots found."

    formatted = []
    for i, slot in enumerate(slots, 1):
        day = slot.strftime("%A, %B %d")
        time = slot.strftime("%I:%M %p").lstrip("0")
        formatted.append(f"{i}. {day} at {time}")

    return "\n".join(formatted)


def parse_m365_datetime(dt_string: str) -> datetime:
    """
    Parse M365 datetime strings which may have 7-digit microseconds.

    M365 Graph API returns formats like:
    - 2025-12-28T15:00:00.0000000
    - 2025-12-28T15:00:00Z

    Args:
        dt_string: ISO format datetime string

    Returns:
        datetime object
    """
    import re

    # Remove 'Z' timezone indicator
    dt_string = dt_string.replace('Z', '+00:00')

    # Regex to find and truncate microseconds to 6 digits (Python's limit)
    # Match: .0000000 (7 digits) and replace with .000000 (6 digits)
    dt_string = re.sub(r'\.(\d{6})\d+', r'.\1', dt_string)

    try:
        return datetime.fromisoformat(dt_string)
    except ValueError as e:
        # If still fails, log and try without microseconds
        logging.warning(f"[HELPERS] Failed to parse datetime '{dt_string}': {e}")
        # Remove microseconds entirely
        dt_string = re.sub(r'\.\d+', '', dt_string)
        return datetime.fromisoformat(dt_string)
