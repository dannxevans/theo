"""
Plex Action Handlers

Provides action handlers for Plex integration, enabling conversational queries
about viewing history and recommendations.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime

from .base_handler import BaseActionHandler

logger = logging.getLogger(__name__)


class PlexHandlers(BaseActionHandler):
    """Action handlers for Plex integration."""

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """
        Initialize Plex handlers.

        Args:
            action_registry: ActionProviderRegistry instance
            memory_store: MemoryStore instance
            confirmation_manager: ConfirmationManager instance (optional)
        """
        super().__init__(action_registry, memory_store, confirmation_manager)
        self.logger = logging.getLogger(__name__)

    def handle_plex(
        self, user_text: str, session_id: str, user_id: int, context: Dict
    ) -> Dict:
        """
        General Plex handler that routes to specific Plex actions based on query.

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Request context

        Returns:
            dict: Action response
        """
        text_l = user_text.lower()

        # Determine which Plex action based on keywords
        if any(phrase in text_l for phrase in ["currently playing", "what am i watching", "watching now", "playing now"]):
            return self.handle_get_currently_playing(user_text, session_id, user_id, context)
        elif any(phrase in text_l for phrase in ["what should i watch", "what to watch", "on deck", "up next", "watch next", "anything new", "new to watch", "new on plex"]):
            return self.handle_get_on_deck(user_text, session_id, user_id, context)
        else:
            # Default to recently watched for queries like "what was i watching"
            return self.handle_get_recently_watched(user_text, session_id, user_id, context)

    def handle_get_recently_watched(
        self, user_text: str, session_id: str, user_id: int, context: Dict
    ) -> Dict:
        """
        Handle "What was I watching?" queries.

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Request context

        Returns:
            dict: Action response
        """
        try:
            credentials = self.memory.get_plex_credentials(user_id)
            if not credentials or not credentials.get("is_valid"):
                return {
                    "text": "Your Plex account isn't connected or the credentials are invalid. Please connect your Plex account in Settings.",
                    "provider": "plex",
                    "model": None,
                    "task_type": "plex_recently_watched",
                }

            from services.plex_client import PlexClient

            client = PlexClient(
                credentials["access_token"], credentials["server_url"]
            )
            items = client.get_recently_watched(limit=5)

            formatted = _format_recently_watched(items)

            # Process through lightweight LLM for natural language
            llm_result = self._process_with_llm(formatted, user_id)

            metadata = {
                "item_count": len(items) if items else 0,
                "service": "Plex",
                "sub_task": "Recently watched"
            }

            # Add LLM provider info to metadata
            if llm_result["provider_name"]:
                metadata["llm_provider_name"] = llm_result["provider_name"]
            if llm_result["model"]:
                metadata["llm_model"] = llm_result["model"]

            return {
                "text": llm_result["text"],
                "provider": "action_router",
                "model": None,
                "task_type": "plex",
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"[PLEX_ACTION] Error in get_recently_watched: {e}")
            return {
                "text": f"Sorry, I couldn't fetch your recently watched items. Error: {str(e)}",
                "provider": "plex",
                "model": None,
                "task_type": "plex_recently_watched",
            }

    def handle_get_on_deck(
        self, user_text: str, session_id: str, user_id: int, context: Dict
    ) -> Dict:
        """
        Handle "What should I watch next?" queries.

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Request context

        Returns:
            dict: Action response
        """
        try:
            credentials = self.memory.get_plex_credentials(user_id)
            if not credentials or not credentials.get("is_valid"):
                return {
                    "text": "Your Plex account isn't connected. Please connect it in Settings.",
                    "provider": "plex",
                    "model": None,
                    "task_type": "plex_on_deck",
                }

            from services.plex_client import PlexClient

            client = PlexClient(
                credentials["access_token"], credentials["server_url"]
            )
            items = client.get_on_deck()

            formatted = _format_on_deck(items)

            # Process through lightweight LLM for natural language
            llm_result = self._process_with_llm(formatted, user_id)

            metadata = {
                "item_count": len(items) if items else 0,
                "service": "Plex",
                "sub_task": "On deck"
            }

            # Add LLM provider info to metadata
            if llm_result["provider_name"]:
                metadata["llm_provider_name"] = llm_result["provider_name"]
            if llm_result["model"]:
                metadata["llm_model"] = llm_result["model"]

            return {
                "text": llm_result["text"],
                "provider": "action_router",
                "model": None,
                "task_type": "plex",
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"[PLEX_ACTION] Error in get_on_deck: {e}")
            return {
                "text": f"Sorry, I couldn't fetch your On Deck items. Error: {str(e)}",
                "provider": "plex",
                "model": None,
                "task_type": "plex_on_deck",
            }

    def handle_get_currently_playing(
        self, user_text: str, session_id: str, user_id: int, context: Dict
    ) -> Dict:
        """
        Handle "What am I watching?" queries.

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Request context

        Returns:
            dict: Action response
        """
        try:
            credentials = self.memory.get_plex_credentials(user_id)
            if not credentials or not credentials.get("is_valid"):
                return {
                    "text": "Your Plex account isn't connected. Please connect it in Settings.",
                    "provider": "plex",
                    "model": None,
                    "task_type": "plex_currently_playing",
                }

            from services.plex_client import PlexClient

            client = PlexClient(
                credentials["access_token"], credentials["server_url"]
            )
            sessions = client.get_currently_playing()

            formatted = _format_currently_playing(sessions)

            # Process through lightweight LLM for natural language
            llm_result = self._process_with_llm(formatted, user_id)

            metadata = {
                "session_count": len(sessions) if sessions else 0,
                "service": "Plex",
                "sub_task": "Currently playing"
            }

            # Add LLM provider info to metadata
            if llm_result["provider_name"]:
                metadata["llm_provider_name"] = llm_result["provider_name"]
            if llm_result["model"]:
                metadata["llm_model"] = llm_result["model"]

            return {
                "text": llm_result["text"],
                "provider": "action_router",
                "model": None,
                "task_type": "plex",
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"[PLEX_ACTION] Error in get_currently_playing: {e}")
            return {
                "text": f"Sorry, I couldn't fetch currently playing sessions. Error: {str(e)}",
                "provider": "plex",
                "model": None,
                "task_type": "plex_currently_playing",
            }

    def _process_with_llm(self, raw_data: str, user_id: int) -> Dict:
        """
        Process raw Plex data through lightweight LLM for natural language output.

        Args:
            raw_data: Raw Plex data summary
            user_id: User ID for routing

        Returns:
            dict: Contains 'text', 'provider', and 'model' from LLM response
        """
        try:
            from core.router import route_request

            prompt = f"""You are presenting Plex Media Server data to the user. Convert this viewing data into a brief, friendly, conversational summary.

Guidelines:
- Be concise (2-3 sentences max)
- Use natural language, avoid bullet points
- Be conversational and casual about their viewing habits
- If showing TV shows, mention the show names naturally
- If showing movies, include relevant details like year if provided
- Keep the tone friendly and enthusiastic about their content

Raw data:
{raw_data}

Present this data in a natural, conversational way:"""

            router_context = {
                "text": prompt,
                "user_id": user_id,
                "force_intent": "system",  # Use lightweight LLM
                "memory": self.memory
            }

            result = route_request(router_context)

            self.logger.info(f"[PLEX] Processed query response via lightweight LLM")

            # Extract provider name from metadata (this is the friendly name like "Haiku-4.5")
            provider_name = None
            if result.get("metadata"):
                provider_name = result["metadata"].get("provider_name")

            return {
                "text": result.get("text", raw_data),
                "provider_name": provider_name,
                "model": result.get("model")
            }

        except Exception as e:
            self.logger.error(f"[PLEX] Error processing with LLM: {e}")
            # Fallback to raw data if LLM processing fails
            return {
                "text": raw_data,
                "provider_name": None,
                "model": None
            }


def _format_recently_watched(items: List[Dict]) -> str:
    """
    Format recently watched items for display.

    Args:
        items: List of recently watched items

    Returns:
        str: Formatted response
    """
    if not items:
        return "No recently watched items found."

    lines = ["Here's what you've been watching recently:"]

    for item in items[:5]:  # Show top 5
        item_type = item.get("type")

        if item_type == "episode":
            show = item.get("show_title", "Unknown Show")
            season = item.get("season", 0)
            episode = item.get("episode", 0)
            title = item.get("title", "")
            lines.append(
                f"• {show} - S{season:02d}E{episode:02d}"
                + (f' "{title}"' if title else "")
            )

        elif item_type == "movie":
            title = item.get("title", "Unknown Movie")
            year = item.get("year")
            lines.append(f"• {title}" + (f" ({year})" if year else ""))

        else:
            title = item.get("title", "Unknown")
            lines.append(f"• {title}")

    return "\n".join(lines)


def _format_on_deck(items: List[Dict]) -> str:
    """
    Format On Deck items for display.

    Args:
        items: List of On Deck items

    Returns:
        str: Formatted response
    """
    if not items:
        return "No items in your On Deck queue."

    lines = ["Here's what's up next to watch:"]

    for item in items[:5]:  # Show top 5
        item_type = item.get("type")

        if item_type == "episode":
            show = item.get("show_title", "Unknown Show")
            season = item.get("season", 0)
            episode = item.get("episode", 0)
            title = item.get("title", "")
            lines.append(
                f"• {show} - S{season:02d}E{episode:02d}"
                + (f' "{title}"' if title else "")
            )

        elif item_type == "movie":
            title = item.get("title", "Unknown Movie")
            year = item.get("year")
            lines.append(f"• {title}" + (f" ({year})" if year else ""))

        else:
            title = item.get("title", "Unknown")
            lines.append(f"• {title}")

    return "\n".join(lines)


def _format_currently_playing(sessions: List[Dict]) -> str:
    """
    Format currently playing sessions for display.

    Args:
        sessions: List of active sessions

    Returns:
        str: Formatted response
    """
    if not sessions:
        return "Nothing is currently playing on your Plex server."

    lines = ["Currently playing:"]

    for session in sessions:
        item_type = session.get("type")
        user = session.get("user", "Unknown")
        player = session.get("player", "Unknown Device")
        state = session.get("state", "unknown")

        if item_type == "episode":
            show = session.get("show_title", "Unknown Show")
            season = session.get("season", 0)
            episode = session.get("episode", 0)
            title = session.get("title", "")
            lines.append(
                f"• {show} - S{season:02d}E{episode:02d}"
                + (f' "{title}"' if title else "")
                + f" ({state} on {player})"
            )

        elif item_type == "movie":
            title = session.get("title", "Unknown Movie")
            lines.append(f"• {title} ({state} on {player})")

        else:
            title = session.get("title", "Unknown")
            lines.append(f"• {title} ({state} on {player})")

    return "\n".join(lines)
