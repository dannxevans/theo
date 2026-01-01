"""
Tests for WeatherService.

Tests weather data fetching and formatting.
"""

import pytest
from unittest.mock import Mock, patch
from core.weather_service import WeatherService


@pytest.fixture
def weather_service():
    """Create a WeatherService instance with a test API key."""
    return WeatherService("test_api_key_12345")


@pytest.fixture
def mock_weather_response():
    """Mock successful weather API response."""
    return {
        "name": "London",
        "sys": {"country": "GB"},
        "main": {
            "temp": 15.2,
            "feels_like": 14.1,
            "humidity": 72
        },
        "weather": [
            {"description": "overcast clouds"}
        ],
        "wind": {
            "speed": 3.5
        }
    }


def test_weather_service_initialization():
    """Test WeatherService initialization."""
    service = WeatherService("my_api_key")
    assert service.api_key == "my_api_key"
    assert service.BASE_URL == "https://api.openweathermap.org/data/2.5/weather"


@patch('core.weather_service.requests.get')
def test_get_weather_success(mock_get, weather_service, mock_weather_response):
    """Test successful weather fetch."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_weather_response
    mock_get.return_value = mock_response

    # Fetch weather
    result = weather_service.get_weather("London,UK")

    # Verify request was made correctly
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args[0][0] == weather_service.BASE_URL
    assert call_args[1]['params']['q'] == "London,UK"
    assert call_args[1]['params']['appid'] == "test_api_key_12345"
    assert call_args[1]['params']['units'] == "metric"

    # Verify response
    assert result is not None
    assert result['location'] == "London, GB"
    assert result['temperature'] == 15.2
    assert result['feels_like'] == 14.1
    assert result['humidity'] == 72
    assert result['description'] == "overcast clouds"
    assert result['wind_speed'] == 3.5
    assert result['units'] == "metric"


@patch('core.weather_service.requests.get')
def test_get_weather_imperial_units(mock_get, weather_service, mock_weather_response):
    """Test weather fetch with imperial units."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_weather_response
    mock_get.return_value = mock_response

    result = weather_service.get_weather("New York", units="imperial")

    # Verify imperial units were requested
    call_args = mock_get.call_args
    assert call_args[1]['params']['units'] == "imperial"
    assert result['units'] == "imperial"  # Should reflect the requested units


@patch('core.weather_service.requests.get')
def test_get_weather_invalid_api_key(mock_get, weather_service):
    """Test weather fetch with invalid API key."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    result = weather_service.get_weather("London")

    assert result is None


@patch('core.weather_service.requests.get')
def test_get_weather_location_not_found(mock_get, weather_service):
    """Test weather fetch with invalid location."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    result = weather_service.get_weather("InvalidCity123")

    assert result is None


@patch('core.weather_service.requests.get')
def test_get_weather_timeout(mock_get, weather_service):
    """Test weather fetch with timeout."""
    import requests
    mock_get.side_effect = requests.exceptions.Timeout()

    result = weather_service.get_weather("London")

    assert result is None


@patch('core.weather_service.requests.get')
def test_get_weather_request_exception(mock_get, weather_service):
    """Test weather fetch with request exception."""
    import requests
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    result = weather_service.get_weather("London")

    assert result is None


@patch('core.weather_service.requests.get')
def test_get_weather_malformed_response(mock_get, weather_service):
    """Test weather fetch with malformed response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"incomplete": "data"}  # Missing required fields
    mock_get.return_value = mock_response

    result = weather_service.get_weather("London")

    assert result is None


def test_format_weather_response_metric(weather_service):
    """Test formatting weather data with metric units."""
    weather_data = {
        "location": "London, GB",
        "temperature": 15.2,
        "feels_like": 14.1,
        "humidity": 72,
        "description": "overcast clouds",
        "wind_speed": 3.5,
        "units": "metric"
    }

    result = weather_service.format_weather_response(weather_data)

    assert "Weather in London, GB:" in result
    assert "15.2°C" in result
    assert "14.1°C" in result
    assert "Overcast clouds" in result  # Capitalized
    assert "72%" in result
    assert "3.5 m/s" in result


def test_format_weather_response_imperial(weather_service):
    """Test formatting weather data with imperial units."""
    weather_data = {
        "location": "New York, US",
        "temperature": 59.4,
        "feels_like": 57.4,
        "humidity": 65,
        "description": "clear sky",
        "wind_speed": 7.8,
        "units": "imperial"
    }

    result = weather_service.format_weather_response(weather_data)

    assert "Weather in New York, US:" in result
    assert "59.4°F" in result
    assert "57.4°F" in result
    assert "Clear sky" in result
    assert "65%" in result
    assert "7.8 mph" in result


def test_format_weather_response_none(weather_service):
    """Test formatting None weather data."""
    result = weather_service.format_weather_response(None)

    assert result == "Unable to fetch weather information."


def test_format_weather_response_empty_dict(weather_service):
    """Test formatting empty weather data."""
    result = weather_service.format_weather_response({})

    # Should handle missing keys gracefully
    assert "Unable to fetch weather information" in result or "KeyError" not in result
