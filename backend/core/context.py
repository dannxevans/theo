from datetime import datetime


class ContextManager:
    """
    Responsible for building and maintaining conversation context for THEO.

    This includes:
    - Persistent session summaries (stored via MemoryStore)
    - Rolling working set of recent turns
    - Stable system persona injected on every request
    """

    MAX_RECENT_TURNS = 3

    def __init__(self, memory):
        self.memory = memory

    # =============================
    # Context construction
    # =============================
    def build_context(self, session_id, user_text):
        """
        Build the context package sent to the router / provider layer.
        """

        session_summary = self._get_session_summary(session_id)
        user_memory = self.memory.get_all("local")

        system_prompt = (
            "CRITICAL CONTEXT — MUST BE USED\n"
            "The following facts are persistent and authoritative across the entire conversation.\n"
            "You must recall and use them when answering direct questions.\n\n"
        )

        if user_memory:
            formatted_memory = "\n".join(
                [f"- {k}: {v}" for k, v in user_memory.items()]
            )
            memory_block = (
                "PERSISTENT USER FACTS (AUTHORITATIVE):\n"
                f"{formatted_memory}\n\n"
                "If the user asks about any of these facts, you must answer directly from this list.\n"
                "Do NOT say you lack context for these facts.\n\n"
            )
        else:
            memory_block = "PERSISTENT USER FACTS (AUTHORITATIVE):\n- none recorded yet.\n\nIf the user asks about any of these facts, you must answer directly from this list.\nDo NOT say you lack context for these facts.\n\n"

        system_prompt += memory_block

        system_prompt += (
            "SYSTEM PERSONA:\n"
            "You are THEO, a personal AI assistant.\n"
            "Tone: professional, conversational, direct.\n"
            "Rules:\n"
            "- No em dashes\n"
            "- Be concise first, then detailed\n"
            "- Provide full working solutions when asked for code\n"
            "- Maintain a consistent persona regardless of model\n\n"
        )

        messages = []

        # Inject recent working turns
        recent_turns = self._get_recent_turns(session_id)
        for turn in recent_turns:
            messages.append({
                "role": turn["role"],
                "content": turn["content"]
            })

        # Current user turn
        messages.append({
            "role": "user",
            "content": user_text
        })

        return {
            "system": system_prompt,
            "messages": messages,
            "task": {
                "goal": user_text
            },
            "usermemory": user_memory,
            "memory": self.memory
        }

    # =============================
    # Context update
    # =============================
    def update(self, session_id, user_text, assistant_text):
        """
        Persist the latest turn and update the rolling session summary.
        """

        # Normalise assistant output to plain text
        if isinstance(assistant_text, dict):
            if "provider" in assistant_text:
                self.memory.set_last_provider(session_id, assistant_text["provider"])
            assistant_text = assistant_text.get("text", "")

        # Store recent turns
        self._store_turn(session_id, "user", user_text)
        self._store_turn(session_id, "assistant", assistant_text)

        # Derive and persist session title if supported by memory store
        if hasattr(self.memory, "save_session_title"):
            title = self._derive_title(session_id)
            self.memory.save_session_title(session_id, title)

        # Update summary (simple heuristic for now)
        new_summary = self._generate_summary(session_id)
        self._store_session_summary(session_id, new_summary)

    # =============================
    # Internal helpers
    # =============================
    def _get_session_summary(self, session_id):
        return self.memory.get_session_summary(session_id)

    def _store_session_summary(self, session_id, summary):
        self.memory.save_session_summary(session_id, summary)

    def _get_recent_turns(self, session_id):
        return self.memory.get_recent_turns(
            session_id,
            limit=self.MAX_RECENT_TURNS * 2
        )

    def _store_turn(self, session_id, role, content):
        self.memory.save_turn(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow()
        )

    def _generate_summary(self, session_id):
        """
        Generate a rolling session summary.

        This summary is:
        - Deterministic
        - Human-readable
        - Optimised for recall across model switches
        """

        turns = self.memory.get_recent_turns(session_id, limit=12)
        if not turns:
            return ""

        user_statements = [
            t["content"].strip()
            for t in turns
            if t["role"] == "user"
        ]

        assistant_statements = [
            t["content"].strip()
            for t in turns
            if t["role"] == "assistant"
        ]

        if not user_statements:
            return ""

        summary_points = []

        # Core intent
        summary_points.append(
            "The user is working with THEO as a personal AI assistant."
        )

        # Detect explicit preferences
        for statement in user_statements:
            lowered = statement.lower()

            if "prefer" in lowered or "i like" in lowered:
                summary_points.append(
                    f"Stated preference: {statement[:120]}"
                )

        # Detect planning or goal-oriented intent
        for statement in reversed(user_statements):
            lowered = statement.lower()
            if any(
                keyword in lowered
                for keyword in [
                    "help me",
                    "plan",
                    "build",
                    "design",
                    "create",
                    "work on",
                    "project"
                ]
            ):
                summary_points.append(
                    f"Current goal: {statement[:120]}"
                )
                break

        # Add assistant progress from most recent assistant message
        if assistant_statements:
            recent_assistant = assistant_statements[-1]
            summary_points.append(
                f"Assistant progress: {recent_assistant[:120]}"
            )

        # Fallback recent focus
        if len(summary_points) == 1:
            summary_points.append(
                f"Recent focus: {user_statements[-1][:120]}"
            )

        return " ".join(summary_points)

    def _derive_title(self, session_id):
        """
        Derive a human-readable session title from the first user message.
        This is deterministic and only runs once per session.
        """
        turns = self.memory.get_recent_turns(session_id, limit=50)
        for t in turns:
            if t["role"] == "user":
                text = t["content"].strip()
                if not text:
                    return "New chat"
                # Keep it short and readable
                title = text.split("\n")[0][:60]
                return title
        return "New chat"