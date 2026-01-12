"""
Service capability registry for orchestration.

Defines what services THEO can access and their available methods.
This registry is used to inform the LLM what operations are possible.
"""

SERVICE_REGISTRY = {
    "calendar": {
        "description": "User's calendar - scheduled appointments, meetings, and time-blocked events (Microsoft 365). Use this to check availability, find meetings, or see what's scheduled.",
        "methods": {
            "get_upcoming_events": {
                "params": {"days_ahead": "int (default: 7)"},
                "returns": "List of events with title, start, end, location",
                "example": "get_upcoming_events(days_ahead=3)"
            },
            "check_availability": {
                "params": {"date": "string (YYYY-MM-DD)"},
                "returns": "Calendar events for that date - shows meetings, appointments, and scheduled time blocks",
                "example": "check_availability(date='2026-01-15')"
            }
        },
        "read_only": True
    },
    "weather": {
        "description": "Weather forecasts and current conditions",
        "methods": {
            "get_forecast": {
                "params": {"location": "string (city name, or 'home'/'work')"},
                "returns": "Temperature, conditions, humidity, wind",
                "example": "get_forecast(location='Manchester')"
            }
        },
        "read_only": True
    },
    "traffic": {
        "description": "Traffic estimates and routing information (HERE Maps)",
        "methods": {
            "get_route": {
                "params": {
                    "origin": "string (address or 'home'/'work')",
                    "destination": "string (address)"
                },
                "returns": "Distance, duration, traffic delays",
                "example": "get_route(origin='home', destination='Manchester Airport')"
            }
        },
        "read_only": True
    },
    "email": {
        "description": "Email inbox and messages (Microsoft 365)",
        "methods": {
            "get_recent": {
                "params": {"count": "int (default: 10)"},
                "returns": "Recent emails with sender, subject, date",
                "example": "get_recent(count=5)"
            },
            "search": {
                "params": {"query": "string (search terms)"},
                "returns": "Emails matching search query",
                "example": "search(query='meeting')"
            }
        },
        "read_only": True
    },
    "tasks": {
        "description": "User's to-do list and action items (Microsoft 365). Use this for things the user needs to do, NOT for checking scheduled time or availability. For scheduled events and availability, use calendar instead.",
        "methods": {
            "get_pending": {
                "params": {},
                "returns": "List of incomplete tasks",
                "example": "get_pending()"
            },
            "get_by_date": {
                "params": {"date": "string (YYYY-MM-DD)"},
                "returns": "Tasks due on specific date",
                "example": "get_by_date(date='2026-01-15')"
            }
        },
        "read_only": True
    },
    "web_fetch": {
        "description": "Fetch and read content from web URLs",
        "methods": {
            "fetch_url": {
                "params": {"url": "string (full URL)"},
                "returns": "Text content from webpage",
                "example": "fetch_url(url='https://example.com')"
            }
        },
        "read_only": True
    },
    "memory": {
        "description": "User's stored facts, preferences, and personal information",
        "methods": {
            "search": {
                "params": {"query": "string (search terms)"},
                "returns": "Relevant memories matching query",
                "example": "search(query='favorite restaurant')"
            }
        },
        "read_only": True
    },
    "whoop": {
        "description": "WHOOP fitness tracker data (sleep, recovery, workouts)",
        "methods": {
            "get_sleep": {
                "params": {"days": "int (default: 1)"},
                "returns": "Sleep data with duration, quality, stages",
                "example": "get_sleep(days=1)"
            },
            "get_recovery": {
                "params": {},
                "returns": "Latest recovery score and metrics",
                "example": "get_recovery()"
            },
            "get_workouts": {
                "params": {"days": "int (default: 7)"},
                "returns": "Recent workout data",
                "example": "get_workouts(days=3)"
            }
        },
        "read_only": True
    },
    "plex": {
        "description": "Plex media server library and playback",
        "methods": {
            "search_library": {
                "params": {"query": "string (movie/show name)"},
                "returns": "Media items matching search",
                "example": "search_library(query='Breaking Bad')"
            },
            "get_history": {
                "params": {"count": "int (default: 10)"},
                "returns": "Recently watched media",
                "example": "get_history(count=5)"
            }
        },
        "read_only": True
    }
}


def get_service_capabilities_prompt() -> str:
    """
    Generate LLM-friendly description of available services.

    Used in service planning prompts to inform the LLM what
    operations are possible.

    Returns:
        str: Formatted service capabilities for LLM prompt
    """
    lines = []

    for service_name, service_info in SERVICE_REGISTRY.items():
        # Service header
        lines.append(f"\n{service_name}:")
        lines.append(f"  Description: {service_info['description']}")
        lines.append(f"  Methods:")

        # Methods
        for method_name, method_info in service_info["methods"].items():
            # Format parameters
            params_list = []
            for param_name, param_desc in method_info["params"].items():
                params_list.append(f"{param_name}: {param_desc}")

            params_str = ", ".join(params_list) if params_list else "none"

            lines.append(f"    - {method_name}({params_str})")
            lines.append(f"      Returns: {method_info['returns']}")
            lines.append(f"      Example: {method_info['example']}")

    return "\n".join(lines)


def validate_service_request(service: str, method: str, params: dict) -> tuple:
    """
    Validate a service request from the LLM.

    Args:
        service: Service name (e.g., "calendar")
        method: Method name (e.g., "get_upcoming_events")
        params: Method parameters as dict

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Check service exists
    if service not in SERVICE_REGISTRY:
        return False, f"Unknown service: {service}"

    service_info = SERVICE_REGISTRY[service]

    # Check method exists
    if method not in service_info["methods"]:
        available = ", ".join(service_info["methods"].keys())
        return False, f"Unknown method '{method}' for service '{service}'. Available: {available}"

    # Params validation could be added here if needed
    # For now, we trust the LLM and let the actual service handle validation

    return True, None
