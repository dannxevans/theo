"""
Tests for HereService.

Tests routing data fetching and formatting.
"""

import pytest
from unittest.mock import Mock, patch
from core.here_service import HereService


@pytest.fixture
def here_service():
    """Create a HereService instance with a test API key."""
    return HereService("test_api_key_12345")


@pytest.fixture
def mock_route_response():
    """Mock successful HERE routing API response."""
    return {
        "routes": [
            {
                "sections": [
                    {
                        "summary": {
                            "length": 1234,
                            "duration": 180
                        }
                    }
                ]
            }
        ]
    }


def test_here_service_initialization():
    """Test HereService initialization."""
    service = HereService("my_api_key")
    assert service.api_key == "my_api_key"
    assert service.BASE_URL == "https://router.hereapi.com/v8/routes"


@patch('core.here_service.requests.get')
def test_get_route_success(mock_get, here_service, mock_route_response):
    """Test successful route fetch."""
    # Mock successful API response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_route_response
    mock_get.return_value = mock_response

    # Fetch route
    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    # Verify request was made correctly
    mock_get.assert_called_once()
    call_args = mock_get.call_args
    assert call_args[0][0] == here_service.BASE_URL
    assert call_args[1]['params']['origin'] == "52.5308,13.3847"
    assert call_args[1]['params']['destination'] == "52.5264,13.3686"
    assert call_args[1]['params']['apikey'] == "test_api_key_12345"
    assert call_args[1]['params']['transportMode'] == "car"
    assert call_args[1]['params']['return'] == "summary"

    # Verify response
    assert result is not None
    assert result['origin'] == "52.5308,13.3847"
    assert result['destination'] == "52.5264,13.3686"
    assert result['transport_mode'] == "car"
    assert result['distance_meters'] == 1234
    assert result['distance_km'] == 1.23
    assert result['duration_seconds'] == 180
    assert result['duration_minutes'] == 3.0


@patch('core.here_service.requests.get')
def test_get_route_different_transport_mode(mock_get, here_service, mock_route_response):
    """Test route fetch with different transport mode."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_route_response
    mock_get.return_value = mock_response

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686", transport_mode="bicycle")

    # Verify transport mode was requested
    call_args = mock_get.call_args
    assert call_args[1]['params']['transportMode'] == "bicycle"
    assert result['transport_mode'] == "bicycle"


@patch('core.here_service.requests.get')
def test_get_route_invalid_api_key(mock_get, here_service):
    """Test route fetch with invalid API key."""
    mock_response = Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    assert result is None


@patch('core.here_service.requests.get')
def test_get_route_bad_request(mock_get, here_service):
    """Test route fetch with bad request."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_get.return_value = mock_response

    result = here_service.get_route("invalid", "coordinates")

    assert result is None


@patch('core.here_service.requests.get')
def test_get_route_timeout(mock_get, here_service):
    """Test route fetch with timeout."""
    import requests
    mock_get.side_effect = requests.exceptions.Timeout()

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    assert result is None


@patch('core.here_service.requests.get')
def test_get_route_request_exception(mock_get, here_service):
    """Test route fetch with request exception."""
    import requests
    mock_get.side_effect = requests.exceptions.RequestException("Network error")

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    assert result is None


@patch('core.here_service.requests.get')
def test_get_route_no_routes(mock_get, here_service):
    """Test route fetch with no routes in response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"routes": []}
    mock_get.return_value = mock_response

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    assert result is None


@patch('core.here_service.requests.get')
def test_get_route_malformed_response(mock_get, here_service):
    """Test route fetch with malformed response."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"incomplete": "data"}  # Missing required fields
    mock_get.return_value = mock_response

    result = here_service.get_route("52.5308,13.3847", "52.5264,13.3686")

    assert result is None


def test_format_route_response(here_service):
    """Test formatting route data."""
    route_data = {
        "origin": "52.5308,13.3847",
        "destination": "52.5264,13.3686",
        "transport_mode": "car",
        "distance_meters": 1234,
        "distance_km": 1.23,
        "duration_seconds": 180,
        "duration_minutes": 3.0
    }

    result = here_service.format_route_response(route_data)

    assert "Route (car)" in result
    assert "52.5308,13.3847" in result
    assert "52.5264,13.3686" in result
    assert "1.23 km" in result
    assert "3.0 minutes" in result


def test_format_route_response_none(here_service):
    """Test formatting None route data."""
    result = here_service.format_route_response(None)

    assert result == "Unable to fetch route information."


def test_format_route_response_empty_dict(here_service):
    """Test formatting empty route data."""
    # Empty dict is falsy, so it should return the error message
    result = here_service.format_route_response({})
    assert result == "Unable to fetch route information."
