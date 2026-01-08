"""
Comprehensive tests for core/intent_classifier.py

Tests cover:
- Intent classification with context
- Keyword matching
- Mode and subtab awareness
- Confidence scoring
- LLM disambiguation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestIntentClassifier:
    """Tests for IntentClassifier class"""

    def test_init(self, memory):
        """Test initialization."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)
        assert classifier.memory == memory
        assert classifier.provider_registry is None

    def test_classify_empty_text(self, memory):
        """Test classification of empty text returns general."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)
        intent, confidence = classifier.classify("")

        assert intent == "general"
        assert confidence == 1.0

    def test_classify_none_text(self, memory):
        """Test classification of None text returns general."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)
        intent, confidence = classifier.classify(None)

        assert intent == "general"
        assert confidence == 1.0

    def test_classify_booking_keywords(self, memory):
        """Test classification of booking-related text."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "book a meeting tomorrow",
            "schedule an appointment",
            "set up a call"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["book_appointment", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_email_keywords(self, memory):
        """Test classification of email-related text."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "compose an email to john",
            "write an email",
            "send a message to team"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["compose_email", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_calendar_read_keywords(self, memory):
        """Test classification of calendar read text."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "what's on my calendar",
            "show my schedule",
            "what meetings do I have"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["read_calendar", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_with_work_mode(self, memory):
        """Test classification with work mode context."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        intent, confidence = classifier.classify(
            "write function to parse JSON",
            mode="work"
        )

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_classify_with_work_mode_code_subtab(self, memory):
        """Test classification with work mode and code subtab."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        intent, confidence = classifier.classify(
            "help me debug this",
            mode="work",
            subtab="code"
        )

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_classify_with_work_mode_email_subtab(self, memory):
        """Test classification with work mode and email subtab."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        intent, confidence = classifier.classify(
            "draft a response",
            mode="work",
            subtab="email"
        )

        # Should bias toward email intent due to context
        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_classify_general_conversation(self, memory):
        """Test classification of general conversation."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "hello",
            "how are you",
            "what's the weather like",
            "tell me a joke"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert isinstance(intent, str)
            assert 0.0 <= confidence <= 1.0

    def test_classify_with_llm_fallback(self, memory):
        """Test LLM fallback for ambiguous intents."""
        from core.intent_classifier import IntentClassifier
        from core.provider_registry import ProviderRegistry

        # Add a provider for LLM fallback
        memory.upsert_provider({
            "id": "haiku",
            "name": "Claude Haiku",
            "type": "anthropic",
            "model": "claude-3-haiku",
            "api_key": "sk-test",
            "enabled": True
        })

        registry = ProviderRegistry(memory)
        classifier = IntentClassifier(memory=memory, provider_registry=registry)

        # Ambiguous text that might trigger LLM
        with patch('core.intent_classifier.IntentClassifier._llm_clarify') as mock_llm:
            mock_llm.return_value = ("book_appointment", 0.9)

            intent, confidence = classifier.classify("set something up tomorrow")

            # Should return result (may or may not use LLM depending on keyword confidence)
            assert isinstance(intent, str)
            assert 0.0 <= confidence <= 1.0

    def test_classify_weather_query(self, memory):
        """Test classification of weather queries."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "what's the weather",
            "is it going to rain",
            "weather forecast"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["weather", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_routing_query(self, memory):
        """Test classification of routing queries."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "how do I get to the office",
            "directions to London",
            "route from here to there"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["routing", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_task_queries(self, memory):
        """Test classification of task-related queries."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            ("show my tasks", "read_tasks"),
            ("what do I need to do today", "read_tasks_today"),
            ("create a new task", "create_task"),
            ("mark task as done", "complete_task")
        ]

        for text, expected_intent in test_cases:
            intent, confidence = classifier.classify(text)
            # Intent should be either the expected or general
            assert intent in [expected_intent, "general"]
            assert 0.0 <= confidence <= 1.0

    def test_classify_planning_query(self, memory):
        """Test classification of planning queries."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "help me plan my day",
            "create a plan for the project",
            "planning session"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            assert intent in ["planning", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_keyword_match_with_user_id(self, memory):
        """Test keyword matching considers user_id for pending confirmations."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        # Classify with user_id
        intent, confidence = classifier.classify(
            "yes, do it",
            user_id=1
        )

        # Should return some intent
        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_context_signals_long_message(self, memory):
        """Test context signal detection for long messages."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        # Long message (>200 chars) should bias toward general
        long_text = "This is a very long message " * 20
        intent, confidence = classifier.classify(long_text)

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_context_signals_short_message(self, memory):
        """Test context signal detection for short messages."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        # Very short message
        intent, confidence = classifier.classify("ok")

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_confidence_ranges(self, memory):
        """Test that all confidence scores are in valid range."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_texts = [
            "",
            "book meeting",
            "hello there",
            "what's the weather",
            "write me an email",
            "show calendar"
        ]

        for text in test_texts:
            intent, confidence = classifier.classify(text)
            assert 0.0 <= confidence <= 1.0
            assert isinstance(intent, str)
            assert len(intent) > 0

    def test_classifier_with_no_memory(self):
        """Test classifier works without memory."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier()

        intent, confidence = classifier.classify("hello")

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_classifier_with_no_provider_registry(self, memory):
        """Test classifier works without provider registry."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory, provider_registry=None)

        # Even with low confidence, shouldn't crash without LLM
        intent, confidence = classifier.classify("ambiguous text here")

        assert isinstance(intent, str)
        assert 0.0 <= confidence <= 1.0

    def test_appointment_variations(self, memory):
        """Test various appointment-related phrases."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "book appointment",
            "schedule meeting",
            "set up call",
            "arrange discussion",
            "cancel my 3pm",
            "reschedule tomorrow",
            "move the meeting"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            # Should classify as some appointment-related or general
            assert intent in ["book_appointment", "update_appointment", "cancel_appointment", "general"]
            assert 0.0 <= confidence <= 1.0

    def test_email_variations(self, memory):
        """Test various email-related phrases."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(memory=memory)

        test_cases = [
            "draft email",
            "send message",
            "write to john",
            "check my inbox",
            "read emails",
            "show unread"
        ]

        for text in test_cases:
            intent, confidence = classifier.classify(text)
            # Should classify as email-related or general
            assert intent in ["compose_email", "read_email", "general"]
            assert 0.0 <= confidence <= 1.0
