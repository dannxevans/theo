"""
Tests for TrafficService.

Tests HERE Routing API integration with geocoding support.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from core.traffic_service import TrafficService


class TestTrafficService:
    """Test suite for TrafficService."""

    @pytest.fixture
    def service(self):
        """Create TrafficService instance with test API key."""
        return TrafficService(api_key="test_api_key_123")

    def test_init(self, service):
        """Test service initialization."""
        assert service.api_key == "test_api_key_123"
        assert service.BASE_URL == "https://router.hereapi.com/v8/routes"
        assert service.GEOCODE_URL == "https://geocode.search.hereapi.com/v1/geocode"

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_with_coordinates(self, mock_get, service):
        """Test traffic estimate with coordinate inputs (no geocoding needed)."""
        # Mock routing API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [{
                "sections": [{
                    "summary": {
                        "length": 1234,
                        "duration": 180,
                        "baseDuration": 150
                    }
                }]
            }]
        }
        mock_get.return_value = mock_response

        result = service.get_traffic_estimate(
            origin="52.5308,13.3847",
            destination="52.5264,13.3686"
        )

        # Verify result
        assert result is not None
        assert result["origin"] == "52.5308,13.3847"
        assert result["destination"] == "52.5264,13.3686"
        assert result["transport_mode"] == "car"
        assert result["distance_km"] == 1.23  # Rounded to 2 decimal places
        assert result["duration_minutes"] == 3.0
        assert result["duration_in_traffic_minutes"] == 3.0
        assert result["traffic_delay_minutes"] == 0.5  # 30 seconds = 0.5 minutes

        # Verify only routing API was called (no geocoding)
        assert mock_get.call_count == 1
        call_url = mock_get.call_args[0][0]
        assert "router.hereapi.com" in call_url

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_with_addresses(self, mock_get, service):
        """Test traffic estimate with address inputs (requires geocoding)."""
        # Mock geocoding responses
        geocode_response_origin = MagicMock()
        geocode_response_origin.status_code = 200
        geocode_response_origin.json.return_value = {
            "items": [{
                "position": {"lat": 52.5308, "lng": 13.3847}
            }]
        }

        geocode_response_dest = MagicMock()
        geocode_response_dest.status_code = 200
        geocode_response_dest.json.return_value = {
            "items": [{
                "position": {"lat": 52.5264, "lng": 13.3686}
            }]
        }

        # Mock routing API response
        routing_response = MagicMock()
        routing_response.status_code = 200
        routing_response.json.return_value = {
            "routes": [{
                "sections": [{
                    "summary": {
                        "length": 5000,
                        "duration": 600,
                        "baseDuration": 540
                    }
                }]
            }]
        }

        # Set up mock to return different responses for geocoding and routing
        mock_get.side_effect = [
            geocode_response_origin,  # First geocode call
            geocode_response_dest,     # Second geocode call
            routing_response           # Routing call
        ]

        result = service.get_traffic_estimate(
            origin="Berlin, Germany",
            destination="Brandenburg Gate, Berlin"
        )

        # Verify result
        assert result is not None
        assert result["origin"] == "52.5308,13.3847"
        assert result["destination"] == "52.5264,13.3686"
        assert result["distance_km"] == 5.0
        assert result["duration_minutes"] == 10
        assert result["traffic_delay_minutes"] == 1

        # Verify all three API calls were made
        assert mock_get.call_count == 3

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_with_departure_time(self, mock_get, service):
        """Test traffic estimate with future departure time."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [{
                "sections": [{
                    "summary": {
                        "length": 10000,
                        "duration": 1200,
                        "baseDuration": 900
                    }
                }]
            }]
        }
        mock_get.return_value = mock_response

        departure_time = datetime(2024, 1, 15, 14, 0, 0)
        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922",
            departure_time=departure_time
        )

        # Verify departure time was included
        assert result["departure_time"] == "2024-01-15T14:00:00"

        # Verify API was called with departureTime parameter
        call_params = mock_get.call_args[1]["params"]
        assert "departureTime" in call_params
        assert call_params["departureTime"] == "2024-01-15T14:00:00"

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_with_transit_mode(self, mock_get, service):
        """Test traffic estimate with public transit mode."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [{
                "sections": [{
                    "summary": {
                        "length": 8000,
                        "duration": 900,
                        "baseDuration": 900
                    }
                }]
            }]
        }
        mock_get.return_value = mock_response

        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922",
            transport_mode="publicTransport"
        )

        # Verify transport mode in result
        assert result["transport_mode"] == "publicTransport"

        # Verify API was called with correct transport mode
        call_params = mock_get.call_args[1]["params"]
        assert call_params["transportMode"] == "publicTransport"

    @patch('core.traffic_service.requests.get')
    def test_geocode_location_success(self, mock_get, service):
        """Test successful geocoding of location."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{
                "position": {"lat": 51.5074, "lng": -0.1278}
            }]
        }
        mock_get.return_value = mock_response

        result = service._geocode_location("London, UK")

        assert result == "51.5074,-0.1278"

        # Verify geocoding API was called correctly
        call_url = mock_get.call_args[0][0]
        assert "geocode.search.hereapi.com" in call_url

        call_params = mock_get.call_args[1]["params"]
        assert call_params["q"] == "London, UK"
        assert call_params["limit"] == 1

    @patch('core.traffic_service.requests.get')
    def test_geocode_location_no_results(self, mock_get, service):
        """Test geocoding with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_get.return_value = mock_response

        result = service._geocode_location("Invalid Location XYZ123")

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_geocode_location_api_error(self, mock_get, service):
        """Test geocoding API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Unauthorized")
        mock_get.return_value = mock_response

        result = service._geocode_location("London, UK")

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_geocode_location_timeout(self, mock_get, service):
        """Test geocoding timeout handling."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = service._geocode_location("London, UK")

        assert result is None

    def test_ensure_coordinates_with_valid_coordinates(self, service):
        """Test _ensure_coordinates with already valid coordinates."""
        # No mocking needed - should return as-is
        result = service._ensure_coordinates("51.5074,-0.1278")
        assert result == "51.5074,-0.1278"

        result = service._ensure_coordinates("52.5308,13.3847")
        assert result == "52.5308,13.3847"

    @patch.object(TrafficService, '_geocode_location')
    def test_ensure_coordinates_with_address(self, mock_geocode, service):
        """Test _ensure_coordinates with address (triggers geocoding)."""
        mock_geocode.return_value = "51.5074,-0.1278"

        result = service._ensure_coordinates("London, UK")

        assert result == "51.5074,-0.1278"
        mock_geocode.assert_called_once_with("London, UK")

    @patch.object(TrafficService, '_geocode_location')
    def test_ensure_coordinates_geocoding_fails(self, mock_geocode, service):
        """Test _ensure_coordinates when geocoding fails."""
        mock_geocode.return_value = None

        result = service._ensure_coordinates("Invalid Location")

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_routing_api_error(self, mock_get, service):
        """Test routing API error handling."""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_get.return_value = mock_response

        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922"
        )

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_timeout(self, mock_get, service):
        """Test routing API timeout handling."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")

        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922"
        )

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_invalid_response(self, mock_get, service):
        """Test handling of invalid API response format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"routes": []}  # Empty routes
        mock_get.return_value = mock_response

        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922"
        )

        assert result is None

    @patch('core.traffic_service.requests.get')
    def test_get_traffic_estimate_high_traffic_delay(self, mock_get, service):
        """Test traffic estimate with significant delay."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "routes": [{
                "sections": [{
                    "summary": {
                        "length": 15000,
                        "duration": 2400,  # 40 minutes
                        "baseDuration": 1200  # 20 minutes base
                    }
                }]
            }]
        }
        mock_get.return_value = mock_response

        result = service.get_traffic_estimate(
            origin="51.5074,-0.1278",
            destination="51.5155,-0.0922"
        )

        # Verify high traffic delay is calculated correctly
        assert result["duration_minutes"] == 40
        assert result["duration_in_traffic_minutes"] == 40
        assert result["traffic_delay_minutes"] == 20

    def test_ensure_coordinates_validates_format(self, service):
        """Test coordinate format validation via _ensure_coordinates."""
        # Valid coordinates should be returned as-is
        result = service._ensure_coordinates("51.5074,-0.1278")
        assert result == "51.5074,-0.1278"

        result = service._ensure_coordinates("52.5308,13.3847")
        assert result == "52.5308,13.3847"

        result = service._ensure_coordinates("-33.8688,151.2093")
        assert result == "-33.8688,151.2093"
