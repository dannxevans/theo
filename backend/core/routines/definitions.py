"""
Routine definitions for THEO.

Defines system routines that bundle multiple actions together.
"""

# System-defined routines
ROUTINES = {
    "good_morning": {
        "name": "Good Morning",
        "description": "Morning briefing with calendar, important emails, and email summary",
        "triggers": [
            "good morning",
            "good morning theo",
            "morning briefing",
            "morning update",
        ],
        "actions": [
            {
                "type": "calendar_read",
                "description": "Read today's calendar events",
                "params": {
                    "timeframe": "today"
                }
            },
            {
                "type": "email_check",
                "description": "Check for important emails",
                "params": {
                    "filter": "important",
                    "unread_only": True
                }
            },
            {
                "type": "email_summary",
                "description": "Summarize unread non-important emails",
                "params": {
                    "filter": "unread",
                    "exclude_important": True
                }
            }
        ],
        "consolidation_prompt": """You are summarizing a morning briefing for the user.

Given the following information:
- Today's calendar events
- Important emails received
- Summary of other unread emails

Create a friendly, concise morning briefing that:
1. Greets the user
2. Highlights key calendar events for today
3. Mentions important emails that need attention
4. Briefly summarizes other unread emails
5. Uses a calm, informative tone

Be natural and conversational. Don't use overly formal language.
"""
    }
}


def get_routine_by_name(routine_name):
    """
    Get a routine definition by name.

    Args:
        routine_name: Name of the routine (e.g., "good_morning")

    Returns:
        Routine definition dict or None if not found
    """
    return ROUTINES.get(routine_name)


def get_all_routines():
    """
    Get all defined routines.

    Returns:
        Dictionary of all routines
    """
    return ROUTINES.copy()


def get_routine_names():
    """
    Get list of all routine names.

    Returns:
        List of routine names
    """
    return list(ROUTINES.keys())
