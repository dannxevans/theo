from datetime import datetime
import logging
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Integer,
    Boolean,
    Table,
    MetaData,
    select,
    delete,
    insert,
    update,
    func,
    and_,
)
from sqlalchemy.orm import sessionmaker


class MemoryStore:
    """
    SQLite-backed memory store for THEO.

    Responsibilities:
    - User preferences (explicit remember / forget)
    - Session summaries
    - Conversation turns (rolling context)
    """

    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.meta = MetaData()

        # =============================
        # Users (Authentication)
        # =============================
        self.users = Table(
            "users",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("username", String, nullable=False, unique=True),
            Column("password_hash", String, nullable=False),
            Column("is_admin", Boolean, default=False),
            Column("is_enabled", Boolean, default=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Sessions (Authentication)
        # =============================
        self.auth_sessions = Table(
            "auth_sessions",
            self.meta,
            Column("id", String, primary_key=True),
            Column("user_id", Integer, nullable=False),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("expires_at", DateTime, nullable=False),
        )

        # =============================
        # Mode Configuration (Work/Personal)
        # =============================
        self.user_mode_config = Table(
            "user_mode_config",
            self.meta,
            Column("user_id", Integer, nullable=False, primary_key=True),
            Column("active_mode", String, default="personal"),  # "work" or "personal"
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        self.mode_settings = Table(
            "mode_settings",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False),
            Column("mode", String, nullable=False),  # "work" or "personal"
            Column("system_prompt_override", Text, nullable=True),
            Column("preferred_provider_id", Integer, nullable=True),
            Column("tone", String, default="neutral"),  # "professional", "casual", "neutral"
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Work Mode Sub-Tab Configuration
        # =============================
        self.work_mode_subtab_config = Table(
            "work_mode_subtab_config",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False),
            Column("subtab", String, nullable=False),  # "conversation", "email", "code"
            Column("config_json", Text, nullable=True),  # JSON for subtab-specific config
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Debug Settings
        # =============================
        self.debug_settings = Table(
            "debug_settings",
            self.meta,
            Column("user_id", String, nullable=False, primary_key=True),
            Column("enabled", Boolean, default=False),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Preferences (legacy - kept for settings)
        # =============================
        self.preferences = Table(
            "preferences",
            self.meta,
            Column("user_id", String, nullable=False),
            Column("key", String, nullable=False),
            Column("value", Text, nullable=False),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # System Prompt Configuration
        # =============================
        self.system_prompt_config = Table(
            "system_prompt_config",
            self.meta,
            Column("user_id", String, nullable=False, primary_key=True),
            Column("persona_name", String, default="THEO"),
            Column("tone", String, default="professional, conversational, direct"),
            Column("style_rules", Text, default="No em dashes\nBe concise first, then detailed\nProvide full working solutions when asked for code\nMaintain a consistent persona regardless of model"),
            Column("custom_instructions", Text, nullable=True),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Structured Memory (Step 2)
        # =============================
        self.memories = Table(
            "memories",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", String, nullable=False),
            Column("type", String, nullable=False),  # fact, preference, goal, context
            Column("key", String, nullable=False),
            Column("value", Text, nullable=False),
            Column("relevance_score", Integer, default=100),  # 0-100, decays over time
            Column("pinned", Boolean, default=False),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("last_accessed_at", DateTime, default=datetime.utcnow),
            Column("access_count", Integer, default=0),
        )

        # =============================
        # User-Defined Intents
        # =============================
        self.intents = Table(
            "intents",
            self.meta,
            Column("id", String, primary_key=True),  # e.g., "coding", "creative"
            Column("user_id", String, nullable=False),
            Column("name", String, nullable=False),  # Display name
            Column("description", Text, nullable=True),  # What this intent is for
            Column("keywords", Text, nullable=False),  # Comma-separated keywords
            Column("priority", Integer, default=0),  # Higher priority checked first
            Column("enabled", Boolean, default=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Routing Preferences
        # =============================
        self.routing_preferences = Table(
            "routing_preferences",
            self.meta,
            Column("user_id", String, nullable=False),
            Column("intent", String, nullable=False),
            Column("provider_id", String, nullable=False),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Step 3: Provider Intelligence
        # =============================
        self.provider_metadata = Table(
            "provider_metadata",
            self.meta,
            Column("provider_id", String, primary_key=True),
            Column("cost_per_1k_input_tokens", Integer, default=0),  # in micro-dollars (1/1000000 of $1)
            Column("cost_per_1k_output_tokens", Integer, default=0),
            Column("avg_latency_ms", Integer, default=0),
            Column("total_requests", Integer, default=0),
            Column("failed_requests", Integer, default=0),
            Column("last_success_at", DateTime, nullable=True),
            Column("last_failure_at", DateTime, nullable=True),
            Column("health_status", String, default="unknown"),  # healthy, degraded, unhealthy, unknown
            Column("circuit_breaker_open", Boolean, default=False),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        self.request_logs = Table(
            "request_logs",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String, nullable=False),
            Column("provider_id", String, nullable=False),
            Column("intent", String, nullable=False),
            Column("success", Boolean, default=True),
            Column("latency_ms", Integer, nullable=True),
            Column("input_tokens", Integer, default=0),
            Column("output_tokens", Integer, default=0),
            Column("estimated_cost", Integer, default=0),  # in micro-dollars
            Column("error_message", Text, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Providers
        # =============================
        self.providers = Table(
            "providers",
            self.meta,
            Column("id", String, primary_key=True),
            Column("name", String, nullable=False),
            Column("type", String, nullable=False),
            Column("base_url", String, nullable=True),
            Column("model", String, nullable=True),
            Column("api_key", Text, nullable=True),
            Column("enabled", Boolean, default=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Sessions
        # =============================
        self.sessions = Table(
            "sessions",
            self.meta,
            Column("id", String, primary_key=True),
            Column("title", String, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Session summaries
        # =============================
        self.summaries = Table(
            "summaries",
            self.meta,
            Column("session_id", String, nullable=False),
            Column("content", Text, nullable=False),
            Column("created_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Conversation turns
        # =============================
        self.turns = Table(
            "turns",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("session_id", String, nullable=False),
            Column("role", String, nullable=False),
            Column("content", Text, nullable=False),
            Column("created_at", DateTime, default=datetime.utcnow),
            # Provider metadata for assistant messages
            Column("provider_id", String, nullable=True),
            Column("model", String, nullable=True),
            Column("intent", String, nullable=True),
            Column("metadata", Text, nullable=True),  # JSON metadata for confirmations, etc.
        )

        # =============================
        # Session Providers
        # =============================
        self.session_providers = Table(
            "session_providers",
            self.meta,
            Column("session_id", String, primary_key=True),
            Column("provider_id", String, nullable=False),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Personal AI Agent: Service Providers
        # =============================
        self.service_providers = Table(
            "service_providers",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False),
            Column("name", String, nullable=False),
            Column("category", String, nullable=False),
            Column("provider_type", String, nullable=False),
            Column("capabilities", Text, nullable=True),
            Column("api_base_url", String, nullable=True),
            Column("auth_method", String, nullable=True),
            Column("access_token", Text, nullable=True),
            Column("refresh_token", Text, nullable=True),
            Column("token_expires_at", DateTime, nullable=True),
            Column("api_endpoint_calendar", String, nullable=True),
            Column("api_endpoint_email", String, nullable=True),
            Column("additional_metadata", Text, nullable=True),
            Column("trust_level", String, default="manual"),
            Column("booking_method", String, nullable=True),
            Column("preferred_for_category", Boolean, default=False),
            Column("is_enabled", Boolean, default=True),
            Column("last_synced_at", DateTime, nullable=True),
            Column("health_status", String, default="unknown"),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Personal AI Agent: Actions
        # =============================
        self.actions = Table(
            "actions",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False),
            Column("session_id", String, nullable=False),
            Column("action_type", String, nullable=False),
            Column("category", String, nullable=False),
            Column("intent_summary", Text, nullable=False),
            Column("service_provider_id", Integer, nullable=True),
            Column("action_params", Text, nullable=True),
            Column("planned_execution_time", DateTime, nullable=True),
            Column("status", String, default="pending"),
            Column("requires_confirmation", Boolean, default=True),
            Column("initiated_at", DateTime, nullable=True),
            Column("approved_at", DateTime, nullable=True),
            Column("executed_at", DateTime, nullable=True),
            Column("completed_at", DateTime, nullable=True),
            Column("result_data", Text, nullable=True),
            Column("error_message", Text, nullable=True),
            Column("retry_count", Integer, default=0),
            Column("max_retries", Integer, default=3),
            Column("is_reversible", Boolean, default=False),
            Column("rollback_action_id", Integer, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Personal AI Agent: Action Confirmations
        # =============================
        self.action_confirmations = Table(
            "action_confirmations",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("action_id", Integer, nullable=False, unique=True),
            Column("confirmation_message", Text, nullable=False),
            Column("user_response", String, nullable=True),
            Column("user_response_text", Text, nullable=True),
            Column("modified_params", Text, nullable=True),
            Column("presented_at", DateTime, nullable=False),
            Column("responded_at", DateTime, nullable=True),
            Column("expires_at", DateTime, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Personal AI Agent: M365 Credentials
        # =============================
        self.m365_credentials = Table(
            "m365_credentials",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False, unique=True),
            Column("access_token", Text, nullable=False),
            Column("refresh_token", Text, nullable=False),
            Column("token_type", String, default="Bearer"),
            Column("expires_at", DateTime, nullable=False),
            Column("scope", Text, nullable=True),
            Column("tenant_id", String, nullable=True),
            Column("user_principal_name", String, nullable=True),
            Column("is_valid", Boolean, default=True),
            Column("last_refreshed_at", DateTime, nullable=True),
            Column("last_error", Text, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
            Column("updated_at", DateTime, default=datetime.utcnow),
        )

        # =============================
        # Personal AI Agent: Calendar Events Cache
        # =============================
        self.calendar_events_cache = Table(
            "calendar_events_cache",
            self.meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", Integer, nullable=False),
            Column("event_id", String, nullable=False),
            Column("calendar_id", String, nullable=True),
            Column("subject", String, nullable=True),
            Column("start_time", DateTime, nullable=False),
            Column("end_time", DateTime, nullable=False),
            Column("location", String, nullable=True),
            Column("description", Text, nullable=True),
            Column("attendees", Text, nullable=True),
            Column("is_all_day", Boolean, default=False),
            Column("status", String, nullable=True),
            Column("importance", String, nullable=True),
            Column("fetched_at", DateTime, nullable=False),
            Column("cache_expires_at", DateTime, nullable=True),
            Column("created_at", DateTime, default=datetime.utcnow),
        )

        self.meta.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    # =============================
    # Preferences API
    # =============================
    def remember(self, user_id, key, value):
        with self.engine.begin() as conn:
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
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.preferences)
                .where(self.preferences.c.user_id == user_id)
                .where(self.preferences.c.key == key)
            )

    def get_all(self, user_id):
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.preferences)
                .where(self.preferences.c.user_id == user_id)
            ).fetchall()
            return {r.key: r.value for r in rows}

    # =============================
    # Structured Memory API (Step 2)
    # =============================
    def store_memory(self, user_id, memory_type, key, value, pinned=False):
        """
        Store a structured memory with type classification.
        Types: fact, preference, goal, context
        """
        with self.engine.begin() as conn:
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
        Returns list of memory dicts sorted by relevance score (descending).
        """
        with self.engine.begin() as conn:
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
        """
        import math
        from datetime import timedelta

        with self.engine.begin() as conn:
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
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.memories)
                .where(self.memories.c.id == memory_id)
                .where(self.memories.c.user_id == user_id)
            )

    def pin_memory(self, user_id, memory_id, pinned=True):
        """
        Pin or unpin a memory.
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.memories)
                .where(self.memories.c.id == memory_id)
                .where(self.memories.c.user_id == user_id)
                .values(pinned=pinned)
            )

    def decay_memory_scores(self, user_id, decay_amount=1):
        """
        Apply time-based decay to all non-pinned memories.
        Called periodically (e.g., daily background task).
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.memories)
                .where(self.memories.c.user_id == user_id)
                .where(self.memories.c.pinned == False)
                .values(
                    relevance_score=func.greatest(
                        self.memories.c.relevance_score - decay_amount,
                        0
                    )
                )
            )

    # =============================
    # System Prompt Configuration API
    # =============================
    def get_system_prompt_config(self, user_id):
        """Get system prompt configuration for a user."""
        with self.engine.begin() as conn:
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
        """Update system prompt configuration for a user."""
        updates["updated_at"] = datetime.utcnow()

        with self.engine.begin() as conn:
            # Check if config exists
            exists = conn.execute(
                select(self.system_prompt_config.c.user_id)
                .where(self.system_prompt_config.c.user_id == user_id)
            ).fetchone()

            if exists:
                # Update existing
                conn.execute(
                    update(self.system_prompt_config)
                    .where(self.system_prompt_config.c.user_id == user_id)
                    .values(**updates)
                )
            else:
                # Insert new
                updates["user_id"] = user_id
                conn.execute(
                    insert(self.system_prompt_config).values(**updates)
                )

    # =============================
    # Routing Preferences API
    # =============================
    def set_routing_preference(self, user_id, intent, provider_id):
        with self.engine.begin() as conn:
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
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
            ).fetchall()
            return {r.intent: r.provider_id for r in rows}

    def delete_routing_preference(self, user_id, intent):
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent)
            )

    def get_routing_provider(self, user_id, intent):
        """
        Return provider_id for the given user_id and intent, or None if not found.
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.routing_preferences.c.provider_id)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent)
            ).fetchone()
            return row.provider_id if row else None

    def set_routing_provider(self, user_id, intent, provider_id):
        """
        Alias for set_routing_preference to set the provider for a user and intent.
        """
        self.set_routing_preference(user_id, intent, provider_id)

    # =============================
    # User-Defined Intents API
    # =============================
    def list_intents(self, user_id):
        """Get all intents for a user, ordered by priority (highest first)."""
        with self.engine.begin() as conn:
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
        """Get a single intent by ID."""
        with self.engine.begin() as conn:
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
        """Create a new intent."""
        with self.engine.begin() as conn:
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
        """Update an existing intent."""
        updates["updated_at"] = datetime.utcnow()
        with self.engine.begin() as conn:
            conn.execute(
                update(self.intents)
                .where(self.intents.c.user_id == user_id)
                .where(self.intents.c.id == intent_id)
                .values(**updates)
            )

    def delete_intent(self, user_id, intent_id):
        """Delete an intent and its routing preferences."""
        with self.engine.begin() as conn:
            # Delete routing preferences first
            conn.execute(
                delete(self.routing_preferences)
                .where(self.routing_preferences.c.user_id == user_id)
                .where(self.routing_preferences.c.intent == intent_id)
            )
            # Delete intent
            conn.execute(
                delete(self.intents)
                .where(self.intents.c.user_id == user_id)
                .where(self.intents.c.id == intent_id)
            )

    def seed_default_intents(self, user_id):
        """Seed default intents if none exist for the user."""
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

    # =============================
    # Sessions API
    # =============================
    def _ensure_session(self, session_id):
        with self.engine.begin() as conn:
            exists = conn.execute(
                select(self.sessions.c.id)
                .where(self.sessions.c.id == session_id)
            ).fetchone()
            if not exists:
                conn.execute(
                    insert(self.sessions).values(
                        id=session_id,
                        title=None,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def save_session_title(self, session_id, title):
        with self.engine.begin() as conn:
            conn.execute(
                update(self.sessions)
                .where(self.sessions.c.id == session_id)
                .values(
                    title=title,
                    updated_at=datetime.utcnow(),
                )
            )

    def list_sessions(self):
        """
        Return all sessions with their latest summary (if any),
        ordered by most recently updated (based on latest turn created_at).
        Only sessions with at least one turn are returned, limited to the most recent 50.
        """
        with self.engine.begin() as conn:
            latest_turn_subq = (
                select(
                    self.turns.c.session_id,
                    func.max(self.turns.c.created_at).label("latest_turn_created_at"),
                    func.count(self.turns.c.id).label("turn_count")
                )
                .group_by(self.turns.c.session_id)
                .subquery()
            )

            rows = conn.execute(
                select(
                    self.sessions.c.id,
                    self.sessions.c.title,
                    self.sessions.c.created_at,
                    self.sessions.c.updated_at,
                    latest_turn_subq.c.turn_count,
                    latest_turn_subq.c.latest_turn_created_at,
                )
                .join(latest_turn_subq, self.sessions.c.id == latest_turn_subq.c.session_id)
                .order_by(latest_turn_subq.c.latest_turn_created_at.desc())
                .limit(50)
            ).fetchall()

            result = []
            for r in rows:
                summary_row = conn.execute(
                    select(self.summaries.c.content)
                    .where(self.summaries.c.session_id == r.id)
                    .order_by(self.summaries.c.created_at.desc())
                    .limit(1)
                ).fetchone()

                result.append({
                    "id": r.id,
                    "title": r.title,
                    "summary": summary_row.content if summary_row else "",
                    "has_messages": r.turn_count > 0,
                    "updated_at": r.latest_turn_created_at,
                })

            return result

    def delete_session(self, session_id):
        """
        Permanently delete a session and all associated data.
        This includes:
        - session row
        - summaries
        - conversation turns
        """
        with self.engine.begin() as conn:
            # Delete turns first (FK safety even if not enforced)
            conn.execute(
                delete(self.turns)
                .where(self.turns.c.session_id == session_id)
            )

            # Delete summaries
            conn.execute(
                delete(self.summaries)
                .where(self.summaries.c.session_id == session_id)
            )

            # Delete session
            conn.execute(
                delete(self.sessions)
                .where(self.sessions.c.id == session_id)
            )

    # =============================
    # Summaries API
    # =============================
    def save_session_summary(self, session_id, content):
        self._ensure_session(session_id)
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.summaries).values(
                    session_id=session_id,
                    content=content,
                    created_at=datetime.utcnow(),
                )
            )

    def get_session_summary(self, session_id):
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.summaries.c.content)
                .where(self.summaries.c.session_id == session_id)
                .order_by(self.summaries.c.created_at.desc())
                .limit(1)
            ).fetchone()
            return row.content if row else ""

    def should_generate_summary(self, session_id, threshold=20):
        """
        Check if a summary should be generated for this session.
        Returns True if:
        - Session has more than threshold turns AND
        - No summary exists OR summary is outdated (older than 10 turns)
        """
        with self.engine.begin() as conn:
            # Count total turns
            turn_count = conn.execute(
                select(func.count())
                .select_from(self.turns)
                .where(self.turns.c.session_id == session_id)
            ).scalar()

            if turn_count < threshold:
                return False

            # Check if summary exists
            summary_row = conn.execute(
                select(self.summaries.c.created_at)
                .where(self.summaries.c.session_id == session_id)
                .order_by(self.summaries.c.created_at.desc())
                .limit(1)
            ).fetchone()

            if not summary_row:
                return True

            # Count turns since last summary
            turns_since_summary = conn.execute(
                select(func.count())
                .select_from(self.turns)
                .where(
                    and_(
                        self.turns.c.session_id == session_id,
                        self.turns.c.created_at > summary_row.created_at
                    )
                )
            ).scalar()

            # Generate new summary if 10+ new turns
            return turns_since_summary >= 10

    def generate_auto_summary(self, session_id, provider_call):
        """
        Generate an automatic summary of the conversation.

        Args:
            session_id: The session to summarize
            provider_call: A callable that takes (messages) and returns response text
                          e.g., lambda msgs: provider.chat(msgs)["text"]

        Returns:
            The generated summary text, or None if generation failed
        """
        # Get all turns for this session
        turns = self.get_recent_turns(session_id, limit=10000)

        if len(turns) < 5:
            return None  # Not enough content to summarize

        # Build a prompt to summarize the conversation
        summary_messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversations concisely. "
                          "Capture the key topics, decisions, and important information. "
                          "Keep it to 3-5 sentences."
            }
        ]

        # Add conversation turns
        conversation_text = []
        for turn in turns:
            role_label = "User" if turn["role"] == "user" else "Assistant"
            conversation_text.append(f"{role_label}: {turn['content']}")

        summary_messages.append({
            "role": "user",
            "content": f"Please summarize this conversation:\n\n" + "\n\n".join(conversation_text[:100])  # Limit to first 100 turns
        })

        try:
            summary = provider_call(summary_messages)
            if summary:
                self.save_session_summary(session_id, summary)
                logging.info(f"[MEMORY] Auto-generated summary for session {session_id}")
                return summary
        except Exception as e:
            logging.error(f"[MEMORY] Failed to generate summary: {e}")
            return None

    # =============================
    # Conversation turns API
    # =============================
    def save_turn(self, session_id, role, content, created_at=None, provider_id=None, model=None, intent=None, metadata=None):
        import json
        logging.info(f"[MEMORY] save_turn() called: session={session_id}, role={role}, has_metadata={metadata is not None}")
        self._ensure_session(session_id)

        # Set session title from first user message (once)
        if role == "user":
            with self.engine.begin() as conn:
                row = conn.execute(
                    select(self.sessions.c.title)
                    .where(self.sessions.c.id == session_id)
                ).fetchone()

                if row and not row.title:
                    title = content.strip().splitlines()[0][:60]
                    self.save_session_title(session_id, title)

        # Serialize metadata to JSON if it's a dict
        metadata_json = None
        if metadata:
            try:
                metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else metadata
                logging.info(f"[MEMORY] Serialized metadata to JSON, length={len(metadata_json)}")
            except (TypeError, ValueError) as e:
                logging.error(f"[MEMORY] Failed to serialize metadata to JSON: {e}")
                logging.error(f"[MEMORY] Metadata content: {metadata}")
                metadata_json = None

        now = created_at or datetime.utcnow()
        with self.engine.begin() as conn:
            logging.info(f"[MEMORY] Inserting turn into database...")
            conn.execute(
                insert(self.turns).values(
                    session_id=session_id,
                    role=role,
                    content=content,
                    created_at=now,
                    provider_id=provider_id,
                    model=model,
                    intent=intent,
                    metadata=metadata_json,
                )
            )
            logging.info(f"[MEMORY] Turn inserted successfully")
            conn.execute(
                update(self.sessions)
                .where(self.sessions.c.id == session_id)
                .values(updated_at=now)
            )

    def get_recent_turns(self, session_id, limit=6):
        import json
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.turns.c.role,
                    self.turns.c.content,
                    self.turns.c.created_at,
                    self.turns.c.provider_id,
                    self.turns.c.model,
                    self.turns.c.intent,
                    self.turns.c.metadata,
                )
                .where(self.turns.c.session_id == session_id)
                .order_by(self.turns.c.created_at.desc())
                .limit(limit)
            ).fetchall()

            # Reverse so oldest → newest
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "created_at": r.created_at,
                    "provider_id": r.provider_id,
                    "model": r.model,
                    "intent": r.intent,
                    "metadata": json.loads(r.metadata) if r.metadata else None,
                }
                for r in reversed(rows)
            ]

    def build_context(self, session_id, system_prompt, limit=12):
        """
        Build deterministic context for model invocation.
        Order:
        1. system prompt
        2. session summary (if exists)
        3. most recent conversation turns (bounded)
        """
        messages = []

        # Always include system prompt
        messages.append({
            "role": "system",
            "content": system_prompt,
        })

        # Optional long-term summary
        summary = self.get_session_summary(session_id)
        if summary:
            messages.append({
                "role": "system",
                "content": f"Conversation summary so far:\n{summary}",
            })

        # Recent turns with timestamps for temporal context
        turns = self.get_recent_turns(session_id, limit=limit)
        for t in turns:
            content = t["content"]

            # Add timestamp context if available
            if t.get("created_at"):
                from datetime import datetime
                created_at = t["created_at"]
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at)

                time_str = created_at.strftime("%Y-%m-%d %H:%M UTC")
                content = f"[{time_str}] {content}"

            messages.append({
                "role": t["role"],
                "content": content,
            })

        return messages

    # =============================
    # Providers API
    # =============================
    def list_providers(self):
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.providers)).fetchall()
            return [dict(row._mapping) for row in rows]

    def get_provider(self, provider_id):
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.providers)
                .where(self.providers.c.id == provider_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def upsert_provider(self, provider):
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(self.providers.c.id)
                .where(self.providers.c.id == provider["id"])
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.providers)
                    .where(self.providers.c.id == provider["id"])
                    .values(
                        name=provider["name"],
                        type=provider["type"],
                        base_url=provider.get("base_url"),
                        model=provider.get("model"),
                        api_key=provider.get("api_key"),
                        enabled=provider.get("enabled", True),
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    insert(self.providers).values(
                        id=provider["id"],
                        name=provider["name"],
                        type=provider["type"],
                        base_url=provider.get("base_url"),
                        model=provider.get("model"),
                        api_key=provider.get("api_key"),
                        enabled=provider.get("enabled", True),
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def delete_provider(self, provider_id):
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.providers)
                .where(self.providers.c.id == provider_id)
            )

    # =============================
    # Step 3: Provider Intelligence API
    # =============================
    def init_provider_metadata(self, provider_id, cost_per_1k_input=0, cost_per_1k_output=0):
        """
        Initialize provider metadata with cost data.
        Costs in micro-dollars (1/1,000,000 of $1).
        """
        with self.engine.begin() as conn:
            existing = conn.execute(
                select(self.provider_metadata.c.provider_id)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()

            if not existing:
                conn.execute(
                    insert(self.provider_metadata).values(
                        provider_id=provider_id,
                        cost_per_1k_input_tokens=cost_per_1k_input,
                        cost_per_1k_output_tokens=cost_per_1k_output,
                        avg_latency_ms=0,
                        total_requests=0,
                        failed_requests=0,
                        health_status="unknown",
                        circuit_breaker_open=False,
                        updated_at=datetime.utcnow(),
                    )
                )

    def get_provider_metadata(self, provider_id):
        """Get metadata for a specific provider."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_all_provider_metadata(self):
        """Get metadata for all providers."""
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.provider_metadata)).fetchall()
            return {row.provider_id: dict(row._mapping) for row in rows}

    def log_request(self, session_id, provider_id, intent, success, latency_ms,
                   input_tokens=0, output_tokens=0, estimated_cost=0, error_message=None):
        """
        Log a provider request for analytics and health tracking.
        """
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.request_logs).values(
                    session_id=session_id,
                    provider_id=provider_id,
                    intent=intent,
                    success=success,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    error_message=error_message,
                    created_at=datetime.utcnow(),
                )
            )

    def update_provider_health(self, provider_id, success, latency_ms=None):
        """
        Update provider health metrics based on request outcome.
        """
        with self.engine.begin() as conn:
            # Get current metadata
            metadata = conn.execute(
                select(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            ).fetchone()

            if not metadata:
                # Initialize if doesn't exist
                self.init_provider_metadata(provider_id)
                metadata = conn.execute(
                    select(self.provider_metadata)
                    .where(self.provider_metadata.c.provider_id == provider_id)
                ).fetchone()

            now = datetime.utcnow()
            total = metadata.total_requests + 1
            failed = metadata.failed_requests + (0 if success else 1)

            # Calculate rolling average latency
            if latency_ms and success:
                current_avg = metadata.avg_latency_ms or 0
                current_count = metadata.total_requests
                new_avg = ((current_avg * current_count) + latency_ms) / total
            else:
                new_avg = metadata.avg_latency_ms

            # Determine health status
            failure_rate = failed / total if total > 0 else 0

            if total < 5:
                health_status = "unknown"
            elif failure_rate > 0.5:
                health_status = "unhealthy"
            elif failure_rate > 0.2:
                health_status = "degraded"
            else:
                health_status = "healthy"

            # Circuit breaker logic: open if 5+ consecutive failures
            recent_failures = conn.execute(
                select(func.count(self.request_logs.c.id))
                .where(self.request_logs.c.provider_id == provider_id)
                .where(self.request_logs.c.success == False)
                .order_by(self.request_logs.c.created_at.desc())
                .limit(5)
            ).scalar()

            circuit_breaker_open = recent_failures >= 5

            conn.execute(
                update(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
                .values(
                    total_requests=total,
                    failed_requests=failed,
                    avg_latency_ms=int(new_avg),
                    last_success_at=now if success else metadata.last_success_at,
                    last_failure_at=now if not success else metadata.last_failure_at,
                    health_status=health_status,
                    circuit_breaker_open=circuit_breaker_open,
                    updated_at=now,
                )
            )

    def get_provider_health_summary(self):
        """
        Get health summary for all providers.
        """
        with self.engine.begin() as conn:
            rows = conn.execute(select(self.provider_metadata)).fetchall()

            summary = {}
            for row in rows:
                failure_rate = row.failed_requests / row.total_requests if row.total_requests > 0 else 0
                summary[row.provider_id] = {
                    "health_status": row.health_status,
                    "circuit_breaker_open": row.circuit_breaker_open,
                    "total_requests": row.total_requests,
                    "failure_rate": round(failure_rate * 100, 2),
                    "avg_latency_ms": row.avg_latency_ms,
                    "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
                    "last_failure_at": row.last_failure_at.isoformat() if row.last_failure_at else None,
                }

            return summary

    def estimate_cost(self, provider_id, input_tokens, output_tokens):
        """
        Estimate cost for a request in micro-dollars.
        """
        metadata = self.get_provider_metadata(provider_id)
        if not metadata:
            return 0

        input_cost = (input_tokens / 1000) * metadata["cost_per_1k_input_tokens"]
        output_cost = (output_tokens / 1000) * metadata["cost_per_1k_output_tokens"]

        return int(input_cost + output_cost)

    def delete_provider_metadata(self, provider_id):
        """
        Delete provider metadata and request logs when provider is removed.
        """
        with self.engine.begin() as conn:
            # Delete metadata
            conn.execute(
                delete(self.provider_metadata)
                .where(self.provider_metadata.c.provider_id == provider_id)
            )

            # Delete request logs
            conn.execute(
                delete(self.request_logs)
                .where(self.request_logs.c.provider_id == provider_id)
            )
    def set_last_provider(self, session_id, provider_id):
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.session_providers)
                .where(self.session_providers.c.session_id == session_id)
            )
            conn.execute(
                insert(self.session_providers).values(
                    session_id=session_id,
                    provider_id=provider_id,
                    updated_at=datetime.utcnow(),
                )
            )

    def get_last_provider(self, session_id):
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.session_providers.c.provider_id)
                .where(self.session_providers.c.session_id == session_id)
            ).fetchone()
            return row.provider_id if row else None
    # =============================
    # Debug Settings API
    # =============================
    def set_debug_enabled(self, user_id, enabled: bool):
        """
        Upsert the debug enabled flag for a user.
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.debug_settings)
                .where(self.debug_settings.c.user_id == user_id)
            )
            conn.execute(
                insert(self.debug_settings).values(
                    user_id=user_id,
                    enabled=enabled,
                    updated_at=datetime.utcnow(),
                )
            )

    def is_debug_enabled(self, user_id) -> bool:
        """
        Return True if debug logging is enabled for the given user_id.
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.debug_settings.c.enabled)
                .where(self.debug_settings.c.user_id == user_id)
            ).fetchone()
            return bool(row.enabled) if row and row.enabled else False

    # =============================
    # Authentication API
    # =============================
    def create_user(self, username, password_hash, is_admin=False):
        """Create a new user."""
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.users).values(
                    username=username,
                    password_hash=password_hash,
                    is_admin=is_admin,
                    is_enabled=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

    def get_user_by_username(self, username):
        """Get user by username."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.users)
                .where(self.users.c.username == username)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_user_by_id(self, user_id):
        """Get user by ID."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.users)
                .where(self.users.c.id == user_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def update_user_password(self, user_id, password_hash):
        """Update user password."""
        with self.engine.begin() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(
                    password_hash=password_hash,
                    updated_at=datetime.utcnow(),
                )
            )

    def disable_user(self, user_id):
        """Disable a user account."""
        with self.engine.begin() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(
                    is_enabled=False,
                    updated_at=datetime.utcnow(),
                )
            )

    def create_auth_session(self, session_id, user_id, expires_at):
        """Create an authentication session."""
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.auth_sessions).values(
                    id=session_id,
                    user_id=user_id,
                    created_at=datetime.utcnow(),
                    expires_at=expires_at,
                )
            )

    def get_auth_session(self, session_id):
        """Get authentication session."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.auth_sessions)
                .where(self.auth_sessions.c.id == session_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def delete_auth_session(self, session_id):
        """Delete authentication session (logout)."""
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.auth_sessions)
                .where(self.auth_sessions.c.id == session_id)
            )

    # =============================
    # Mode Management API
    # =============================

    def get_user_mode(self, user_id):
        """Get user's active mode."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.user_mode_config)
                .where(self.user_mode_config.c.user_id == user_id)
            ).fetchone()

            if row:
                return dict(row._mapping)

            # Create default if not exists
            conn.execute(
                insert(self.user_mode_config).values(
                    user_id=user_id,
                    active_mode="personal",
                    updated_at=datetime.utcnow(),
                )
            )
            return {"user_id": user_id, "active_mode": "personal"}

    def set_user_mode(self, user_id, mode):
        """Set user's active mode."""
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.user_mode_config)
                .where(self.user_mode_config.c.user_id == user_id)
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.user_mode_config)
                    .where(self.user_mode_config.c.user_id == user_id)
                    .values(
                        active_mode=mode,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    insert(self.user_mode_config).values(
                        user_id=user_id,
                        active_mode=mode,
                        updated_at=datetime.utcnow(),
                    )
                )

    def get_mode_settings(self, user_id, mode):
        """Get settings for a specific mode."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
                .where(self.mode_settings.c.mode == mode)
            ).fetchone()
            return dict(row._mapping) if row else None

    def create_or_update_mode_settings(self, user_id, mode, system_prompt_override=None,
                                       preferred_provider_id=None, tone=None):
        """Create or update mode settings."""
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
                .where(self.mode_settings.c.mode == mode)
            ).fetchone()

            values = {
                "updated_at": datetime.utcnow(),
            }

            if system_prompt_override is not None:
                values["system_prompt_override"] = system_prompt_override
            if preferred_provider_id is not None:
                values["preferred_provider_id"] = preferred_provider_id
            if tone is not None:
                values["tone"] = tone

            if existing:
                conn.execute(
                    update(self.mode_settings)
                    .where(self.mode_settings.c.user_id == user_id)
                    .where(self.mode_settings.c.mode == mode)
                    .values(**values)
                )
            else:
                values.update({
                    "user_id": user_id,
                    "mode": mode,
                    "created_at": datetime.utcnow(),
                })
                if "system_prompt_override" not in values:
                    values["system_prompt_override"] = None
                if "preferred_provider_id" not in values:
                    values["preferred_provider_id"] = None
                if "tone" not in values:
                    values["tone"] = "neutral"

                conn.execute(
                    insert(self.mode_settings).values(**values)
                )

    def get_all_mode_settings(self, user_id):
        """Get all mode settings for a user."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.mode_settings)
                .where(self.mode_settings.c.user_id == user_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    # =============================
    # Work Mode Sub-Tab API
    # =============================

    def get_work_subtab_config(self, user_id, subtab):
        """Get configuration for a specific work subtab."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
                .where(self.work_mode_subtab_config.c.subtab == subtab)
            ).fetchone()
            return dict(row._mapping) if row else None

    def update_work_subtab_config(self, user_id, subtab, config_json):
        """Update configuration for a specific work subtab."""
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
                .where(self.work_mode_subtab_config.c.subtab == subtab)
            ).fetchone()

            if existing:
                conn.execute(
                    update(self.work_mode_subtab_config)
                    .where(self.work_mode_subtab_config.c.user_id == user_id)
                    .where(self.work_mode_subtab_config.c.subtab == subtab)
                    .values(
                        config_json=config_json,
                        updated_at=datetime.utcnow(),
                    )
                )
            else:
                conn.execute(
                    insert(self.work_mode_subtab_config).values(
                        user_id=user_id,
                        subtab=subtab,
                        config_json=config_json,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

    def get_all_work_subtab_configs(self, user_id):
        """Get all work subtab configurations for a user."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.work_mode_subtab_config)
                .where(self.work_mode_subtab_config.c.user_id == user_id)
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    def cleanup_expired_sessions(self):
        """Remove expired authentication sessions."""
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.auth_sessions)
                .where(self.auth_sessions.c.expires_at < datetime.utcnow())
            )
    # =============================
    # Personal AI Agent: Service Providers API
    # =============================

    def store_service_provider(self, user_id, name, category, provider_type, **kwargs):
        """Store a service provider."""
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.service_providers).values(
                    user_id=user_id,
                    name=name,
                    category=category,
                    provider_type=provider_type,
                    capabilities=kwargs.get("capabilities"),
                    api_base_url=kwargs.get("api_base_url"),
                    auth_method=kwargs.get("auth_method"),
                    access_token=kwargs.get("access_token"),
                    refresh_token=kwargs.get("refresh_token"),
                    token_expires_at=kwargs.get("token_expires_at"),
                    trust_level=kwargs.get("trust_level", "manual"),
                    booking_method=kwargs.get("booking_method"),
                    preferred_for_category=kwargs.get("preferred_for_category", False),
                    is_enabled=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            return result.lastrowid

    def get_service_providers(self, user_id, category=None):
        """Get service providers for a user, optionally filtered by category."""
        with self.engine.begin() as conn:
            query = select(self.service_providers).where(
                self.service_providers.c.user_id == user_id
            )

            if category:
                query = query.where(self.service_providers.c.category == category)

            rows = conn.execute(query).fetchall()
            return [dict(row._mapping) for row in rows]

    def get_service_provider(self, provider_id):
        """Get a single service provider by ID."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.service_providers).where(
                    self.service_providers.c.id == provider_id
                )
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_preferred_provider(self, user_id, category):
        """
        Get the preferred provider for a category.
        Falls back to any provider in that category if no preferred one exists.
        """
        with self.engine.begin() as conn:
            # First, try to get a preferred provider
            row = conn.execute(
                select(self.service_providers)
                .where(self.service_providers.c.user_id == user_id)
                .where(self.service_providers.c.category == category)
                .where(self.service_providers.c.preferred_for_category == True)
                .limit(1)
            ).fetchone()

            if row:
                return dict(row._mapping)

            # Fall back to any provider in this category
            row = conn.execute(
                select(self.service_providers)
                .where(self.service_providers.c.user_id == user_id)
                .where(self.service_providers.c.category == category)
                .limit(1)
            ).fetchone()

            return dict(row._mapping) if row else None

    def update_service_provider(self, provider_id, **kwargs):
        """Update a service provider."""
        with self.engine.begin() as conn:
            update_values = {k: v for k, v in kwargs.items() if v is not None}
            update_values["updated_at"] = datetime.utcnow()

            conn.execute(
                update(self.service_providers)
                .where(self.service_providers.c.id == provider_id)
                .values(**update_values)
            )

    def delete_service_provider(self, provider_id, user_id):
        """Delete a service provider (with user ownership check)."""
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.service_providers)
                .where(self.service_providers.c.id == provider_id)
                .where(self.service_providers.c.user_id == user_id)
            )

    # =============================
    # Personal AI Agent: M365 Credentials API
    # =============================

    def store_m365_credentials(self, user_id, access_token, refresh_token,
                                expires_at, scope=None, tenant_id=None, upn=None):
        """Store M365 OAuth credentials."""
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.m365_credentials.c.id)
                .where(self.m365_credentials.c.user_id == user_id)
            ).fetchone()

            if existing:
                # Update
                conn.execute(
                    update(self.m365_credentials)
                    .where(self.m365_credentials.c.user_id == user_id)
                    .values(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        scope=scope,
                        tenant_id=tenant_id,
                        user_principal_name=upn,
                        is_valid=True,
                        last_refreshed_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Insert
                conn.execute(
                    insert(self.m365_credentials).values(
                        user_id=user_id,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        scope=scope,
                        tenant_id=tenant_id,
                        user_principal_name=upn,
                        is_valid=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )

    def get_m365_credentials(self, user_id):
        """Get M365 credentials for a user."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def invalidate_m365_credentials(self, user_id, error=None):
        """Mark M365 credentials as invalid."""
        with self.engine.begin() as conn:
            conn.execute(
                update(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
                .values(
                    is_valid=False,
                    last_error=error,
                    updated_at=datetime.utcnow()
                )
            )

    def delete_m365_credentials(self, user_id):
        """Delete M365 credentials for a user."""
        with self.engine.begin() as conn:
            from sqlalchemy import delete
            conn.execute(
                delete(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
            )

    # =============================
    # Personal AI Agent: Actions API
    # =============================

    def create_action(self, user_id, session_id, action_type, category,
                      intent_summary, service_provider_id=None, **kwargs):
        """Create a new action."""
        import json

        # Serialize action_params to JSON if it's a dict
        action_params = kwargs.get("action_params")
        if action_params and isinstance(action_params, dict):
            action_params = json.dumps(action_params)

        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.actions).values(
                    user_id=user_id,
                    session_id=session_id,
                    action_type=action_type,
                    category=category,
                    intent_summary=intent_summary,
                    service_provider_id=service_provider_id,
                    action_params=action_params,
                    planned_execution_time=kwargs.get("planned_execution_time"),
                    status=kwargs.get("status", "pending"),
                    requires_confirmation=kwargs.get("requires_confirmation", True),
                    is_reversible=kwargs.get("is_reversible", False),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            return result.lastrowid

    def get_action(self, action_id):
        """Get an action by ID."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.actions).where(self.actions.c.id == action_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_pending_actions(self, user_id):
        """Get all pending actions for a user."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.actions)
                .where(self.actions.c.user_id == user_id)
                .where(self.actions.c.status == "pending")
                .order_by(self.actions.c.created_at.desc())
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    def update_action_status(self, action_id, status, **kwargs):
        """Update action status and related fields."""
        with self.engine.begin() as conn:
            update_values = {"status": status, "updated_at": datetime.utcnow()}

            # Add timestamp based on status
            if status == "approved":
                update_values["approved_at"] = datetime.utcnow()
            elif status == "executing":
                update_values["initiated_at"] = datetime.utcnow()
            elif status == "completed":
                update_values["completed_at"] = datetime.utcnow()

            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    update_values[key] = value

            conn.execute(
                update(self.actions)
                .where(self.actions.c.id == action_id)
                .values(**update_values)
            )

    # =============================
    # Personal AI Agent: Action Confirmations API
    # =============================

    def create_confirmation(self, action_id, confirmation_message, expires_at):
        """Create a confirmation request for an action."""
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.action_confirmations).values(
                    action_id=action_id,
                    confirmation_message=confirmation_message,
                    presented_at=datetime.utcnow(),
                    expires_at=expires_at,
                    created_at=datetime.utcnow()
                )
            )
            return result.lastrowid

    def get_pending_confirmations(self, user_id):
        """Get all pending confirmations for a user."""
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.actions,
                    self.action_confirmations
                )
                .join(
                    self.action_confirmations,
                    self.actions.c.id == self.action_confirmations.c.action_id
                )
                .where(self.actions.c.user_id == user_id)
                .where(self.actions.c.status == "pending")
                .where(self.action_confirmations.c.user_response.is_(None))
            ).fetchall()

            return [dict(row._mapping) for row in rows]

    def update_confirmation_response(self, action_id, user_response, user_response_text=None):
        """Update confirmation with user response."""
        with self.engine.begin() as conn:
            conn.execute(
                update(self.action_confirmations)
                .where(self.action_confirmations.c.action_id == action_id)
                .values(
                    user_response=user_response,
                    user_response_text=user_response_text,
                    responded_at=datetime.utcnow()
                )
            )

    def get_confirmation_by_id(self, confirmation_id):
        """Get a confirmation by ID with computed status."""
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.action_confirmations)
                .where(self.action_confirmations.c.id == confirmation_id)
            ).fetchone()

            if not row:
                return None

            result = dict(row._mapping)

            # Add computed status field
            if result.get("user_response"):
                result["status"] = result["user_response"]
            elif result.get("expires_at") and result["expires_at"] < datetime.utcnow():
                result["status"] = "expired"
            else:
                result["status"] = "pending"

            return result

    def update_confirmation_status(self, confirmation_id, status, **kwargs):
        """
        Update confirmation status.

        Maps status to user_response field:
        - "approved" → user_response="approved"
        - "rejected" → user_response="rejected"
        - "expired" → user_response="expired"
        """
        with self.engine.begin() as conn:
            update_values = {"user_response": status}

            # Add responded_at if provided
            if "responded_at" in kwargs:
                update_values["responded_at"] = kwargs["responded_at"]

            conn.execute(
                update(self.action_confirmations)
                .where(self.action_confirmations.c.id == confirmation_id)
                .values(**update_values)
            )

    def get_action_by_id(self, action_id):
        """Get an action by ID (alias for get_action)."""
        return self.get_action(action_id)

    def update_turn_metadata(self, session_id: str, confirmation_id: int, approved: bool):
        """
        Update the metadata of a turn to reflect approval/rejection status.

        Args:
            session_id: Session ID
            confirmation_id: Confirmation ID to find the turn
            approved: True if approved, False if rejected
        """
        import json

        with self.engine.begin() as conn:
            # Find the turn with this confirmation_id in metadata
            rows = conn.execute(
                select(
                    self.turns.c.id,
                    self.turns.c.metadata
                )
                .where(self.turns.c.session_id == session_id)
                .where(self.turns.c.metadata.isnot(None))
            ).fetchall()

            for row in rows:
                try:
                    metadata = json.loads(row.metadata) if row.metadata else None
                    if metadata and metadata.get('confirmation_id') == confirmation_id:
                        # Update the metadata
                        metadata['approved'] = approved
                        metadata['rejected'] = not approved

                        # Update the turn
                        conn.execute(
                            update(self.turns)
                            .where(self.turns.c.id == row.id)
                            .values(metadata=json.dumps(metadata))
                        )
                        logging.info(f"[MEMORY] Updated turn metadata for confirmation {confirmation_id}: approved={approved}")
                        break
                except (json.JSONDecodeError, KeyError) as e:
                    logging.warning(f"[MEMORY] Failed to parse turn metadata: {e}")
                    continue
