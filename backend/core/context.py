from datetime import datetime
import logging


class ContextManager:
    """
    Responsible for building and maintaining conversation context for THEO.

    This includes:
    - Persistent session summaries (stored via MemoryStore)
    - Rolling working set of recent turns
    - Stable system persona injected on every request
    """

    MAX_RECENT_TURNS = 3
    MAX_MESSAGE_CHARS = 12000
    SYSTEM_HEADER = "SYSTEM CONTEXT — AUTHORITATIVE"
    MAX_HISTORY_TURNS = 6
    MAX_SYSTEM_CHARS = 4000

    def __init__(self, memory):
        self.memory = memory

    # =============================
    # Context construction
    # =============================
    def build_context(self, session_id, user_text, system_prompt_override=None, subtab_context_prefix=None):
        """
        Build the context package sent to the router / provider layer.
        Step 2: Use selective memory recall instead of full dump.
        Args:
            system_prompt_override: Optional custom system prompt to replace the default
            subtab_context_prefix: Optional context prefix from work mode subtabs
        """

        session_summary = self._get_session_summary(session_id)

        # Step 2: Get relevant memories only (max 7)
        relevant_memories = self.memory.get_relevant_memories("local", user_text, max_results=7)

        # Legacy fallback for settings/preferences
        user_memory = self.memory.get_all("local")

        # Use override if provided, otherwise build default
        if system_prompt_override:
            system_prompt = system_prompt_override[:self.MAX_SYSTEM_CHARS]
        else:
            system_prompt = self._build_system_prompt(user_memory, relevant_memories)
            system_prompt = system_prompt[:self.MAX_SYSTEM_CHARS]

        # Prepend subtab context prefix if provided - this takes precedence over base system prompt
        if subtab_context_prefix:
            # Place mode context at the VERY TOP with maximum authority
            system_prompt = f"=== CURRENT MODE (HIGHEST PRIORITY) ===\n{subtab_context_prefix}\n\n{system_prompt}"
            system_prompt = system_prompt[:self.MAX_SYSTEM_CHARS]

        messages = []

        # Inject recent working turns
        recent_turns = self.memory.get_recent_turns(session_id, limit=self.MAX_HISTORY_TURNS * 2)
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

        messages = self._truncate_messages(messages)

        return {
            "system": system_prompt,
            "messages": messages,
            "task_context": {
                "goal": user_text
            },
            "memory": self.memory,
            "relevant_memories": relevant_memories  # Step 2: Pass through for debugging
        }

    def _build_system_prompt(self, user_memory, relevant_memories=None):
        # Get configurable system prompt settings
        prompt_config = self.memory.get_system_prompt_config("local")

        # Add current date/time context
        from datetime import datetime
        current_time = datetime.utcnow()
        current_date_str = current_time.strftime("%A, %B %d, %Y")
        current_time_str = current_time.strftime("%H:%M UTC")

        system_prompt = (
            f"{self.SYSTEM_HEADER}\n"
            f"CURRENT DATE AND TIME:\n"
            f"Today is {current_date_str} at {current_time_str}.\n"
            f"Use this to understand temporal context in the conversation.\n\n"
            "The following facts are persistent and authoritative across the entire conversation.\n"
            "You must recall and use them when answering direct questions.\n\n"
        )

        # Step 2: Use structured memory if available, otherwise fall back to legacy
        if relevant_memories:
            formatted_memory = "\n".join([
                f"- {mem['key']}: {mem['value']}"
                + (f" [pinned]" if mem.get('pinned') else "")
                + (f" (relevance: {mem.get('computed_relevance', 0)})" if 'computed_relevance' in mem else "")
                for mem in relevant_memories
            ])
            memory_block = (
                "PERSISTENT USER FACTS (AUTHORITATIVE):\n"
                f"{formatted_memory}\n\n"
                "If the user asks about any of these facts, you must answer directly from this list.\n"
                "Do NOT say you lack context for these facts.\n\n"
            )
        elif user_memory:
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

        # Use configurable system persona
        persona_name = prompt_config.get("persona_name", "THEO")
        tone = prompt_config.get("tone", "professional, conversational, direct")
        style_rules = prompt_config.get("style_rules", "- No em dashes\n- Be concise first, then detailed\n- Provide full working solutions when asked for code\n- Maintain a consistent persona regardless of model")
        custom_instructions = prompt_config.get("custom_instructions", "")

        system_prompt += (
            "SYSTEM PERSONA:\n"
            f"You are {persona_name}, an AI assistant.\n"
            f"Tone: {tone}.\n"
            "Rules:\n"
            f"{style_rules}\n"
        )

        if custom_instructions:
            system_prompt += f"\nADDITIONAL INSTRUCTIONS:\n{custom_instructions}\n"

        system_prompt += "\n"

        return system_prompt

    def _truncate_messages(self, messages):
        total_chars = 0
        truncated = []

        # Always preserve the most recent user message
        if not messages:
            return []

        # Start from the newest message and go backwards
        for message in reversed(messages):
            content_length = len(message.get("content", ""))
            if total_chars + content_length > self.MAX_MESSAGE_CHARS:
                # Stop adding more messages once limit exceeded
                break
            truncated.append(message)
            total_chars += content_length

        # Ensure the most recent user message is preserved if it was excluded
        most_recent_user = None
        for message in reversed(messages):
            if message["role"] == "user":
                most_recent_user = message
                break
        if most_recent_user and most_recent_user not in truncated:
            truncated.append(most_recent_user)

        # Return in original order
        truncated.reverse()
        return truncated

    # =============================
    # Context update
    # =============================
    def update(self, session_id, user_text, assistant_text, provider_registry=None, mode="personal", user_id=None):
        """
        Persist the latest turn and update the rolling session summary.

        Args:
            mode: Session mode ("work" or "personal")
            user_id: User ID for session filtering
        """
        logging.info(f"[CONTEXT] update() called for session {session_id}, mode={mode}")

        # Extract metadata from assistant response if it's a dict
        provider_id = None
        model = None
        intent = None
        metadata = None

        if isinstance(assistant_text, dict):
            provider_id = assistant_text.get("provider")
            model = assistant_text.get("model")
            intent = assistant_text.get("task_type")  # task_type is the intent
            metadata = assistant_text.get("metadata")  # Extract metadata for confirmations
            logging.info(f"[CONTEXT] Extracted metadata: {metadata}")

            if provider_id:
                self.memory.set_last_provider(session_id, provider_id)

            assistant_text = assistant_text.get("text", "")

        # Store recent turns with mode and user_id
        logging.info(f"[CONTEXT] Storing user turn")
        self._store_turn(session_id, "user", user_text, mode=mode, user_id=user_id)
        logging.info(f"[CONTEXT] Storing assistant turn with metadata: {metadata is not None}")
        self._store_turn(session_id, "assistant", assistant_text, provider_id=provider_id, model=model, intent=intent, metadata=metadata, mode=mode, user_id=user_id)
        logging.info(f"[CONTEXT] Turns stored successfully")

        # Derive and persist session title if supported by memory store
        if hasattr(self.memory, "save_session_title"):
            title = self._derive_title(session_id)
            self.memory.save_session_title(session_id, title)

        # Check if auto-summarization is needed
        if hasattr(self.memory, "should_generate_summary") and self.memory.should_generate_summary(session_id):
            logging.info(f"[CONTEXT] Auto-summarization triggered for session {session_id}")
            # Use AI to generate summary if provider_registry is available
            if provider_registry and hasattr(self.memory, "generate_auto_summary"):
                try:
                    # Get a provider to use for summarization (prefer fast ones)
                    providers = provider_registry.list()
                    enabled_providers = [p for p in providers if p.get("enabled")]

                    if enabled_providers:
                        # Create a simple provider call wrapper
                        def provider_call(messages):
                            from core.router import route_request
                            result = route_request(
                                user_message="",  # Not used, we pass messages directly
                                session_id=session_id,
                                memory=self.memory,
                                provider_registry=provider_registry,
                                intent="general",  # Use general intent for summarization
                                context={"messages": messages}  # Pass messages for summarization
                            )
                            return result.get("text", "")

                        # Generate AI-powered summary
                        self.memory.generate_auto_summary(session_id, provider_call)
                        logging.info(f"[CONTEXT] Auto-summary generated successfully")
                except Exception as e:
                    logging.error(f"[CONTEXT] Failed to auto-generate summary: {e}")
                    # Fall back to simple summary
                    new_summary = self._generate_summary(session_id)
                    self._store_session_summary(session_id, new_summary)
            else:
                # Fall back to simple heuristic summary
                new_summary = self._generate_summary(session_id)
                self._store_session_summary(session_id, new_summary)
        else:
            # Update summary using simple heuristic
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

    def _store_turn(self, session_id, role, content, provider_id=None, model=None, intent=None, metadata=None, mode="personal", user_id=None):
        self.memory.save_turn(
            session_id=session_id,
            role=role,
            content=content,
            created_at=datetime.utcnow(),
            provider_id=provider_id,
            model=model,
            intent=intent,
            metadata=metadata,
            mode=mode,
            user_id=user_id
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
            "The user is working with THEO as an AI assistant."
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