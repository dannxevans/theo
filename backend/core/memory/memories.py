"""
Memory operations module.

Handles all memory-related CRUD operations including:
- Preference storage (remember/forget)
- Structured memory management
- Memory relevance scoring
- System prompt configuration
"""

from datetime import datetime
from sqlalchemy import select, delete, insert, update, func, case

from .base import BaseMemoryOperations


class MemoryOperations(BaseMemoryOperations):
    """Operations for managing user memories and preferences."""

    def remember(self, user_id, key, value):
        """
        Store a user preference (legacy API).

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.preferences)
                .where(self.preferences.c.user_id == user_id)
                .where(self.preferences.c.key == key)
            )
            conn.execute(
                insert(self.preferences).values(
                    user_id=user_id,
                    key=key,
                    value=value,
                    updated_at=datetime.utcnow(),
                )
            )

    def forget(self, user_id, key):
        """
        Remove a user preference (legacy API).

        Args:
            user_id: User identifier
            key: Preference key
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.preferences)
                .where(self.preferences.c.user_id == user_id)
                .where(self.preferences.c.key == key)
            )

    def get_all(self, user_id):
        """
        Get all user preferences (legacy API).

        Args:
            user_id: User identifier

        Returns:
            Dictionary of key-value pairs
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.preferences)
                .where(self.preferences.c.user_id == user_id)
            ).fetchall()
            return {r.key: r.value for r in rows}

    def store_memory(self, user_id, memory_type, key, value, pinned=False):
        """
        Store a structured memory with type classification.

        Args:
            user_id: User identifier
            memory_type: Type of memory (fact, preference, goal, context)
            key: Memory key/identifier
            value: Memory content
            pinned: Whether memory should be pinned (not subject to decay)
        """
        with self._get_connection() as conn:
            # Check if memory with this key already exists
            existing = conn.execute(
                select(self.memories.c.id)
                .where(self.memories.c.user_id == user_id)
                .where(self.memories.c.key == key)
            ).fetchone()

            now = datetime.utcnow()

            if existing:
                # Update existing memory
                conn.execute(
                    update(self.memories)
                    .where(self.memories.c.id == existing.id)
                    .values(
                        value=value,
                        type=memory_type,
                        relevance_score=100,  # Reset score on update
                        pinned=pinned,
                        last_accessed_at=now,
                        access_count=self.memories.c.access_count + 1,
                    )
                )
            else:
                # Insert new memory
                conn.execute(
                    insert(self.memories).values(
                        user_id=user_id,
                        type=memory_type,
                        key=key,
                        value=value,
                        relevance_score=100,
                        pinned=pinned,
                        created_at=now,
                        last_accessed_at=now,
                        access_count=1,
                    )
                )

    def get_memories(self, user_id, memory_type=None, limit=None):
        """
        Retrieve memories, optionally filtered by type.

        Args:
            user_id: User identifier
            memory_type: Optional type filter (fact, preference, goal, context)
            limit: Optional maximum number of results

        Returns:
            List of memory dictionaries sorted by relevance score (descending)
        """
        with self._get_connection() as conn:
            query = select(self.memories).where(self.memories.c.user_id == user_id)

            if memory_type:
                query = query.where(self.memories.c.type == memory_type)

            query = query.order_by(self.memories.c.relevance_score.desc())

            if limit:
                query = query.limit(limit)

            rows = conn.execute(query).fetchall()
            return [dict(row._mapping) for row in rows]

    def get_relevant_memories(self, user_id, query_text, max_results=7):
        """
        Score and return most relevant memories for a given query.

        Scoring logic:
        - Pinned memories always included
        - Keyword match in query boosts score
        - Recent access boosts score
        - Time decay reduces score

        Args:
            user_id: User identifier
            query_text: Query text to match against
            max_results: Maximum number of memories to return

        Returns:
            List of memory dictionaries with computed_relevance scores
        """
        with self._get_connection() as conn:
            all_memories = conn.execute(
                select(self.memories)
                .where(self.memories.c.user_id == user_id)
            ).fetchall()

            if not all_memories:
                return []

            scored_memories = []
            query_lower = query_text.lower()
            now = datetime.utcnow()

            for mem in all_memories:
                score = mem.relevance_score

                # Pinned memories get max boost
                if mem.pinned:
                    score += 200

                # Keyword match boost
                key_lower = mem.key.lower()
                value_lower = mem.value.lower()

                if key_lower in query_lower or any(word in query_lower for word in key_lower.split()):
                    score += 50

                if value_lower in query_lower:
                    score += 30

                # Access frequency boost
                score += min(mem.access_count * 2, 20)

                # Time decay (1 point per day old, max -30)
                days_old = (now - mem.created_at).days
                score -= min(days_old, 30)

                # Recent access boost
                days_since_access = (now - mem.last_accessed_at).days
                if days_since_access < 7:
                    score += 15

                scored_memories.append({
                    "memory": dict(mem._mapping),
                    "computed_score": max(score, 0)
                })

            # Sort by computed score
            scored_memories.sort(key=lambda x: x["computed_score"], reverse=True)

            # Return top N with scores
            results = []
            for item in scored_memories[:max_results]:
                mem_data = item["memory"]
                mem_data["computed_relevance"] = item["computed_score"]
                results.append(mem_data)

            # Update access stats for returned memories
            for mem in results:
                conn.execute(
                    update(self.memories)
                    .where(self.memories.c.id == mem["id"])
                    .values(
                        last_accessed_at=now,
                        access_count=self.memories.c.access_count + 1,
                    )
                )

            return results

    def delete_memory(self, user_id, memory_id):
        """
        Permanently delete a memory by ID.

        Args:
            user_id: User identifier
            memory_id: Memory ID to delete
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.memories)
                .where(self.memories.c.id == memory_id)
                .where(self.memories.c.user_id == user_id)
            )

    def pin_memory(self, user_id, memory_id, pinned=True):
        """
        Pin or unpin a memory.

        Args:
            user_id: User identifier
            memory_id: Memory ID to pin/unpin
            pinned: True to pin, False to unpin
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.memories)
                .where(self.memories.c.id == memory_id)
                .where(self.memories.c.user_id == user_id)
                .values(pinned=pinned)
            )

    def decay_memory_scores(self, user_id, decay_amount=1):
        """
        Apply time-based decay to all non-pinned memories.

        Should be called periodically (e.g., daily background task).

        Args:
            user_id: User identifier
            decay_amount: Amount to decrease relevance scores
        """
        with self._get_connection() as conn:
            # Use case expression for SQLite compatibility (no greatest function)
            new_score = case(
                (self.memories.c.relevance_score - decay_amount > 0,
                 self.memories.c.relevance_score - decay_amount),
                else_=0
            )
            conn.execute(
                update(self.memories)
                .where(self.memories.c.user_id == user_id)
                .where(self.memories.c.pinned == False)
                .values(relevance_score=new_score)
            )

    def get_system_prompt_config(self, user_id):
        """
        Get system prompt configuration for a user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with persona_name, tone, style_rules, custom_instructions
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.system_prompt_config)
                .where(self.system_prompt_config.c.user_id == user_id)
            ).fetchone()

            if row:
                return {
                    "persona_name": row.persona_name,
                    "tone": row.tone,
                    "style_rules": row.style_rules,
                    "custom_instructions": row.custom_instructions,
                }
            else:
                # Return defaults if not configured
                return {
                    "persona_name": "THEO",
                    "tone": "professional, conversational, direct",
                    "style_rules": "No em dashes\nBe concise first, then detailed\nProvide full working solutions when asked for code\nMaintain a consistent persona regardless of model",
                    "custom_instructions": None,
                }

    def update_system_prompt_config(self, user_id, **updates):
        """
        Update system prompt configuration.

        Args:
            user_id: User identifier
            **updates: Fields to update (persona_name, tone, style_rules, custom_instructions)
        """
        with self._get_connection() as conn:
            # Check if config exists
            existing = conn.execute(
                select(self.system_prompt_config.c.user_id)
                .where(self.system_prompt_config.c.user_id == user_id)
            ).fetchone()

            updates["updated_at"] = datetime.utcnow()

            if existing:
                # Update existing
                conn.execute(
                    update(self.system_prompt_config)
                    .where(self.system_prompt_config.c.user_id == user_id)
                    .values(**updates)
                )
            else:
                # Insert new with defaults + updates
                defaults = {
                    "user_id": user_id,
                    "persona_name": "THEO",
                    "tone": "professional, conversational, direct",
                    "style_rules": "No em dashes\nBe concise first, then detailed\nProvide full working solutions when asked for code\nMaintain a consistent persona regardless of model",
                    "custom_instructions": None,
                }
                defaults.update(updates)
                conn.execute(insert(self.system_prompt_config).values(**defaults))
