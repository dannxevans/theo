"""
Tests for orchestration system.

Phase 1: Tests for orchestration trigger logic
"""

import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from core.orchestration.orchestrator import Orchestrator, OrchestrationResult


@dataclass
class MockServiceSignal:
    """Mock ServiceSignal for testing."""
    service: str
    relevance: float
    reason: str


@dataclass
class MockEntities:
    """Mock ExtractedEntities for testing."""
    locations: list
    datetimes: list
    people: list
    activities: list
    items: list
    durations: list
    urls: list


@dataclass
class MockReasoningResult:
    """Mock IntentReasoningResult for testing."""
    intent: str
    confidence: float
    service_signals: list
    entities: MockEntities
    is_ambiguous: bool = False
    clarification_question: str = None
    orchestration_recommended: bool = None  # None means not provided (fallback to heuristics)
    orchestration_reason: str = None


class TestOrchestrationTrigger:
    """Test orchestration decision logic (should_orchestrate)."""

    def test_should_orchestrate_with_two_high_relevance_services(self):
        """Test: 2+ services with relevance >= 0.7 triggers orchestration."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.85, "User wants good weather"),
                MockServiceSignal("calendar", 0.75, "Need to check availability")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True
        assert result.skip_reason is None

    def test_should_orchestrate_with_complex_entities(self):
        """Test: 3+ complex entities (locations/datetimes/people) triggers orchestration."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("calendar", 0.6, "Low relevance")  # Below threshold
            ],
            entities=MockEntities(
                locations=["home", "work"],
                datetimes=["tomorrow"],
                people=["Alice"],
                activities=[], items=[], durations=[], urls=[]
            )
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        # 4 complex entities (2 locations + 1 datetime + 1 person) >= 3
        assert result.should_orchestrate is True

    def test_should_not_orchestrate_with_one_service(self):
        """Test: Single high-relevance service does NOT trigger orchestration."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.95, "User wants weather")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False
        assert result.skip_reason == "insufficient_complexity"

    def test_should_not_orchestrate_with_low_relevance_services(self):
        """Test: Services below 0.7 relevance threshold don't trigger orchestration."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.6, "Maybe weather related"),
                MockServiceSignal("calendar", 0.5, "Possibly calendar related")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False
        assert result.skip_reason == "insufficient_complexity"

    def test_should_not_orchestrate_when_ambiguous(self):
        """Test: Ambiguous queries skip orchestration (handled by clarification)."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.85, "User wants weather"),
                MockServiceSignal("calendar", 0.75, "User might need calendar")
            ],
            entities=MockEntities([], [], [], [], [], [], []),
            is_ambiguous=True,
            clarification_question="Which location did you mean?"
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False
        assert result.skip_reason == "ambiguous_query"

    def test_should_orchestrate_with_three_services(self):
        """Test: 3 high-relevance services definitely triggers orchestration."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.9, "Weather check"),
                MockServiceSignal("calendar", 0.85, "Calendar check"),
                MockServiceSignal("traffic", 0.75, "Traffic estimate")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True

    def test_threshold_values_are_configurable(self):
        """Test: Orchestrator uses configurable thresholds."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        # Verify default thresholds
        assert orchestrator.HIGH_RELEVANCE_THRESHOLD == 0.7
        assert orchestrator.MIN_HIGH_RELEVANCE_SERVICES == 2
        assert orchestrator.MIN_COMPLEX_ENTITIES == 3


class TestLLMFirstOrchestration:
    """Test LLM-first orchestration decision logic."""

    def test_llm_recommends_orchestration(self):
        """Test: LLM recommendation takes precedence over heuristics."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        # Single service, normally wouldn't trigger orchestration
        # But LLM says to orchestrate
        reasoning_result = MockReasoningResult(
            intent="create_task",
            confidence=0.85,
            service_signals=[
                MockServiceSignal("tasks", 0.9, "Create task"),
                MockServiceSignal("weather", 0.6, "Check weather")  # Below threshold
            ],
            entities=MockEntities(
                locations=[],
                datetimes=["this weekend"],
                people=[],
                activities=["grocery shopping"],
                items=[],
                durations=[],
                urls=[]
            ),
            orchestration_recommended=True,
            orchestration_reason="Weather-dependent planning requires calendar + weather coordination"
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True
        assert result.metadata["decision_method"] == "llm"
        assert result.metadata["reason"] == "Weather-dependent planning requires calendar + weather coordination"

    def test_llm_skips_orchestration(self):
        """Test: LLM says no orchestration even with multiple services."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        # Multiple high-relevance services, normally would trigger orchestration
        # But LLM says no need
        reasoning_result = MockReasoningResult(
            intent="create_task",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("tasks", 0.9, "Create task"),
                MockServiceSignal("calendar", 0.8, "Add to calendar")
            ],
            entities=MockEntities([], [], [], [], [], [], []),
            orchestration_recommended=False,
            orchestration_reason="Simple task creation, no coordination needed"
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False
        assert result.skip_reason == "llm_decision"
        assert result.metadata["decision_method"] == "llm"

    def test_fallback_to_heuristics_when_no_llm_recommendation(self):
        """Test: Falls back to heuristics if LLM doesn't provide orchestration_recommended."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        # orchestration_recommended is None (not provided by LLM)
        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.9,
            service_signals=[
                MockServiceSignal("weather", 0.85, "User wants weather"),
                MockServiceSignal("calendar", 0.75, "Check calendar")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
            # orchestration_recommended defaults to None
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True
        assert result.metadata["decision_method"] == "heuristics"

    def test_grocery_shopping_scenario_with_llm_decision(self):
        """Test: 'I need to buy groceries this weekend when the weather is nice' with LLM."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="create_task",  # Intent Reasoning might classify as task
            confidence=0.85,
            service_signals=[
                MockServiceSignal("tasks", 0.9, "Create grocery task"),
                MockServiceSignal("weather", 0.6, "Check weather conditions")
            ],
            entities=MockEntities(
                locations=[],
                datetimes=["this weekend"],
                people=[],
                activities=["grocery shopping"],
                items=["groceries"],
                durations=[],
                urls=[]
            ),
            orchestration_recommended=True,
            orchestration_reason="Conditional planning: 'when weather is nice' requires coordinating calendar availability with weather forecast"
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True, "LLM should detect conditional planning need"
        assert result.metadata["decision_method"] == "llm"
        assert "conditional planning" in result.metadata["reason"].lower() or "weather" in result.metadata["reason"].lower()


class TestOrchestrationScenarios:
    """Test real-world orchestration scenarios."""

    def test_shopping_scenario(self):
        """Test: 'I need to buy groceries this weekend when the weather is nice'"""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.92,
            service_signals=[
                MockServiceSignal("weather", 0.85, "User wants good weather"),
                MockServiceSignal("calendar", 0.75, "Need to check weekend availability")
            ],
            entities=MockEntities(
                locations=["home"],
                datetimes=["this weekend"],
                people=[],
                activities=["grocery shopping"],
                items=["groceries"],
                durations=[],
                urls=[]
            )
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is True, "Shopping scenario should trigger orchestration"

    def test_airport_travel_scenario(self):
        """Test: 'I need to get to the airport by 2pm tomorrow'"""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.94,
            service_signals=[
                MockServiceSignal("traffic", 0.95, "Route planning needed"),
                MockServiceSignal("calendar", 0.80, "Check for conflicts"),
                MockServiceSignal("weather", 0.60, "Weather might affect travel")  # Below threshold
            ],
            entities=MockEntities(
                locations=["home", "airport"],
                datetimes=["2pm tomorrow"],
                people=[],
                activities=["travel"],
                items=[],
                durations=[],
                urls=[]
            )
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        # Should trigger: 2 high-relevance services (traffic, calendar)
        # OR 3 complex entities (2 locations + 1 datetime)
        assert result.should_orchestrate is True, "Airport travel should trigger orchestration"

    def test_simple_weather_query_no_orchestration(self):
        """Test: 'What's the weather today?' - simple query, no orchestration"""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="general",
            confidence=0.95,
            service_signals=[
                MockServiceSignal("weather", 0.95, "User wants weather")
            ],
            entities=MockEntities(
                locations=[],
                datetimes=["today"],
                people=[],
                activities=[],
                items=[],
                durations=[],
                urls=[]
            )
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False, "Simple weather query should NOT trigger orchestration"
        assert result.skip_reason == "insufficient_complexity"

    def test_simple_calendar_query_no_orchestration(self):
        """Test: 'What's on my calendar?' - simple query, no orchestration"""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        reasoning_result = MockReasoningResult(
            intent="read_calendar",
            confidence=0.98,
            service_signals=[
                MockServiceSignal("calendar", 0.98, "User wants calendar")
            ],
            entities=MockEntities([], [], [], [], [], [], [])
        )

        result = orchestrator.should_orchestrate(reasoning_result)

        assert result.should_orchestrate is False, "Simple calendar query should NOT trigger orchestration"


class TestOrchestrationResult:
    """Test OrchestrationResult dataclass."""

    def test_orchestration_result_skip(self):
        """Test creating a skip result."""
        result = OrchestrationResult(
            should_orchestrate=False,
            skip_reason="test_reason"
        )

        assert result.should_orchestrate is False
        assert result.skip_reason == "test_reason"
        assert result.text is None
        assert result.confirmations is None

    def test_orchestration_result_success(self):
        """Test creating a success result."""
        result = OrchestrationResult(
            should_orchestrate=True,
            text="Test response",
            confirmations=[],
            metadata={"test": "data"}
        )

        assert result.should_orchestrate is True
        assert result.text == "Test response"
        assert result.confirmations == []
        assert result.metadata == {"test": "data"}
