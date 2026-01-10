"""
Comprehensive tests for core/intent_reasoning.py

Tests cover:
- IntentReasoningEngine initialization
- Intent classification with confidence scoring
- Entity extraction (locations, datetimes, people, activities, items)
- Service signal generation
- Ambiguity detection and clarification
- Fallback to existing classification system
- Caching behavior
- JSON response parsing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestIntentReasoningEngine:
    """Tests for IntentReasoningEngine class"""

    def test_init(self):
        """Test initialization."""
        from core.intent_reasoning import IntentReasoningEngine

        mock_registry = Mock()
        mock_memory = Mock()

        engine = IntentReasoningEngine(
            provider_registry=mock_registry,
            memory=mock_memory,
            cache_ttl=300,
            user_id=1
        )

        assert engine.provider_registry == mock_registry
        assert engine.memory == mock_memory
        assert engine.cache_ttl == 300
        assert engine.user_id == 1
        assert engine.cache == {}
        assert engine.cache_timestamps == {}

    def test_cache_key_generation(self):
        """Test cache key generation is consistent."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        key1 = engine._cache_key("hello", "personal", "conversation")
        key2 = engine._cache_key("hello", "personal", "conversation")
        key3 = engine._cache_key("hello", "work", "conversation")

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different inputs = different key

    def test_entity_extraction_fallback(self):
        """Test fallback entity extraction using regex."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        # Test datetime extraction
        entities = engine._extract_entities_fallback("Let's meet today at 3pm")
        assert "today" in entities.datetimes
        assert "3pm" in entities.datetimes or "3 pm" in entities.datetimes

        # Test URL extraction
        entities = engine._extract_entities_fallback("Check https://example.com for info")
        assert "https://example.com" in entities.urls

    def test_service_signal_generation_fallback(self):
        """Test fallback service signal generation."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        # Test calendar signals
        signals = engine._generate_service_signals_fallback("What's on my schedule today?")
        calendar_signal = next((s for s in signals if s.service == "calendar"), None)
        assert calendar_signal is not None
        assert calendar_signal.relevance > 0

        # Test location signals
        signals = engine._generate_service_signals_fallback("Find the nearest coffee shop")
        location_signal = next((s for s in signals if s.service == "location"), None)
        assert location_signal is not None

        # Test weather signals
        signals = engine._generate_service_signals_fallback("Will it rain today?")
        weather_signal = next((s for s in signals if s.service == "weather"), None)
        assert weather_signal is not None

    def test_parse_response_valid_json(self):
        """Test parsing valid JSON response from LLM."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        json_response = json.dumps({
            "intent": "book_appointment",
            "confidence": 0.95,
            "reasoning": "User wants to schedule a meeting",
            "entities": {
                "locations": ["office"],
                "datetimes": ["tomorrow", "2pm"],
                "people": ["John"],
                "activities": ["meeting"],
                "items": []
            },
            "services": [
                {"service": "calendar", "relevance": 0.9, "reason": "Need to book time"}
            ],
            "params": {"title": "Meeting with John"},
            "ambiguous": False,
            "clarify": None
        })

        result = engine._parse_response(json_response, "Book a meeting with John tomorrow at 2pm")

        assert result.intent == "book_appointment"
        assert result.confidence == 0.95
        assert result.reasoning == "User wants to schedule a meeting"
        assert "office" in result.entities.locations
        assert "tomorrow" in result.entities.datetimes
        assert "2pm" in result.entities.datetimes
        assert "John" in result.entities.people
        assert len(result.service_signals) == 1
        assert result.service_signals[0].service == "calendar"
        assert result.is_ambiguous is False

    def test_parse_response_with_extra_text(self):
        """Test parsing JSON response with extra text around it."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        json_response = '''Sure, here's the analysis:
        {"intent": "general", "confidence": 0.8, "reasoning": "Casual greeting", "entities": {}, "services": [], "params": {}, "ambiguous": false, "clarify": null}
        Hope this helps!'''

        result = engine._parse_response(json_response, "Hello")

        assert result.intent == "general"
        assert result.confidence == 0.8

    def test_parse_response_invalid_json(self):
        """Test parsing invalid JSON returns minimal valid result."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        result = engine._parse_response("Not valid JSON at all", "Hello")

        assert result.intent == "general"
        assert result.confidence == 0.5
        assert "Parse error" in result.reasoning
        assert len(result.service_signals) == 0

    def test_fallback_classify(self):
        """Test fallback to existing classification system."""
        from core.intent_reasoning import IntentReasoningEngine

        mock_memory = Mock()
        mock_registry = Mock()

        engine = IntentReasoningEngine(mock_registry, mock_memory, user_id=1)

        with patch('core.intent_classifier.IntentClassifier') as MockClassifier:
            mock_classifier = Mock()
            mock_classifier.classify.return_value = ("general", 0.7)
            MockClassifier.return_value = mock_classifier

            result = engine._fallback_classify("Hello", "personal", "conversation", 1)

            assert result.intent == "general"
            assert result.confidence == 0.7
            assert result.source == "fallback"
            mock_classifier.classify.assert_called_once()

    def test_build_prompt(self):
        """Test prompt building."""
        from core.intent_reasoning import IntentReasoningEngine

        engine = IntentReasoningEngine(Mock(), None)

        system_prompt, user_message = engine._build_prompt("Book a meeting", "work", "calendar")

        # Check system prompt
        assert "book_appointment" in system_prompt
        assert "JSON" in system_prompt
        assert "Intents" in system_prompt or "intents" in system_prompt.lower()

        # Check user message
        assert "mode=work" in user_message
        assert "tab=calendar" in user_message
        assert "Book a meeting" in user_message

    @patch('core.router.select_provider')
    @patch('core.router.instantiate_provider')
    def test_llm_reason_success(self, mock_instantiate, mock_select):
        """Test successful LLM reasoning."""
        from core.intent_reasoning import IntentReasoningEngine

        # Mock provider selection
        mock_select.return_value = {"id": "haiku", "model": "claude-haiku"}

        # Mock provider
        mock_provider = Mock()
        json_response = json.dumps({
            "intent": "weather",
            "confidence": 0.9,
            "reasoning": "User wants weather info",
            "entities": {"locations": ["London"]},
            "services": [{"service": "weather", "relevance": 0.95, "reason": "Weather query"}],
            "params": {},
            "ambiguous": False,
            "clarify": None
        })
        mock_provider.chat.return_value = json_response
        mock_instantiate.return_value = mock_provider

        engine = IntentReasoningEngine(Mock(), Mock(), user_id=1)

        result = engine._llm_reason("What's the weather in London?", "personal", "conversation")

        assert result.intent == "weather"
        assert result.confidence == 0.9
        assert "London" in result.entities.locations
        assert len(result.service_signals) == 1
        assert result.service_signals[0].service == "weather"

    def test_caching_behavior(self):
        """Test that caching works correctly."""
        from core.intent_reasoning import IntentReasoningEngine
        from core.intent_reasoning import IntentReasoningResult, ExtractedEntities

        engine = IntentReasoningEngine(Mock(), None, cache_ttl=300)

        # Create a test result
        test_result = IntentReasoningResult(
            intent="general",
            confidence=0.8,
            reasoning="Test",
            entities=ExtractedEntities(),
            service_signals=[],
            source="reasoning"
        )

        # Cache it
        cache_key = engine._cache_key("hello", None, None)
        engine._cache_result(cache_key, test_result)

        # Retrieve it
        cached = engine._get_cached(cache_key)
        assert cached is not None
        assert cached.intent == "general"
        assert cached.confidence == 0.8

    def test_cache_expiration(self):
        """Test that cache entries expire after TTL."""
        from core.intent_reasoning import IntentReasoningEngine
        from core.intent_reasoning import IntentReasoningResult, ExtractedEntities
        import time

        engine = IntentReasoningEngine(Mock(), None, cache_ttl=1)  # 1 second TTL

        test_result = IntentReasoningResult(
            intent="general",
            confidence=0.8,
            reasoning="Test",
            entities=ExtractedEntities(),
            service_signals=[],
            source="reasoning"
        )

        cache_key = engine._cache_key("hello", None, None)
        engine._cache_result(cache_key, test_result)

        # Should be cached immediately
        assert engine._get_cached(cache_key) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired now
        assert engine._get_cached(cache_key) is None


class TestDataClasses:
    """Tests for dataclasses"""

    def test_service_signal(self):
        """Test ServiceSignal dataclass."""
        from core.intent_reasoning import ServiceSignal

        signal = ServiceSignal(
            service="calendar",
            relevance=0.9,
            reason="User mentioned schedule"
        )

        assert signal.service == "calendar"
        assert signal.relevance == 0.9
        assert signal.reason == "User mentioned schedule"

    def test_extracted_entities(self):
        """Test ExtractedEntities dataclass."""
        from core.intent_reasoning import ExtractedEntities

        entities = ExtractedEntities(
            locations=["London", "Paris"],
            datetimes=["tomorrow", "3pm"],
            people=["John", "Jane"],
            activities=["meeting"],
            items=["report"],
            durations=["1 hour"],
            urls=["https://example.com"]
        )

        assert len(entities.locations) == 2
        assert "London" in entities.locations
        assert "tomorrow" in entities.datetimes
        assert "John" in entities.people

    def test_intent_reasoning_result_to_dict(self):
        """Test IntentReasoningResult to_dict method."""
        from core.intent_reasoning import (
            IntentReasoningResult,
            ExtractedEntities,
            ServiceSignal
        )

        result = IntentReasoningResult(
            intent="general",
            confidence=0.85,
            reasoning="Test reasoning",
            entities=ExtractedEntities(locations=["London"]),
            service_signals=[
                ServiceSignal(service="calendar", relevance=0.9, reason="Test")
            ],
            parameters={"key": "value"},
            is_ambiguous=False,
            source="reasoning"
        )

        result_dict = result.to_dict()

        assert result_dict["intent"] == "general"
        assert result_dict["confidence"] == 0.85
        assert result_dict["reasoning"] == "Test reasoning"
        assert "London" in result_dict["entities"]["locations"]
        assert len(result_dict["service_signals"]) == 1
        assert result_dict["service_signals"][0]["service"] == "calendar"
        assert result_dict["parameters"]["key"] == "value"


class TestIntegration:
    """Integration tests"""

    @patch('core.router.select_provider')
    @patch('core.router.instantiate_provider')
    def test_end_to_end_reasoning(self, mock_instantiate, mock_select):
        """Test complete reasoning flow."""
        from core.intent_reasoning import IntentReasoningEngine

        # Mock provider
        mock_select.return_value = {"id": "haiku", "model": "claude-haiku"}
        mock_provider = Mock()
        json_response = json.dumps({
            "intent": "book_appointment",
            "confidence": 0.92,
            "reasoning": "User wants to schedule shopping trip",
            "entities": {
                "locations": ["Sainsburys"],
                "datetimes": ["today"],
                "activities": ["shopping"],
                "items": ["groceries"]
            },
            "services": [
                {"service": "calendar", "relevance": 0.85, "reason": "Check availability"},
                {"service": "location", "relevance": 0.9, "reason": "Find store"},
                {"service": "search", "relevance": 0.7, "reason": "Store hours"}
            ],
            "params": {},
            "ambiguous": False,
            "clarify": None
        })
        mock_provider.chat.return_value = json_response
        mock_instantiate.return_value = mock_provider

        engine = IntentReasoningEngine(Mock(), Mock(), user_id=1)

        result = engine.reason(
            text="I need to go shopping at Sainsburys today",
            mode="personal",
            subtab="conversation",
            user_id=1
        )

        assert result.intent == "book_appointment"
        assert result.confidence == 0.92
        assert "Sainsburys" in result.entities.locations
        assert "today" in result.entities.datetimes
        assert "shopping" in result.entities.activities
        assert len(result.service_signals) == 3
        assert result.latency_ms >= 0  # Can be 0 if cached

    @patch('core.router.select_provider')
    @patch('core.router.instantiate_provider')
    def test_ambiguous_request_handling(self, mock_instantiate, mock_select):
        """Test handling of ambiguous requests."""
        from core.intent_reasoning import IntentReasoningEngine

        mock_select.return_value = {"id": "haiku", "model": "claude-haiku"}
        mock_provider = Mock()
        json_response = json.dumps({
            "intent": "general",
            "confidence": 0.5,
            "reasoning": "Unclear what user wants",
            "entities": {},
            "services": [],
            "params": {},
            "ambiguous": True,
            "clarify": "Are you asking about the weather or your schedule?"
        })
        mock_provider.chat.return_value = json_response
        mock_instantiate.return_value = mock_provider

        engine = IntentReasoningEngine(Mock(), Mock(), user_id=1)

        result = engine.reason(
            text="What about tomorrow?",
            mode="personal",
            subtab="conversation",
            user_id=1
        )

        assert result.is_ambiguous is True
        assert result.clarification_question is not None
        assert "weather" in result.clarification_question or "schedule" in result.clarification_question
