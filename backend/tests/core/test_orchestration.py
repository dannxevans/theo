"""
Tests for orchestration system.

Phase 1: Tests for orchestration trigger logic
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
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


class TestServiceExecution:
    """Test service execution logic."""

    def test_execute_weather_service(self):
        """Test weather service execution."""
        memory = Mock()
        memory.get_all.return_value = {
            "feature_provider_openweather_api_key": "test_key_123"
        }

        orchestrator = Orchestrator(memory)

        with patch('core.weather_service.WeatherService') as mock_weather_class:
            mock_weather = Mock()
            mock_weather.get_weather.return_value = {
                "location": "London, GB",
                "temperature": 15.2,
                "description": "overcast clouds"
            }
            mock_weather_class.return_value = mock_weather

            result = orchestrator._execute_service(
                service="weather",
                method="get_forecast",
                params={"location": "London"},
                user_id=1
            )

            assert result["method"] == "get_forecast"
            assert result["data"]["location"] == "London, GB"
            mock_weather_class.assert_called_once_with("test_key_123")
            mock_weather.get_weather.assert_called_once_with("London")

    def test_execute_memory_service(self):
        """Test memory service execution."""
        memory = Mock()
        memory.get_all.return_value = [
            {"key": "home location", "value": "123 Main St"},
            {"key": "favorite food", "value": "pizza"},
            {"key": "work location", "value": "456 Office Rd"}
        ]

        orchestrator = Orchestrator(memory)

        result = orchestrator._execute_service(
            service="memory",
            method="search",
            params={"query": "location"},
            user_id=1
        )

        assert result["method"] == "search"
        assert result["data"]["query"] == "location"
        assert len(result["data"]["results"]) == 2  # home and work location
        assert any("home location" in str(r) for r in result["data"]["results"])

    def test_execute_service_with_location_alias(self):
        """Test service execution with 'home' alias resolution."""
        memory = Mock()
        memory.get_all.return_value = {
            "home location": "123 Main St, London",
            "feature_provider_here_api_key": "test_here_key"
        }

        orchestrator = Orchestrator(memory)

        with patch('core.traffic_service.TrafficService') as mock_traffic_class:
            mock_traffic = Mock()
            mock_traffic.get_traffic_estimate.return_value = {
                "distance_km": 5.2,
                "duration_minutes": 12
            }
            mock_traffic_class.return_value = mock_traffic

            result = orchestrator._execute_service(
                service="traffic",
                method="get_route",
                params={"origin": "home", "destination": "Airport"},
                user_id=1
            )

            # Verify 'home' was resolved to actual address
            mock_traffic.get_traffic_estimate.assert_called_once()
            call_args = mock_traffic.get_traffic_estimate.call_args[0]
            assert call_args[0] == "123 Main St, London"  # origin resolved
            assert call_args[1] == "Airport"  # destination unchanged

    def test_execute_service_missing_api_key(self):
        """Test service execution fails gracefully when API key missing."""
        memory = Mock()
        memory.get_feature_providers.return_value = []  # No API keys

        orchestrator = Orchestrator(memory)

        try:
            orchestrator._execute_service(
                service="weather",
                method="get_forecast",
                params={"location": "London"},
                user_id=1
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "API key not configured" in str(e)

    def test_execute_service_unknown_service(self):
        """Test execution fails for unknown service."""
        memory = Mock()
        orchestrator = Orchestrator(memory)

        try:
            orchestrator._execute_service(
                service="unknown_service",
                method="some_method",
                params={},
                user_id=1
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown service" in str(e)

    def test_execute_service_unknown_method(self):
        """Test execution fails for unknown method."""
        memory = Mock()
        memory.get_all.return_value = []
        orchestrator = Orchestrator(memory)

        try:
            orchestrator._execute_service(
                service="memory",
                method="unknown_method",
                params={},
                user_id=1
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown memory method" in str(e)

    def test_gather_context_with_service_failure(self):
        """Test that one service failure doesn't block others."""
        memory = Mock()
        memory.get_all.return_value = {
            "test": "data",
            "feature_provider_openweather_api_key": "test_key"
        }

        orchestrator = Orchestrator(memory)

        with patch('core.weather_service.WeatherService') as mock_weather_class:
            # Weather service raises exception
            mock_weather = Mock()
            mock_weather.get_weather.side_effect = Exception("API Error")
            mock_weather_class.return_value = mock_weather

            services_to_query = [
                {"service": "weather", "method": "get_forecast", "params": {"location": "London"}},
                {"service": "memory", "method": "search", "params": {"query": "test"}}
            ]

            result = orchestrator._gather_context(services_to_query, user_id=1)

            # Weather should have error
            assert "error" in result.get("weather", {})
            assert "API Error" in str(result["weather"]["error"])

            # Memory should succeed
            assert "data" in result.get("memory", {})
            assert result["memory"]["method"] == "search"

class TestPhase4ActionConfirmation:
    """Test Phase 4: Action Confirmation & Execution"""

    def test_synthesis_proposes_calendar_action(self):
        """Test LLM proposes calendar event creation with proper structure."""
        memory = Mock()
        memory.get_all.return_value = {}
        memory.get_memories.return_value = []
        orchestrator = Orchestrator(memory)

        # Mock proposed action from synthesis
        synthesis_result = {
            "response": "I can create a calendar event for your shopping trip.",
            "needs_confirmation": True,
            "proposed_actions": [
                {
                    "type": "create_calendar_event",
                    "service": "calendar",
                    "params": {
                        "subject": "Shopping at Asda",
                        "start_time": "2026-01-14T14:00:00",
                        "end_time": "2026-01-14T15:00:00",
                        "body": "Buy: milk, eggs, bread"
                    },
                    "confirmation_message": "Create calendar event 'Shopping at Asda' tomorrow at 2:00 PM?",
                    "reasoning": "User requested shopping trip"
                }
            ]
        }

        # Verify action structure
        action = synthesis_result["proposed_actions"][0]
        assert action["type"] == "create_calendar_event"
        assert "confirmation_message" in action
        assert "params" in action
        assert "subject" in action["params"]
        assert "start_time" in action["params"]

    def test_synthesis_proposes_task_action(self):
        """Test LLM proposes task creation."""
        synthesis_result = {
            "response": "I'll create a task for your reminder.",
            "needs_confirmation": True,
            "proposed_actions": [
                {
                    "type": "create_task",
                    "service": "tasks",
                    "params": {
                        "title": "Buy milk",
                        "due_date": "2026-01-14",
                        "notes": "From Asda",
                        "importance": "normal"
                    },
                    "confirmation_message": "Create task 'Buy milk' due on 2026-01-14?",
                    "reasoning": "User requested reminder"
                }
            ]
        }

        action = synthesis_result["proposed_actions"][0]
        assert action["type"] == "create_task"
        assert action["params"]["title"] == "Buy milk"
        assert "due_date" in action["params"]

    def test_confirmation_creation_with_valid_action(self):
        """Test confirmation creation with valid action proposal."""
        from core.confirmation_manager import ConfirmationManager
        from datetime import datetime, timedelta

        memory = Mock()
        
        # Mock create_action to return action_id
        memory.create_action.return_value = 1
        
        # Mock create_confirmation to return confirmation_id
        memory.create_confirmation.return_value = 123

        confirmation_manager = ConfirmationManager(memory, action_router=None)

        action = {
            "type": "create_calendar_event",
            "params": {
                "subject": "Shopping",
                "start_time": "2026-01-14T14:00:00",
                "end_time": "2026-01-14T15:00:00"
            },
            "confirmation_message": "Create calendar event 'Shopping'?"
        }

        confirmation = confirmation_manager.create_confirmation(
            user_id=1,
            session_id="test_session",
            action_type=action["type"],
            action_params=action["params"],
            confirmation_message=action["confirmation_message"],
            provider_id=None,
            expires_in_hours=24
        )

        # Verify confirmation structure
        assert confirmation["confirmation_id"] == 123
        assert confirmation["action_id"] == 1
        assert confirmation["message"] == "Create calendar event 'Shopping'?"
        assert "expires_at" in confirmation
        assert confirmation["status"] == "pending"

    def test_multiple_actions_proposed(self):
        """Test multiple actions in one response."""
        synthesis_result = {
            "response": "I'll create both a calendar event and a task.",
            "needs_confirmation": True,
            "proposed_actions": [
                {
                    "type": "create_calendar_event",
                    "service": "calendar",
                    "params": {"subject": "Meeting", "start_time": "2026-01-14T14:00:00", "end_time": "2026-01-14T15:00:00"},
                    "confirmation_message": "Create calendar event 'Meeting'?"
                },
                {
                    "type": "create_task",
                    "service": "tasks",
                    "params": {"title": "Prepare presentation", "due_date": "2026-01-14"},
                    "confirmation_message": "Create task 'Prepare presentation'?"
                }
            ]
        }

        assert len(synthesis_result["proposed_actions"]) == 2
        assert synthesis_result["proposed_actions"][0]["type"] == "create_calendar_event"
        assert synthesis_result["proposed_actions"][1]["type"] == "create_task"

    def test_action_proposal_date_validation(self):
        """Test date parameters are in correct format."""
        action = {
            "type": "create_calendar_event",
            "params": {
                "subject": "Test",
                "start_time": "2026-01-14T14:00:00",  # ISO 8601
                "end_time": "2026-01-14T15:00:00"
            }
        }

        # Verify ISO 8601 format
        assert "T" in action["params"]["start_time"]
        assert len(action["params"]["start_time"]) == 19  # YYYY-MM-DDTHH:MM:SS

        # Verify parseable
        from datetime import datetime
        parsed = datetime.fromisoformat(action["params"]["start_time"])
        assert parsed.year == 2026
        assert parsed.month == 1
        assert parsed.day == 14

    def test_informational_query_no_action(self):
        """Test informational queries don't propose actions."""
        synthesis_result = {
            "response": "Tomorrow's weather will be partly cloudy with a high of 15°C.",
            "needs_confirmation": False,
            "proposed_actions": []
        }

        assert synthesis_result["needs_confirmation"] is False
        assert len(synthesis_result["proposed_actions"]) == 0

    def test_missing_confirmation_message_handled(self):
        """Test graceful handling of missing confirmation_message."""
        from core.confirmation_manager import ConfirmationManager

        memory = Mock()
        memory.create_action.return_value = 1
        memory.create_confirmation.return_value = 123

        confirmation_manager = ConfirmationManager(memory, action_router=None)

        # Action without confirmation_message
        action = {
            "type": "create_calendar_event",
            "params": {"subject": "Test"}
        }

        # Should use default message
        confirmation = confirmation_manager.create_confirmation(
            user_id=1,
            session_id="test",
            action_type=action["type"],
            action_params=action["params"],
            confirmation_message=f"Confirm {action['type']}?",  # Default fallback
            provider_id=None
        )

        assert confirmation["confirmation_id"] == 123

    def test_confirmation_metadata_transformation(self):
        """Test confirmation metadata is transformed for frontend."""
        from datetime import datetime

        # Mock confirmation from database
        confirmation = {
            "confirmation_id": 123,
            "action_id": 1,
            "message": "Create event?",
            "expires_at": datetime(2026, 1, 14, 18, 0, 0),
            "status": "pending"
        }

        # Transform for frontend (similar to router.py logic)
        frontend_conf = {
            "confirmation_id": confirmation["confirmation_id"],
            "action_id": confirmation["action_id"],
            "confirmation_message": confirmation["message"],
            "expires_at": confirmation["expires_at"].isoformat(),
            "status": confirmation["status"],
            "approved": False,
            "rejected": False
        }

        assert frontend_conf["confirmation_id"] == 123
        assert frontend_conf["confirmation_message"] == "Create event?"
        assert "T" in frontend_conf["expires_at"]  # ISO format
        assert frontend_conf["approved"] is False
        assert frontend_conf["rejected"] is False
