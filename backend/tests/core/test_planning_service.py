"""
Tests for PlanningService.

Tests context-aware planning with activity analysis and enrichment.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from core.planning_service import PlanningService


class TestPlanningService:
    """Test suite for PlanningService."""

    @pytest.fixture
    def mock_memory(self):
        """Create mock MemoryStore."""
        memory = Mock()
        memory.get_all.return_value = {
            "feature_provider_openweather_api_key": "test_weather_key",
            "feature_provider_here_api_key": "test_here_key",
            "home location": "Liverpool, UK",
            "work location": "Manchester, UK"
        }
        memory.get_m365_credentials.return_value = None
        return memory

    @pytest.fixture
    def service(self, mock_memory):
        """Create PlanningService instance."""
        return PlanningService(mock_memory)

    def test_init(self, service, mock_memory):
        """Test service initialization."""
        assert service.memory == mock_memory

    # Test analyze_activity

    def test_analyze_activity_with_shopping(self, service):
        """Test activity analysis for shopping intent."""
        result = service.analyze_activity(
            user_text="I'm going shopping at Westfield tomorrow at 2pm",
            session_id="test-session",
            user_id="1"
        )

        assert result is not None
        assert result["has_planning_intent"] is True
        assert result["activity_type"] == "shopping"
        assert result["location"] == "Westfield"
        assert result["time"] is not None
        assert result["needs_weather"] is True
        assert result["needs_traffic"] is True
        assert result["needs_calendar_check"] is True

    def test_analyze_activity_with_meeting(self, service):
        """Test activity analysis for meeting intent."""
        result = service.analyze_activity(
            user_text="I have a meeting at London Bridge tomorrow",
            session_id="test-session",
            user_id="1"
        )

        assert result is not None
        assert result["activity_type"] == "meeting"
        assert result["location"] == "London Bridge"
        assert result["needs_weather"] is True

    def test_analyze_activity_with_dining(self, service):
        """Test activity analysis for dining intent."""
        result = service.analyze_activity(
            user_text="Going to dinner at Manchester tonight",
            session_id="test-session",
            user_id="1"
        )

        assert result is not None
        assert result["activity_type"] == "dining"
        assert result["location"] == "Manchester"

    def test_analyze_activity_no_planning_intent(self, service):
        """Test activity analysis with no planning keywords."""
        result = service.analyze_activity(
            user_text="What's the weather like?",
            session_id="test-session",
            user_id="1"
        )

        assert result is None

    def test_analyze_activity_planning_keywords_but_no_details(self, service):
        """Test activity analysis with planning keywords but no location/time."""
        result = service.analyze_activity(
            user_text="I'm going somewhere",
            session_id="test-session",
            user_id="1"
        )

        assert result is None

    # Test _extract_location

    def test_extract_location_with_at(self, service):
        """Test location extraction with 'at' preposition."""
        location = service._extract_location("I'm going shopping at Westfield London")
        assert location == "Westfield London"

    def test_extract_location_with_to(self, service):
        """Test location extraction with 'to' preposition."""
        location = service._extract_location("I'm heading to Manchester City Center")
        assert location == "Manchester City Center"

    def test_extract_location_with_in(self, service):
        """Test location extraction with 'in' preposition."""
        location = service._extract_location("Meeting in Birmingham")
        assert location == "Birmingham"

    def test_extract_location_no_match(self, service):
        """Test location extraction with no valid location."""
        location = service._extract_location("I'm going tomorrow")
        assert location is None

    def test_extract_location_filters_time_words(self, service):
        """Test that time words are filtered out from locations."""
        location = service._extract_location("Meeting at tomorrow")
        assert location is None

    # Test _extract_time

    def test_extract_time_tomorrow(self, service):
        """Test time extraction for 'tomorrow'."""
        time_str = service._extract_time("I'm going shopping tomorrow")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        tomorrow = datetime.utcnow() + timedelta(days=1)
        assert time_obj.date() == tomorrow.date()

    def test_extract_time_tomorrow_with_hour(self, service):
        """Test time extraction for 'tomorrow at 2pm'."""
        time_str = service._extract_time("I'm going shopping tomorrow at 2pm")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        assert time_obj.hour == 14

    def test_extract_time_tonight(self, service):
        """Test time extraction for 'tonight'."""
        time_str = service._extract_time("Going to dinner tonight")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        assert time_obj.hour == 19

    def test_extract_time_afternoon(self, service):
        """Test time extraction for 'this afternoon'."""
        time_str = service._extract_time("Meeting this afternoon")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        assert time_obj.hour == 14

    def test_extract_time_today(self, service):
        """Test time extraction for 'today'."""
        time_str = service._extract_time("Going shopping today")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        # Should be approximately current time + 1 hour
        now = datetime.utcnow()
        assert time_obj.date() == now.date()
        # Should be within the next few hours
        assert time_obj.hour >= now.hour

    def test_extract_time_specific_time_pm(self, service):
        """Test time extraction for specific time with PM."""
        time_str = service._extract_time("Meeting at 3pm")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        assert time_obj.hour == 15

    def test_extract_time_specific_time_am(self, service):
        """Test time extraction for specific time with AM."""
        time_str = service._extract_time("Meeting at 9am")
        assert time_str is not None

        time_obj = datetime.fromisoformat(time_str)
        assert time_obj.hour == 9

    def test_extract_time_no_match(self, service):
        """Test time extraction with no time indicators."""
        time_str = service._extract_time("I'm going shopping")
        assert time_str is None

    # Test _extract_activity_type

    def test_extract_activity_type_shopping(self, service):
        """Test activity type extraction for shopping."""
        activity = service._extract_activity_type("Going shopping at the mall")
        assert activity == "shopping"

    def test_extract_activity_type_meeting(self, service):
        """Test activity type extraction for meeting."""
        activity = service._extract_activity_type("I have a meeting tomorrow")
        assert activity == "meeting"

    def test_extract_activity_type_dining(self, service):
        """Test activity type extraction for dining."""
        activity = service._extract_activity_type("Going to dinner tonight")
        assert activity == "dining"

    def test_extract_activity_type_travel(self, service):
        """Test activity type extraction for travel."""
        activity = service._extract_activity_type("Taking a flight tomorrow")
        assert activity == "travel"

    def test_extract_activity_type_event(self, service):
        """Test activity type extraction for event."""
        activity = service._extract_activity_type("Going to a concert tonight")
        assert activity == "event"

    def test_extract_activity_type_generic(self, service):
        """Test activity type extraction with no specific keywords."""
        activity = service._extract_activity_type("Going somewhere tomorrow")
        assert activity == "activity"

    # Test get_context_for_activity

    @patch('core.planning_service.WeatherService')
    @patch('core.planning_service.TrafficService')
    def test_get_context_for_activity_full_context(
        self, mock_traffic_service_class, mock_weather_service_class, service
    ):
        """Test getting full context with weather and traffic."""
        # Mock weather service
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 15,
            "description": "cloudy",
            "humidity": 70
        }
        mock_weather_service_class.return_value = mock_weather

        # Mock traffic service
        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {
            "duration_minutes": 30,
            "traffic_delay_minutes": 5
        }
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "has_planning_intent": True,
            "activity_type": "shopping",
            "location": "Westfield",
            "time": datetime.utcnow().isoformat(),
            "needs_weather": True,
            "needs_traffic": True,
            "needs_calendar_check": False
        }

        result = service.get_context_for_activity(activity_data, "1")

        assert result["weather"] is not None
        assert result["weather"]["temperature"] == 15
        assert result["traffic"] is not None
        assert result["traffic"]["duration_minutes"] == 30
        # No recommendation for traffic delay of 5 minutes (threshold is > 10)
        assert len(result["recommendations"]) == 0

    @patch('core.planning_service.WeatherService')
    def test_get_context_for_activity_rain_recommendation(
        self, mock_weather_service_class, service
    ):
        """Test rain recommendation generation."""
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 12,
            "description": "light rain",
            "humidity": 85
        }
        mock_weather_service_class.return_value = mock_weather

        activity_data = {
            "has_planning_intent": True,
            "activity_type": "shopping",
            "location": "Westfield",
            "time": None,
            "needs_weather": True,
            "needs_traffic": False,
            "needs_calendar_check": False
        }

        result = service.get_context_for_activity(activity_data, "1")

        assert any("umbrella" in rec.lower() for rec in result["recommendations"])

    @patch('core.planning_service.WeatherService')
    def test_get_context_for_activity_cold_weather_recommendation(
        self, mock_weather_service_class, service
    ):
        """Test cold weather recommendation generation."""
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 2,
            "description": "clear",
            "humidity": 60
        }
        mock_weather_service_class.return_value = mock_weather

        activity_data = {
            "has_planning_intent": True,
            "activity_type": "shopping",
            "location": "Westfield",
            "time": None,
            "needs_weather": True,
            "needs_traffic": False,
            "needs_calendar_check": False
        }

        result = service.get_context_for_activity(activity_data, "1")

        assert any("dress warmly" in rec.lower() for rec in result["recommendations"])

    @patch('core.planning_service.WeatherService')
    @patch('core.planning_service.TrafficService')
    def test_get_context_for_activity_high_traffic_recommendation(
        self, mock_traffic_service_class, mock_weather_service_class, service
    ):
        """Test high traffic delay recommendation."""
        # Mock weather service
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 15,
            "description": "clear"
        }
        mock_weather_service_class.return_value = mock_weather

        # Mock traffic service with high delay
        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {
            "duration_minutes": 45,
            "traffic_delay_minutes": 15
        }
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "has_planning_intent": True,
            "activity_type": "meeting",
            "location": "Manchester",
            "time": datetime.utcnow().isoformat(),
            "needs_weather": True,
            "needs_traffic": True,
            "needs_calendar_check": False
        }

        result = service.get_context_for_activity(activity_data, "1")

        assert any("heavy traffic" in rec.lower() for rec in result["recommendations"])
        assert any("15 minutes" in rec for rec in result["recommendations"])

    # Test _fetch_weather

    @patch('core.planning_service.WeatherService')
    def test_fetch_weather_success(self, mock_weather_service_class, service):
        """Test successful weather fetching."""
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 18,
            "description": "sunny"
        }
        mock_weather_service_class.return_value = mock_weather

        result = service._fetch_weather("London", "1")

        assert result is not None
        assert result["temperature"] == 18
        assert result["description"] == "sunny"

    @patch('core.planning_service.WeatherService')
    def test_fetch_weather_no_api_key(self, mock_weather_service_class, service, mock_memory):
        """Test weather fetching with no API key configured."""
        mock_memory.get_all.return_value = {}

        result = service._fetch_weather("London", "1")

        assert result is None

    @patch('core.planning_service.WeatherService')
    def test_fetch_weather_api_error(self, mock_weather_service_class, service):
        """Test weather fetching with API error."""
        mock_weather = MagicMock()
        mock_weather.get_weather.side_effect = Exception("API Error")
        mock_weather_service_class.return_value = mock_weather

        result = service._fetch_weather("London", "1")

        assert result is None

    # Test _fetch_traffic

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_success(self, mock_traffic_service_class, service):
        """Test successful traffic fetching."""
        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {
            "duration_minutes": 25,
            "traffic_delay_minutes": 3
        }
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "location": "Manchester",
            "time": datetime.utcnow().isoformat()
        }

        result = service._fetch_traffic(activity_data, "1")

        assert result is not None
        assert result["duration_minutes"] == 25
        assert result["traffic_delay_minutes"] == 3

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_uses_home_location(self, mock_traffic_service_class, service):
        """Test traffic fetching uses home location as origin."""
        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {}
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "location": "Manchester",
            "time": None
        }

        service._fetch_traffic(activity_data, "1")

        # Verify traffic service was called with home location
        call_kwargs = mock_traffic.get_traffic_estimate.call_args[1]
        assert call_kwargs["origin"] == "Liverpool, UK"

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_uses_work_location_fallback(self, mock_traffic_service_class, service, mock_memory):
        """Test traffic fetching falls back to work location if no home location."""
        mock_memory.get_all.return_value = {
            "feature_provider_here_api_key": "test_key",
            "work location": "Manchester, UK"
        }

        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {}
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "location": "London",
            "time": None
        }

        service._fetch_traffic(activity_data, "1")

        # Verify traffic service was called with work location
        call_kwargs = mock_traffic.get_traffic_estimate.call_args[1]
        assert call_kwargs["origin"] == "Manchester, UK"

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_uses_liverpool_default(self, mock_traffic_service_class, service, mock_memory):
        """Test traffic fetching uses Liverpool default if no location set."""
        mock_memory.get_all.return_value = {
            "feature_provider_here_api_key": "test_key"
        }

        mock_traffic = MagicMock()
        mock_traffic.get_traffic_estimate.return_value = {}
        mock_traffic_service_class.return_value = mock_traffic

        activity_data = {
            "location": "London",
            "time": None
        }

        service._fetch_traffic(activity_data, "1")

        # Verify traffic service was called with Liverpool coordinates
        call_kwargs = mock_traffic.get_traffic_estimate.call_args[1]
        assert call_kwargs["origin"] == "53.4084,-2.9916"

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_no_api_key(self, mock_traffic_service_class, service, mock_memory):
        """Test traffic fetching with no API key configured."""
        mock_memory.get_all.return_value = {}

        activity_data = {
            "location": "Manchester",
            "time": None
        }

        result = service._fetch_traffic(activity_data, "1")

        assert result is None

    @patch('core.planning_service.TrafficService')
    def test_fetch_traffic_no_destination(self, mock_traffic_service_class, service):
        """Test traffic fetching with no destination."""
        activity_data = {
            "time": None
        }

        result = service._fetch_traffic(activity_data, "1")

        assert result is None

    # Test _get_weather_icon

    def test_get_weather_icon_clear(self, service):
        """Test weather icon for clear weather."""
        icon = service._get_weather_icon("clear sky")
        assert icon == "☀️"

    def test_get_weather_icon_cloudy(self, service):
        """Test weather icon for cloudy weather."""
        icon = service._get_weather_icon("partly cloudy")
        assert icon == "☁️"

    def test_get_weather_icon_rain(self, service):
        """Test weather icon for rainy weather."""
        icon = service._get_weather_icon("light rain")
        assert icon == "🌧️"

    def test_get_weather_icon_snow(self, service):
        """Test weather icon for snowy weather."""
        icon = service._get_weather_icon("snow showers")
        assert icon == "❄️"

    def test_get_weather_icon_storm(self, service):
        """Test weather icon for stormy weather."""
        icon = service._get_weather_icon("thunderstorm")
        assert icon == "⛈️"

    def test_get_weather_icon_default(self, service):
        """Test weather icon for unknown weather."""
        icon = service._get_weather_icon("unknown")
        assert icon == "🌤️"

    # Test enrich_calendar_view

    @patch('core.planning_service.WeatherService')
    def test_enrich_calendar_view(self, mock_weather_service_class, service):
        """Test calendar event enrichment with weather."""
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = {
            "temperature": 18,
            "description": "sunny"
        }
        mock_weather_service_class.return_value = mock_weather

        events = [
            {
                "id": "1",
                "subject": "Meeting",
                "start": datetime.utcnow().isoformat(),
                "location": "London"
            }
        ]

        enriched = service.enrich_calendar_view(events, "1")

        assert len(enriched) == 1
        assert enriched[0]["weather"] is not None
        assert enriched[0]["weather"]["temperature"] == 18
        assert enriched[0]["weather"]["icon"] == "☀️"

    @patch('core.planning_service.WeatherService')
    def test_enrich_calendar_view_no_location(self, mock_weather_service_class, service):
        """Test calendar enrichment with no location."""
        events = [
            {
                "id": "1",
                "subject": "Meeting",
                "start": datetime.utcnow().isoformat()
            }
        ]

        enriched = service.enrich_calendar_view(events, "1")

        assert len(enriched) == 1
        assert "weather" not in enriched[0]

    @patch('core.planning_service.WeatherService')
    def test_enrich_calendar_view_weather_api_error(self, mock_weather_service_class, service):
        """Test calendar enrichment with weather API error."""
        mock_weather = MagicMock()
        mock_weather.get_weather.return_value = None
        mock_weather_service_class.return_value = mock_weather

        events = [
            {
                "id": "1",
                "subject": "Meeting",
                "start": datetime.utcnow().isoformat(),
                "location": "London"
            }
        ]

        enriched = service.enrich_calendar_view(events, "1")

        assert len(enriched) == 1
        assert "weather" not in enriched[0]
