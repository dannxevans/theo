from .base import LLMProvider


class MockProvider(LLMProvider):
    """
    Context-aware mock provider for THEO.

    This provider does NOT generate intelligence.
    It deterministically reflects back injected context so we can
    validate routing, session memory, and long-term memory wiring
    without external models.
    """

    name = "mock"

    def chat(self, system, messages):
        # Extract latest user message
        user_msg = messages[-1]["content"]
        lowered = user_msg.lower()

        session_summary = None
        user_memory = {}

        # Parse system messages
        for msg in messages:
            if msg["role"] != "system":
                continue

            content = msg["content"]

            # Session summary
            if content.startswith("Session summary:"):
                session_summary = content.replace("Session summary:", "").strip()

            # Long-term user memory
            if content.startswith("User memory"):
                lines = content.splitlines()[1:]
                for line in lines:
                    if ":" in line:
                        key, value = line.lstrip("- ").split(":", 1)
                        user_memory[key.strip()] = value.strip()

        # Handle long-term memory questions
        if user_memory and any(
            phrase in lowered
            for phrase in [
                "what do i prefer",
                "what style do i prefer",
                "what do you know about me",
                "my preferences",
                "my style"
            ]
        ):
            details = "\n".join(
                [f"{k}: {v}" for k, v in user_memory.items()]
            )
            return (
                "Summary: Recalling saved preferences.\n\n"
                f"Details:\n{details}"
            )

        # Handle session recall-style questions
        if session_summary and any(
            phrase in lowered
            for phrase in [
                "what was i doing",
                "what were we doing",
                "remind me",
                "earlier",
                "previously"
            ]
        ):
            return (
                "Summary: Recalling earlier context.\n\n"
                f"Details: {session_summary}"
            )

        # Default deterministic behaviour
        return (
            "Summary: Responding locally.\n\n"
            f"Details: You said '{user_msg}'. "
            "This is a mock provider response from THEO."
        )

    def stream_chat(self, system, messages):
        response = self.chat(system, messages)
        chunk_size = 30
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]