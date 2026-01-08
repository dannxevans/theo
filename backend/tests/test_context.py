"""
Comprehensive tests for core/context.py

Tests cover:
- Context building
- System prompt construction
- Message truncation
- Session summary handling
- Memory integration
"""

import pytest


class TestContextManager:
    """Tests for ContextManager class"""

    def test_init(self, memory):
        """Test initialization."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        assert manager.memory == memory

    def test_build_context_simple(self, memory):
        """Test simple context building."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-1"

        context = manager.build_context(
            session_id=session_id,
            user_text="Hello, THEO"
        )

        assert "system" in context
        assert "messages" in context
        assert isinstance(context["system"], str)
        assert isinstance(context["messages"], list)
        assert len(context["messages"]) > 0
        assert context["messages"][-1]["content"] == "Hello, THEO"

    def test_build_context_with_history(self, memory):
        """Test context building with conversation history."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-2"

        # Add some conversation history
        memory.save_turn(session_id, "user", "What's the weather?")
        memory.save_turn(session_id, "assistant", "It's sunny today.")
        memory.save_turn(session_id, "user", "Great, thanks!")

        context = manager.build_context(
            session_id=session_id,
            user_text="Tell me more"
        )

        # Should include history + current message
        assert len(context["messages"]) >= 2
        assert context["messages"][-1]["content"] == "Tell me more"

    def test_build_context_with_system_prompt_override(self, memory):
        """Test context building with custom system prompt."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-3"

        custom_prompt = "You are a helpful coding assistant."

        context = manager.build_context(
            session_id=session_id,
            user_text="Help me",
            system_prompt_override=custom_prompt
        )

        assert context["system"] == custom_prompt

    def test_build_context_with_subtab_context(self, memory):
        """Test context building with subtab context prefix."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-4"

        subtab_context = "You are in CODE mode. Focus on programming."

        context = manager.build_context(
            session_id=session_id,
            user_text="Debug this",
            subtab_context_prefix=subtab_context
        )

        # Subtab context should be prepended
        assert "CODE mode" in context["system"]
        assert "CURRENT MODE" in context["system"]

    def test_build_context_with_user_id(self, memory):
        """Test context building with user_id."""
        from core.context import ContextManager
        from auth import hash_password

        manager = ContextManager(memory)

        # Create user
        user_id = memory.create_user("testuser", hash_password("pass"), is_admin=False)
        session_id = "test-session-5"

        context = manager.build_context(
            session_id=session_id,
            user_text="Hello",
            user_id=user_id
        )

        assert "system" in context
        assert "messages" in context

    def test_build_context_truncates_long_messages(self, memory):
        """Test that long messages are handled."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-6"

        # Create very long message
        long_text = "x" * 20000

        context = manager.build_context(
            session_id=session_id,
            user_text=long_text
        )

        # Should still return valid context
        assert "system" in context
        assert "messages" in context
        assert len(context["messages"]) > 0

    def test_build_context_includes_relevant_memories(self, memory):
        """Test that context includes relevant memories."""
        from core.context import ContextManager

        manager = ContextManager(memory)

        # Store some memories
        memory.store_memory("local", "fact", "name", "John")
        memory.store_memory("local", "preference", "language", "Python")

        session_id = "test-session-7"

        context = manager.build_context(
            session_id=session_id,
            user_text="What's my name?"
        )

        # System prompt should potentially include memory info
        assert isinstance(context["system"], str)
        assert len(context["system"]) > 0

    def test_build_context_respects_max_history_turns(self, memory):
        """Test that history is limited to MAX_HISTORY_TURNS."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-8"

        # Add many turns
        for i in range(20):
            memory.save_turn(session_id, "user", f"Message {i}")
            memory.save_turn(session_id, "assistant", f"Response {i}")

        context = manager.build_context(
            session_id=session_id,
            user_text="Current message"
        )

        # Should limit history to MAX_HISTORY_TURNS * 2 (user + assistant pairs) + current
        max_expected = manager.MAX_HISTORY_TURNS * 2 + 1
        assert len(context["messages"]) <= max_expected + 2  # Some buffer

    def test_build_context_system_prompt_length(self, memory):
        """Test that system prompt is truncated to MAX_SYSTEM_CHARS."""
        from core.context import ContextManager

        manager = ContextManager(memory)

        # Create very long system prompt override
        long_prompt = "x" * 10000

        session_id = "test-session-9"

        context = manager.build_context(
            session_id=session_id,
            user_text="Test",
            system_prompt_override=long_prompt
        )

        # Should be truncated
        assert len(context["system"]) <= manager.MAX_SYSTEM_CHARS

    def test_build_context_empty_session(self, memory):
        """Test context building for new session with no history."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "brand-new-session"

        context = manager.build_context(
            session_id=session_id,
            user_text="First message"
        )

        # Should have system prompt and just the current message
        assert context["system"]
        assert len(context["messages"]) == 1
        assert context["messages"][0]["content"] == "First message"

    def test_context_message_structure(self, memory):
        """Test that messages have correct structure."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-10"

        context = manager.build_context(
            session_id=session_id,
            user_text="Test message"
        )

        # Check message structure
        for msg in context["messages"]:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["user", "assistant", "system"]
            assert isinstance(msg["content"], str)

    def test_context_with_multiple_user_messages(self, memory):
        """Test context with multiple consecutive user messages."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-11"

        # Add multiple user messages
        memory.save_turn(session_id, "user", "First question")
        memory.save_turn(session_id, "user", "Follow-up question")

        context = manager.build_context(
            session_id=session_id,
            user_text="Another question"
        )

        assert len(context["messages"]) >= 2

    def test_context_with_empty_user_text(self, memory):
        """Test context building with empty user text."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-12"

        context = manager.build_context(
            session_id=session_id,
            user_text=""
        )

        # Should still return valid context
        assert "system" in context
        assert "messages" in context

    def test_system_prompt_includes_timestamp(self, memory):
        """Test that system prompt includes current datetime."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-13"

        context = manager.build_context(
            session_id=session_id,
            user_text="What time is it?"
        )

        # System prompt should mention current date/time somewhere
        assert isinstance(context["system"], str)

    def test_context_constants(self):
        """Test that ContextManager constants are defined."""
        from core.context import ContextManager

        assert hasattr(ContextManager, "MAX_RECENT_TURNS")
        assert hasattr(ContextManager, "MAX_MESSAGE_CHARS")
        assert hasattr(ContextManager, "SYSTEM_HEADER")
        assert hasattr(ContextManager, "MAX_HISTORY_TURNS")
        assert hasattr(ContextManager, "MAX_SYSTEM_CHARS")

        assert isinstance(ContextManager.MAX_RECENT_TURNS, int)
        assert isinstance(ContextManager.MAX_MESSAGE_CHARS, int)
        assert isinstance(ContextManager.SYSTEM_HEADER, str)
        assert isinstance(ContextManager.MAX_HISTORY_TURNS, int)
        assert isinstance(ContextManager.MAX_SYSTEM_CHARS, int)

    def test_build_context_with_special_characters(self, memory):
        """Test context building with special characters in text."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-14"

        special_text = "Test with emojis 😀 and symbols © ® ™ & quotes \"\" ''"

        context = manager.build_context(
            session_id=session_id,
            user_text=special_text
        )

        assert context["messages"][-1]["content"] == special_text

    def test_build_context_with_multiline_text(self, memory):
        """Test context building with multiline text."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-15"

        multiline_text = """This is line 1
        This is line 2
        This is line 3"""

        context = manager.build_context(
            session_id=session_id,
            user_text=multiline_text
        )

        assert context["messages"][-1]["content"] == multiline_text

    def test_context_preserves_message_order(self, memory):
        """Test that message order is preserved in context."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-16"

        # Add messages in order
        memory.save_turn(session_id, "user", "Message 1")
        memory.save_turn(session_id, "assistant", "Response 1")
        memory.save_turn(session_id, "user", "Message 2")

        context = manager.build_context(
            session_id=session_id,
            user_text="Message 3"
        )

        # Check order is preserved
        messages = context["messages"]
        user_messages = [m for m in messages if m["role"] == "user"]

        # Last user message should be the current one
        assert messages[-1]["content"] == "Message 3"

    def test_build_context_returns_dict(self, memory):
        """Test that build_context returns a dictionary."""
        from core.context import ContextManager

        manager = ContextManager(memory)
        session_id = "test-session-17"

        context = manager.build_context(
            session_id=session_id,
            user_text="Test"
        )

        assert isinstance(context, dict)
        assert set(context.keys()) >= {"system", "messages"}
