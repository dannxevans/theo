"""
Session operations module.

Handles all session-related operations including:
- Session CRUD (create, read, update, delete)
- Session summaries
- Conversation turns
- Context building for LLM calls
"""

from datetime import datetime
import logging
import json
from sqlalchemy import select, delete, insert, update, func, and_

from .base import BaseMemoryOperations


class SessionOperations(BaseMemoryOperations):
    """Operations for managing user sessions and conversation history."""

    # =============================
    # Session Management
    # =============================

    def _ensure_session(self, session_id, mode="personal", user_id=None):
        """
        Ensure a session exists in the database.

        Args:
            session_id: Session identifier
            mode: Session mode ("work" or "personal")
            user_id: User ID for filtering sessions
        """
        with self._get_connection() as conn:
            exists = conn.execute(
                select(self.sessions.c.id)
                .where(self.sessions.c.id == session_id)
            ).fetchone()
            if not exists:
                # Determine classification based on mode
                classification = "OFFICIAL" if mode == "work" else None

                conn.execute(
                    insert(self.sessions).values(
                        id=session_id,
                        title=None,
                        mode=mode,
                        classification=classification,
                        user_id=user_id,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )

                # Log classification audit for work mode sessions
                if mode == "work" and user_id:
                    try:
                        classification_audit = self.tables.get("classification_audit")
                        if classification_audit is not None:
                            conn.execute(
                                insert(classification_audit).values(
                                    user_id=user_id,
                                    session_id=session_id,
                                    classification="OFFICIAL",
                                    action="create",
                                    timestamp=datetime.utcnow()
                                )
                            )
                    except Exception as e:
                        # Don't fail session creation if audit logging fails
                        logging.warning(f"Failed to log classification audit: {e}")

    def get_session_title(self, session_id):
        """
        Get the current title for a session.

        Args:
            session_id: Session identifier

        Returns:
            Session title or None if not set or session doesn't exist
        """
        with self._get_connection() as conn:
            result = conn.execute(
                select(self.sessions.c.title)
                .where(self.sessions.c.id == session_id)
            ).fetchone()
            return result.title if result else None

    def save_session_title(self, session_id, title):
        """
        Save or update a session title.

        Args:
            session_id: Session identifier
            title: Session title
        """
        self._ensure_session(session_id)
        with self._get_connection() as conn:
            conn.execute(
                update(self.sessions)
                .where(self.sessions.c.id == session_id)
                .values(
                    title=title,
                    updated_at=datetime.utcnow(),
                )
            )

    def list_sessions(self, user_id=None, mode=None):
        """
        Return all sessions with their latest summary.

        Returns sessions ordered by most recently updated (based on latest turn created_at).
        Only sessions with at least one turn are returned, limited to the most recent 50.

        Args:
            user_id: Filter sessions by user ID (None = all users)
            mode: Filter sessions by mode ("work" or "personal", None = all modes)

        Returns:
            List of session dictionaries with id, title, mode, summary, has_messages, updated_at
        """
        with self._get_connection() as conn:
            latest_turn_subq = (
                select(
                    self.turns.c.session_id,
                    func.max(self.turns.c.created_at).label("latest_turn_created_at"),
                    func.count(self.turns.c.id).label("turn_count")
                )
                .group_by(self.turns.c.session_id)
                .subquery()
            )

            query = (
                select(
                    self.sessions.c.id,
                    self.sessions.c.title,
                    self.sessions.c.mode,
                    self.sessions.c.created_at,
                    self.sessions.c.updated_at,
                    latest_turn_subq.c.turn_count,
                    latest_turn_subq.c.latest_turn_created_at,
                )
                .join(latest_turn_subq, self.sessions.c.id == latest_turn_subq.c.session_id)
            )

            # Apply filters
            if user_id is not None:
                query = query.where(self.sessions.c.user_id == user_id)
            if mode is not None:
                query = query.where(self.sessions.c.mode == mode)

            query = query.order_by(latest_turn_subq.c.latest_turn_created_at.desc()).limit(50)

            rows = conn.execute(query).fetchall()

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
                    "mode": r.mode or "personal",  # Default to personal if NULL
                    "summary": summary_row.content if summary_row else "",
                    "has_messages": r.turn_count > 0,
                    "updated_at": r.latest_turn_created_at,
                })

            return result

    def get_session_mode(self, session_id):
        """
        Get the mode for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            Session mode ("work" or "personal"), or None if session doesn't exist
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.sessions.c.mode)
                .where(self.sessions.c.id == session_id)
            ).fetchone()

            if row:
                return row.mode or "personal"  # Default to personal if NULL
            return None

    def delete_session(self, session_id):
        """
        Permanently delete a session and all associated data.

        This includes:
        - Session row
        - Summaries
        - Conversation turns

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
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
    # Session Summaries
    # =============================

    def save_session_summary(self, session_id, content):
        """
        Save a conversation summary for a session.

        Args:
            session_id: Session identifier
            content: Summary text
        """
        self._ensure_session(session_id)
        with self._get_connection() as conn:
            conn.execute(
                insert(self.summaries).values(
                    session_id=session_id,
                    content=content,
                    created_at=datetime.utcnow(),
                )
            )

    def get_session_summary(self, session_id):
        """
        Get the latest summary for a session.

        Args:
            session_id: Session identifier

        Returns:
            Summary text or None if no summary exists
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.summaries.c.content)
                .where(self.summaries.c.session_id == session_id)
                .order_by(self.summaries.c.created_at.desc())
                .limit(1)
            ).fetchone()
            return row.content if row else None

    def should_generate_summary(self, session_id, threshold=20):
        """
        Check if a summary should be generated for this session.

        Returns True if:
        - Session has more than threshold turns AND
        - No summary exists OR summary is outdated (older than 10 turns)

        Args:
            session_id: Session identifier
            threshold: Minimum number of turns before generating summary

        Returns:
            Boolean indicating if summary should be generated
        """
        with self._get_connection() as conn:
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
        Generate an automatic summary of the conversation using an LLM.

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
    # Conversation Turns
    # =============================

    def save_turn(self, session_id, role, content, created_at=None, provider_id=None, model=None, intent=None, metadata=None, mode="personal", user_id=None):
        """
        Save a conversation turn (message).

        Args:
            session_id: Session identifier
            role: Message role (user or assistant)
            content: Message content
            created_at: Optional timestamp (defaults to now)
            provider_id: Optional provider ID for assistant messages
            model: Optional model name for assistant messages
            intent: Optional detected intent
            metadata: Optional metadata dictionary
            mode: Session mode ("work" or "personal")
            user_id: User ID for session filtering
        """
        logging.info(f"[MEMORY] save_turn() called: session={session_id}, role={role}, mode={mode}, has_metadata={metadata is not None}")
        self._ensure_session(session_id, mode=mode, user_id=user_id)

        # Set session title from first user message (once)
        if role == "user":
            with self._get_connection() as conn:
                row = conn.execute(
                    select(self.sessions.c.title)
                    .where(self.sessions.c.id == session_id)
                ).fetchone()

                if row and not row.title and content.strip():
                    lines = content.strip().splitlines()
                    if lines:
                        title = lines[0][:60]
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
        with self._get_connection() as conn:
            logging.info(f"[MEMORY] Inserting turn into database...")
            result = conn.execute(
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
            turn_id = result.lastrowid
            logging.info(f"[MEMORY] Turn inserted successfully with ID {turn_id}")
            conn.execute(
                update(self.sessions)
                .where(self.sessions.c.id == session_id)
                .values(updated_at=now)
            )
            return turn_id

    def get_recent_turns(self, session_id, limit=6):
        """
        Get recent conversation turns for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of turns to return

        Returns:
            List of turn dictionaries (oldest to newest)
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(
                    self.turns.c.id,
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
                    "id": r.id,
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
        1. System prompt
        2. Session summary (if exists)
        3. Most recent conversation turns (bounded)

        Args:
            session_id: Session identifier
            system_prompt: System prompt text
            limit: Maximum number of recent turns to include

        Returns:
            List of message dictionaries for LLM context
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

    def update_turn_metadata(self, session_id, role, metadata):
        """
        Update metadata for the most recent turn matching session_id and role.

        Args:
            session_id: Session identifier
            role: Turn role to update
            metadata: New metadata dictionary
        """
        metadata_json = json.dumps(metadata) if isinstance(metadata, dict) else metadata

        with self._get_connection() as conn:
            # Get the most recent turn with matching session_id and role
            turn = conn.execute(
                select(self.turns.c.id)
                .where(self.turns.c.session_id == session_id)
                .where(self.turns.c.role == role)
                .order_by(self.turns.c.created_at.desc())
                .limit(1)
            ).fetchone()

            if turn:
                conn.execute(
                    update(self.turns)
                    .where(self.turns.c.id == turn.id)
                    .values(metadata=metadata_json)
                )
