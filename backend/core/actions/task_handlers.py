"""
Task action handlers.

Provides handlers for M365 Tasks (Microsoft To Do) related actions:
- Reading tasks (all, today, this week)
- Creating new tasks
- Updating tasks
- Completing tasks
- Deleting tasks
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import re

from .base_handler import BaseActionHandler


def parse_m365_task_datetime(date_str: str) -> datetime:
    """
    Parse Microsoft To Do datetime strings which can have 7 decimal places.

    Microsoft returns datetimes like: 2026-01-07T00:00:00.0000000
    Python's fromisoformat() only supports up to 6 decimal places (microseconds).

    Args:
        date_str: ISO format datetime string from Microsoft To Do API

    Returns:
        datetime object

    Raises:
        ValueError: If the string cannot be parsed
    """
    if not date_str:
        return None

    # Remove 'Z' timezone indicator if present
    date_str = date_str.replace("Z", "+00:00")

    # Fix the fractional seconds if they have more than 6 digits
    # Match pattern: .0000000 (7 digits) and reduce to .000000 (6 digits)
    if "." in date_str and "+" in date_str:
        parts = date_str.split(".")
        if len(parts) == 2:
            fractional_and_tz = parts[1]
            if "+" in fractional_and_tz:
                fractional, tz = fractional_and_tz.split("+")
                if len(fractional) > 6:
                    # Truncate to 6 digits (microseconds)
                    fractional = fractional[:6]
                date_str = f"{parts[0]}.{fractional}+{tz}"
    elif "." in date_str:
        # No timezone, just fractional seconds
        parts = date_str.split(".")
        if len(parts) == 2:
            fractional = parts[1]
            if len(fractional) > 6:
                fractional = fractional[:6]
            date_str = f"{parts[0]}.{fractional}"

    return datetime.fromisoformat(date_str)


class TaskHandlers(BaseActionHandler):
    """Handlers for M365 Tasks (To Do) operations."""

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """Initialize task handlers."""
        super().__init__(action_registry, memory_store, confirmation_manager)
        self.logger = logging.getLogger(__name__)

    def handle_read_tasks(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle generic task reading requests.

        Examples:
        - "Show my tasks"
        - "What tasks do I have?"
        - "List my tasks"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with tasks
        """
        self.logger.info(f"[TaskHandlers] Reading all tasks for user {user_id}")

        # Get M365 provider
        provider_result = self._get_provider("read_tasks", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "read_tasks",
                "read_tasks",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        try:
            # Read all tasks
            tasks = provider.read_tasks()

            if not tasks:
                return self._format_success_response(
                    "You don't have any tasks in your list.",
                    "read_tasks",
                    {
                        "task_count": 0,
                        "source": "M365",
                        "action": "read_tasks"
                    }
                )

            # Generate AI summary of tasks
            summary_text = self._generate_task_summary(tasks, user_id, "")

            return self._format_success_response(
                summary_text,
                "read_tasks",
                {
                    "task_count": len(tasks),
                    "source": "M365",
                    "action": "read_tasks",
                    "tasks": tasks
                }
            )

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error reading tasks: {e}")
            return self._format_error_response(
                "I had trouble reading your tasks. Please try again.",
                "read_tasks",
                str(e)
            )

    def handle_read_tasks_today(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle today's tasks reading requests.

        Examples:
        - "Today's tasks"
        - "What tasks do I have today?"
        - "Show my tasks for today"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with today's tasks
        """
        self.logger.info(f"[TaskHandlers] Reading today's tasks for user {user_id}")

        # Get M365 provider
        provider_result = self._get_provider("read_tasks", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "read_tasks",
                "read_tasks_today",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        try:
            # Read all tasks and filter for today's due date
            all_tasks = provider.read_tasks()
            today = datetime.now().date()

            today_tasks = []
            for task in all_tasks:
                if task.get("due_date"):
                    try:
                        # Parse due date (ISO format from Graph API)
                        due_date_str = task["due_date"]
                        due_date = parse_m365_task_datetime(due_date_str)

                        if due_date.date() == today:
                            today_tasks.append(task)
                    except (ValueError, AttributeError) as e:
                        self.logger.warning(f"[TaskHandlers] Failed to parse due date: {e}")
                        continue

            if not today_tasks:
                return self._format_success_response(
                    "You don't have any tasks due today.",
                    "read_tasks_today",
                    {
                        "task_count": 0,
                        "source": "M365",
                        "action": "read_tasks_today"
                    }
                )

            # Generate LLM summary of tasks
            summary = self._generate_task_summary(today_tasks, user_id, "today")

            return self._format_success_response(
                summary,
                "read_tasks_today",
                {
                    "task_count": len(today_tasks),
                    "source": "M365",
                    "action": "read_tasks_today",
                    "tasks": today_tasks
                }
            )

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error reading today's tasks: {e}")
            return self._format_error_response(
                "I had trouble reading your tasks. Please try again.",
                "read_tasks_today",
                str(e)
            )

    def handle_read_tasks_week(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle this week's tasks reading requests.

        Examples:
        - "This week's tasks"
        - "What tasks do I have this week?"
        - "Show my tasks for this week"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with this week's tasks
        """
        self.logger.info(f"[TaskHandlers] Reading this week's tasks for user {user_id}")

        # Get M365 provider
        provider_result = self._get_provider("read_tasks", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "read_tasks",
                "read_tasks_week",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        try:
            # Read all tasks and filter for this week
            all_tasks = provider.read_tasks()
            today = datetime.now().date()

            # Calculate end of week (Sunday)
            days_until_sunday = 6 - today.weekday()
            week_end = today + timedelta(days=days_until_sunday)

            week_tasks = []
            for task in all_tasks:
                if task.get("due_date"):
                    try:
                        due_date_str = task["due_date"]
                        due_date = parse_m365_task_datetime(due_date_str)

                        task_date = due_date.date()
                        if today <= task_date <= week_end:
                            week_tasks.append(task)
                    except (ValueError, AttributeError) as e:
                        self.logger.warning(f"[TaskHandlers] Failed to parse due date: {e}")
                        continue

            if not week_tasks:
                return self._format_success_response(
                    "You don't have any tasks due this week.",
                    "read_tasks_week",
                    {
                        "task_count": 0,
                        "source": "M365",
                        "action": "read_tasks_week"
                    }
                )

            # Generate LLM summary of tasks
            summary = self._generate_task_summary(week_tasks, user_id, "this week")

            return self._format_success_response(
                summary,
                "read_tasks_week",
                {
                    "task_count": len(week_tasks),
                    "source": "M365",
                    "action": "read_tasks_week",
                    "tasks": week_tasks
                }
            )

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error reading week's tasks: {e}")
            return self._format_error_response(
                "I had trouble reading your tasks. Please try again.",
                "read_tasks_week",
                str(e)
            )

    def handle_create_task(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle task creation requests.

        Uses confirmation flow - extracts task details and asks for confirmation
        before actually creating the task.

        Examples:
        - "Add a task to review the report"
        - "Create task: call client tomorrow"
        - "New task buy groceries"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with confirmation request
        """
        self.logger.info(f"[TaskHandlers] Creating task for user {user_id}")

        # Check if we have confirmation manager
        if not self.confirmation_manager:
            return self._format_error_response(
                "Task creation is not available right now.",
                "create_task",
                "No confirmation manager"
            )

        # Extract task details from user text
        task_details = self._extract_task_details(user_text)

        if not task_details.get("title"):
            return self._format_error_response(
                "I couldn't determine what task you want to create. Please provide a task title.",
                "create_task",
                "missing_title"
            )

        # Get M365 provider for provider_id
        provider_result = self._get_provider("create_task", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "create_task",
                "create_task",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        # Build action parameters
        action_params = {
            "title": task_details["title"]
        }

        if task_details.get("description"):
            action_params["description"] = task_details["description"]

        if task_details.get("due_date"):
            # Serialize datetime to ISO string for storage
            due_date = task_details["due_date"]
            if isinstance(due_date, datetime):
                action_params["due_date"] = due_date.isoformat()
            else:
                action_params["due_date"] = due_date

        if task_details.get("importance"):
            action_params["importance"] = task_details["importance"]

        # Generate confirmation message
        confirmation_msg = self._format_task_confirmation(task_details)

        # Create confirmation request
        try:
            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="create_task",
                action_params=action_params,
                confirmation_message=confirmation_msg,
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string for JSON serialization
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_msg}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "model": None,
                "task_type": "create_task",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_msg,
                    "expires_at": expires_at,
                    "action_type": "create_task",
                    "action_category": "task"
                }
            }

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Failed to create confirmation: {e}")
            return self._format_error_response(
                "I had trouble setting up the confirmation. Please try again.",
                "create_task",
                str(e)
            )

    def execute_create_task(self, params: Dict, user_id: int) -> Dict:
        """
        Execute confirmed task creation.

        This is called by the confirmation manager after user confirms.

        Args:
            params: Task parameters (title, description, due_date, importance)
            user_id: User ID

        Returns:
            Response dictionary with created task
        """
        self.logger.info(f"[TaskHandlers] Executing task creation for user {user_id}")

        # Get M365 provider
        provider_result = self._get_provider("create_task", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "create_task",
                "create_task",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        try:
            # Create the task
            created_task = provider.create_task(
                title=params["title"],
                description=params.get("description"),
                due_date=params.get("due_date"),
                importance=params.get("importance", "normal")
            )

            return self._format_success_response(
                f"Task created: {created_task['title']}",
                "create_task",
                {
                    "action": "create_task",
                    "source": "M365",
                    "task_id": created_task["id"],
                    "task": created_task
                }
            )

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error creating task: {e}")
            return self._format_error_response(
                "I had trouble creating your task. Please try again.",
                "create_task",
                str(e)
            )

    def handle_complete_task(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle task completion requests.

        Examples:
        - "Mark 'Review report' as complete"
        - "Complete the task about calling client"
        - "Finish review report task"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with completion result
        """
        self.logger.info(f"[TaskHandlers] Completing task for user {user_id}")

        # Get M365 provider
        provider_result = self._get_provider("complete_task", user_id)
        if not provider_result:
            return self._format_no_provider_response(
                "complete_task",
                "complete_task",
                "Microsoft 365 Tasks"
            )

        provider_id, provider = provider_result

        # Extract task identifier from user text
        task_id = self._extract_task_id(user_text, user_id, provider)

        if not task_id:
            return self._format_error_response(
                "I couldn't determine which task to mark as complete. Please be more specific.",
                "complete_task",
                "missing_task_id"
            )

        try:
            # Complete the task
            updated_task = provider.complete_task(task_id)

            return self._format_success_response(
                f"Task marked as complete: {updated_task['title']}",
                "complete_task",
                {
                    "action": "complete_task",
                    "source": "M365",
                    "task_id": task_id,
                    "task": updated_task
                }
            )

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error completing task: {e}")
            return self._format_error_response(
                "I had trouble completing your task. Please try again.",
                "complete_task",
                str(e)
            )

    # =============================
    # Helper Methods
    # =============================

    def _format_task_list(self, tasks: List[Dict], title: str) -> str:
        """
        Format a list of tasks for display.

        Args:
            tasks: List of task dictionaries
            title: Title for the list

        Returns:
            Formatted string
        """
        if not tasks:
            return f"{title}: None"

        lines = [f"{title}:"]

        for task in tasks:
            # Status icon
            status_icon = "✓" if task.get("status") == "completed" else "○"

            # Importance marker
            importance_marker = " !" if task.get("importance") == "high" else ""

            # Build task line
            task_line = f"{status_icon} {task['title']}{importance_marker}"

            # Add due date if present
            if task.get("due_date"):
                try:
                    due_date_str = task["due_date"]
                    due_date = parse_m365_task_datetime(due_date_str)

                    task_line += f" (due: {due_date.strftime('%b %d')})"
                except (ValueError, AttributeError):
                    pass

            lines.append(task_line)

        return "\n".join(lines)

    def _generate_task_summary(self, tasks: List[Dict], user_id: int, time_period: str = "this week") -> str:
        """
        Generate an AI summary of tasks using LLM.

        Args:
            tasks: List of task dictionaries
            user_id: User ID for context
            time_period: Time period description (e.g., "today", "this week")

        Returns:
            AI-generated summary of tasks
        """
        from providers.openai import OpenAIProvider
        from providers.anthropic import AnthropicProvider
        from providers.gemini import GoogleProvider
        from providers.grok import XAIProvider
        from providers.mistral import MistralProvider
        from core.provider_registry import ProviderRegistry

        try:
            # Get system provider for lightweight tasks (configurable)
            registry = ProviderRegistry(self.memory)

            # First check for "system" routing preference
            system_provider_id = self.memory.get_routing_provider(user_id, "system") if self.memory else None
            provider_cfg = None

            if system_provider_id:
                # Use configured system provider
                provider_cfg = registry.get(system_provider_id)
                self.logger.info(f"[TaskHandlers] Using configured system provider: {system_provider_id}")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Try configured fallback provider for system intent
                fallback_provider_id = self.memory.get_fallback_provider(user_id, "system") if self.memory else None
                if fallback_provider_id:
                    provider_cfg = registry.get(fallback_provider_id)
                    if provider_cfg and provider_cfg.get("api_key"):
                        self.logger.info(f"[TaskHandlers] Using configured fallback provider: {fallback_provider_id}")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Fallback to OpenAI provider
                provider_cfg = registry.get_by_type("openai")
                self.logger.info("[TaskHandlers] Using fallback OpenAI provider for task summarization")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # No LLM available at all
                self.logger.warning("[TaskHandlers] No LLM provider available, using basic task list")
                return self._format_task_list(tasks, f"Tasks {time_period}")

            # Instantiate appropriate provider based on type
            provider_type = provider_cfg.get("type", "openai")
            if provider_type == "openai":
                provider = OpenAIProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model") or "gpt-4o-mini"
                )
            elif provider_type == "anthropic":
                provider = AnthropicProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "google":
                provider = GoogleProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "xai":
                provider = XAIProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            elif provider_type == "mistral":
                provider = MistralProvider(
                    api_key=provider_cfg["api_key"],
                    base_url=provider_cfg.get("base_url"),
                    model=provider_cfg.get("model")
                )
            else:
                # Unknown provider type
                self.logger.warning(f"[TaskHandlers] Provider type {provider_type} not supported for lightweight tasks, using basic task list")
                return self._format_task_list(tasks, f"Tasks {time_period}")

            # Build task context for LLM
            task_context = []
            for task in tasks:
                task_info = f"Title: {task.get('title', 'Untitled')}\n"
                task_info += f"Status: {task.get('status', 'notStarted')}\n"

                if task.get('importance'):
                    task_info += f"Importance: {task.get('importance')}\n"

                if task.get('due_date'):
                    try:
                        due_date = parse_m365_task_datetime(task['due_date'])
                        task_info += f"Due: {due_date.strftime('%b %d, %Y')}\n"
                    except (ValueError, AttributeError):
                        pass

                if task.get('body'):
                    body = task['body']
                    if isinstance(body, dict):
                        body = body.get('content', '')
                    # Limit body to first 100 chars
                    if body and len(body) > 100:
                        body = body[:100] + "..."
                    if body:
                        task_info += f"Notes: {body}\n"

                task_context.append(task_info)

            tasks_text = "\n---\n\n".join(task_context)

            # Construct summarization prompt
            self.logger.info(f"[TaskHandlers] Generating summary for {len(tasks)} tasks ({time_period})")
            system_prompt = f"""You are a task assistant. Provide a brief, conversational summary of the user's tasks.

Rules:
1. Start with EXACTLY the count I give you (e.g., "You have 3 tasks due this week")
2. Mention only the MOST important or urgent tasks
3. If a task has high importance, mention it
4. Group by theme when possible
5. Maximum 2-3 sentences total
6. Be natural and conversational
7. CRITICAL: Use the EXACT task count - do not estimate or round

Example: "You have 3 tasks due this week. Most important is the quarterly report (high priority, due Friday). You also need to schedule the team meeting and review the budget."

Focus on what matters. Be concise."""

            user_prompt = f"Here are EXACTLY {len(tasks)} tasks due {time_period}. Provide a brief summary:\n\n{tasks_text}"

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Extract text from response
            summary_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            self.logger.info(f"[TaskHandlers] Generated task summary for {len(tasks)} tasks")
            return summary_text

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Task summary generation failed: {e}")
            # Fallback to basic formatting
            return self._format_task_list(tasks, f"Tasks {time_period}")

    def _extract_task_details(self, user_text: str) -> Dict:
        """
        Extract task details from user message.

        Extracts:
        - Title (required)
        - Description (optional)
        - Due date (optional)
        - Importance/priority (optional)

        Args:
            user_text: User's input text

        Returns:
            Dictionary with extracted details
        """
        details = {}

        # Extract title - everything after "add a task" or similar trigger phrases
        title_patterns = [
            r'add\s+a\s+task\s+(?:to\s+)?(.+)',
            r'create\s+(?:a\s+)?task\s+(?:to\s+)?(.+)',
            r'new\s+task\s+(?:to\s+)?(.+)',
            r'make\s+(?:a\s+)?task\s+(?:to\s+)?(.+)',
        ]

        for pattern in title_patterns:
            match = re.search(pattern, user_text.lower())
            if match:
                details["title"] = match.group(1).strip()
                break

        # If no pattern match, try removing common prefixes
        if not details.get("title"):
            cleaned = re.sub(
                r'(add|create|new|make)\s+(a\s+)?task\s*:?\s*',
                '',
                user_text,
                flags=re.IGNORECASE
            )
            details["title"] = cleaned.strip()

        # Extract due date (simple patterns)
        text_lower = user_text.lower()

        if re.search(r'\btoday\b', text_lower):
            details["due_date"] = datetime.now()
        elif re.search(r'\btomorrow\b', text_lower):
            details["due_date"] = datetime.now() + timedelta(days=1)
        elif re.search(r'\bnext\s+week\b', text_lower):
            details["due_date"] = datetime.now() + timedelta(weeks=1)
        elif re.search(r'\bmonday\b', text_lower):
            # Next Monday
            today = datetime.now()
            days_ahead = 0 - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            details["due_date"] = today + timedelta(days=days_ahead)
        # Add more day patterns as needed

        # Extract importance
        if re.search(r'\b(important|urgent|high\s+priority|asap)\b', text_lower):
            details["importance"] = "high"
        elif re.search(r'\b(low\s+priority)\b', text_lower):
            details["importance"] = "low"
        else:
            details["importance"] = "normal"

        return details

    def _format_task_confirmation(self, task_details: Dict) -> str:
        """
        Format confirmation message for task creation.

        Args:
            task_details: Task details dictionary

        Returns:
            Formatted confirmation message
        """
        lines = [
            "I'll create this task for you:",
            f"Title: {task_details['title']}"
        ]

        if task_details.get("due_date"):
            due_str = task_details["due_date"].strftime("%B %d, %Y")
            lines.append(f"Due: {due_str}")

        if task_details.get("importance") != "normal":
            lines.append(f"Priority: {task_details['importance']}")

        lines.append("\nReply 'yes' to confirm or 'no' to cancel.")

        return "\n".join(lines)

    def _extract_task_id(
        self,
        user_text: str,
        user_id: int,
        provider: Any
    ) -> Optional[str]:
        """
        Extract task ID from user message.

        Attempts to find the task by matching title keywords from user's message
        against existing tasks.

        Args:
            user_text: User's input text
            user_id: User ID
            provider: M365 provider instance

        Returns:
            Task ID if found, None otherwise
        """
        try:
            # Get user's tasks
            tasks = provider.read_tasks()

            if not tasks:
                return None

            # Simple matching - look for task title in user text
            text_lower = user_text.lower()

            for task in tasks:
                task_title = task.get("title", "").lower()
                if task_title and task_title in text_lower:
                    return task["id"]

            # More lenient matching - check if any words from task title are in user text
            user_words = set(re.findall(r'\b\w+\b', text_lower))

            best_match = None
            best_match_score = 0

            for task in tasks:
                task_title = task.get("title", "").lower()
                task_words = set(re.findall(r'\b\w+\b', task_title))

                # Calculate overlap
                overlap = len(user_words & task_words)

                if overlap > best_match_score:
                    best_match_score = overlap
                    best_match = task["id"]

            # Only return if we have a reasonable match (at least 2 words)
            if best_match_score >= 2:
                return best_match

            return None

        except Exception as e:
            self.logger.error(f"[TaskHandlers] Error extracting task ID: {e}")
            return None
