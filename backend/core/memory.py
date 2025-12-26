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
    def save_turn(self, session_id, role, content, created_at=None, provider_id=None, model=None, intent=None):
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
                    provider_id=provider_id,
                    model=model,
                    intent=intent,
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
                    self.turns.c.provider_id,
                    self.turns.c.model,
                    self.turns.c.intent,
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