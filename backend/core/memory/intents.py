"""
Intent and routing operations module.

Handles:
- User-defined intents (CRUD)
- Routing preferences (intent to provider mapping)
- Default intent seeding
"""

from datetime import datetime
import logging
from sqlalchemy import select, delete, insert, update

from .base import BaseMemoryOperations


class IntentOperations(BaseMemoryOperations):
    """Operations for managing intents and routing preferences."""

    # =============================
    # Routing Preferences
    # =============================

    def set_routing_preference(self, user_id, intent, provider_id):
        """
        Set routing preference for an intent.

        Args:
            user_id: User identifier
            intent: Intent ID
            provider_id: Provider ID to route to
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent)
            )
            conn.execute(
                insert(self.routing_preferences).values(
                    user_id=user_id,
                    intent=intent,
                    provider_id=provider_id,
                    updated_at=datetime.utcnow(),
                )
            )

    def get_routing_preferences(self, user_id):
        """
        Get all routing preferences for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping intent to provider_id
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
            ).fetchall()
            return {r.intent: r.provider_id for r in rows}

    def delete_routing_preference(self, user_id, intent):
        """
        Delete a routing preference.

        Args:
            user_id: User identifier
            intent: Intent ID
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent)
            )

    def get_routing_provider(self, user_id, intent):
        """
        Get provider ID for a specific intent.

        Args:
            user_id: User identifier
            intent: Intent ID

        Returns:
            Provider ID or None if not set
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.routing_preferences.c.provider_id)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent)
            ).fetchone()
            return row.provider_id if row else None

    def set_routing_provider(self, user_id, intent, provider_id):
        """
        Alias for set_routing_preference.

        Args:
            user_id: User identifier
            intent: Intent ID
            provider_id: Provider ID to route to
        """
        self.set_routing_preference(user_id, intent, provider_id)

    # =============================
    # Intent Management
    # =============================

    def list_intents(self, user_id):
        """
        Get all intents for a user, ordered by priority (highest first).

        Args:
            user_id: User identifier

        Returns:
            List of intent dictionaries
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.intents)
                .where(self.intents.c.user_id == user_id)
                .order_by(self.intents.c.priority.desc(), self.intents.c.name)
            ).fetchall()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "keywords": r.keywords,
                    "priority": r.priority,
                    "enabled": r.enabled,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]

    def get_intent(self, user_id, intent_id):
        """
        Get a single intent by ID.

        Args:
            user_id: User identifier
            intent_id: Intent ID

        Returns:
            Intent dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.intents)
                .where(self.intents.c.user_id == user_id)
                .where(self.intents.c.id == intent_id)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "keywords": row.keywords,
                "priority": row.priority,
                "enabled": row.enabled,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }

    def create_intent(self, user_id, intent_id, name, description, keywords, priority=0, enabled=True):
        """
        Create a new intent.

        Args:
            user_id: User identifier
            intent_id: Intent ID
            name: Display name
            description: Intent description
            keywords: Comma-separated keywords
            priority: Priority (higher = checked first)
            enabled: Whether intent is enabled
        """
        with self._get_connection() as conn:
            conn.execute(
                insert(self.intents).values(
                    id=intent_id,
                    user_id=user_id,
                    name=name,
                    description=description,
                    keywords=keywords,
                    priority=priority,
                    enabled=enabled,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

    def update_intent(self, user_id, intent_id, **updates):
        """
        Update an existing intent.

        Args:
            user_id: User identifier
            intent_id: Intent ID
            **updates: Fields to update

        Raises:
            ValueError: If intent does not exist
        """
        updates["updated_at"] = datetime.utcnow()
        with self._get_connection() as conn:
            result = conn.execute(
                update(self.intents)
                .where(self.intents.c.user_id == user_id)
                .where(self.intents.c.id == intent_id)
                .values(**updates)
            )
            if result.rowcount == 0:
                raise ValueError(f"Intent {intent_id} not found")

    def delete_intent(self, user_id, intent_id):
        """
        Delete an intent and its routing preferences.

        Args:
            user_id: User identifier
            intent_id: Intent ID

        Raises:
            ValueError: If intent does not exist
        """
        with self._get_connection() as conn:
            # Delete routing preferences first
            conn.execute(
                delete(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent_id)
            )
            # Delete intent
            result = conn.execute(
                delete(self.intents)
                .where(self.intents.c.user_id == user_id)
                .where(self.intents.c.id == intent_id)
            )
            if result.rowcount == 0:
                raise ValueError(f"Intent {intent_id} not found")

    def seed_default_intents(self, user_id):
        """
        Seed default intents if none exist for the user.

        Args:
            user_id: User identifier
        """
        existing = self.list_intents(user_id)
        if existing:
            return  # Already has intents

        default_intents = [
            {
                "id": "coding",
                "name": "Coding",
                "description": "Programming, debugging, code review, and technical tasks",
                "keywords": "code,coding,script,function,python,javascript,js,api,bug,error,debug,programming,software,class,method,variable",
                "priority": 90,
            },
            {
                "id": "reasoning",
                "name": "Reasoning",
                "description": "Deep analysis, explanations, and logical thinking",
                "keywords": "why,how does,explain,analyze,analysis,reasoning,logic,understand,think,consider,evaluate",
                "priority": 80,
            },
            {
                "id": "planning",
                "name": "Planning",
                "description": "Project planning, organization, and structured approaches",
                "keywords": "plan,planning,roadmap,schedule,organize,design,steps,approach,strategy,structure",
                "priority": 70,
            },
            {
                "id": "creative",
                "name": "Creative",
                "description": "Creative writing, storytelling, and artistic content",
                "keywords": "write,story,poem,creative,imagine,fiction,lyrics,novel,character,narrative",
                "priority": 60,
            },
            {
                "id": "general",
                "name": "General",
                "description": "General questions and conversations",
                "keywords": "",  # Empty keywords - catches everything else
                "priority": 0,  # Lowest priority - fallback
            },
        ]

        for intent in default_intents:
            self.create_intent(
                user_id=user_id,
                intent_id=intent["id"],
                name=intent["name"],
                description=intent["description"],
                keywords=intent["keywords"],
                priority=intent["priority"],
            )
        logging.info(f"[MEMORY] Seeded {len(default_intents)} default intents for user {user_id}")
