"""
Routine definitions for THEO.

Provides default routine templates.
All routines are now user-editable.
"""

# Default routine template for "Good Morning"
# This is just a template - actual routines are stored in the database
DEFAULT_GOOD_MORNING_ROUTINE = {
    "name": "Good Morning",
    "description": "Morning briefing with calendar, important emails, and email summary",
    "triggers": [
        "good morning",
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
