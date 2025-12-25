from datetime import datetime
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

    # =============================
    # Conversation turns API
    # =============================
    def save_turn(self, session_id, role, content, created_at=None):
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

        now = created_at or datetime.utcnow()
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.turns).values(
                    session_id=session_id,
                    role=role,
                    content=content,
                    created_at=now,
                )
            )
            conn.execute(
                update(self.sessions)
                .where(self.sessions.c.id == session_id)
                .values(updated_at=now)
            )

    def get_recent_turns(self, session_id, limit=6):
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.turns.c.role,
                    self.turns.c.content,
                    self.turns.c.created_at,
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

        # Recent turns (role + content only)
        turns = self.get_recent_turns(session_id, limit=limit)
        for t in turns:
            messages.append({
                "role": t["role"],
                "content": t["content"],
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