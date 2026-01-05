"""
Tests for WHOOP Integration

Comprehensive test suite covering:
- OAuth flow
- API client
- Memory operations
- Proactive notifications
- Medical guardrails
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from backend.auth.whoop_oauth import WHOOPOAuthHandler
from backend.services.whoop_client import WHOOPClient, WHOOPClientFactory
from backend.core.proactive.whoop_sleep_service import WHOOPSleepService
from backend.core.proactive.whoop_workout_service import WHOOPWorkoutService
from backend.core.proactive.whoop_stress_service import WHOOPStressService


class TestWHOOPOAuth:
    """Test WHOOP OAuth flow."""

    def test_authorization_url_generation(self):
        """Test that authorization URL is correctly generated."""
        handler = WHOOPOAuthHandler(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:1066/callback"
        )

        url, state = handler.get_authorization_url()

        assert "https://api.prod.whoop.com/oauth/oauth2/auth" in url
        assert "client_id=test_client" in url
        assert "response_type=code" in url
        assert f"state={state}" in url
        assert len(state) == 64  # SHA256 hex is 64 chars

    @patch('requests.post')
    def test_token_exchange_success(self, mock_post):
        """Test successful token exchange."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user": {"id": 123456}
        }
        mock_post.return_value = mock_response

        handler = WHOOPOAuthHandler(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:1066/callback"
        )

        result = handler.exchange_code_for_token("auth_code_123")

        assert result["access_token"] == "test_access_token"
        assert result["token_type"] == "Bearer"
        assert "expires_at" in result
        assert "whoop_user_id" in result

    @patch('requests.post')
    def test_token_exchange_failure(self, mock_post):
        """Test token exchange with invalid code."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("Invalid code")
        mock_post.return_value = mock_response

        handler = WHOOPOAuthHandler(
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:1066/callback"
        )

        with pytest.raises(Exception):
            handler.exchange_code_for_token("invalid_code")


class TestWHOOPClient:
    """Test WHOOP API client."""

    @patch('requests.Session')
    def test_get_user_profile(self, mock_session):
        """Test fetching user profile."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": 123456,
            "email": "test@example.com",
            "first_name": "Test"
        }

        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        client = WHOOPClient("test_access_token")
        client.session = mock_session_instance

        profile = client.get_user_profile()

        assert profile["user_id"] == 123456
        assert profile["email"] == "test@example.com"

    @patch('requests.Session')
    def test_get_latest_sleep(self, mock_session):
        """Test fetching latest sleep record."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [{
                "id": "sleep_123",
                "score": {
                    "sleep_performance_percentage": 85,
                    "sleep_efficiency_percentage": 90
                }
            }]
        }

        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance

        client = WHOOPClient("test_access_token")
        client.session = mock_session_instance

        sleep = client.get_latest_sleep()

        assert sleep["id"] == "sleep_123"
        assert sleep["score"]["sleep_performance_percentage"] == 85


class TestWHOOPSleepService:
    """Test WHOOP sleep notification service."""

    def test_medical_guardrails_in_summary(self):
        """Test that summaries use observational language only."""
        mock_memory = Mock()
        service = WHOOPSleepService(mock_memory)

        mock_data = {
            "sleep": {
                "id": "sleep_123",
                "score": {
                    "sleep_performance_percentage": 85,
                    "sleep_efficiency_percentage": 90,
                    "total_in_bed_time_milli": 28800000  # 8 hours
                },
                "end": "2026-01-05T08:00:00Z"
            },
            "recovery": {
                "score": {
                    "recovery_score": 75,
                    "hrv_rmssd_milli": 45.5,
                    "resting_heart_rate": 55
                }
            }
        }

        summary = service._generate_sleep_summary(mock_data)

        # Check for observational language
        assert "observed" in summary.lower() or "metrics" in summary.lower()

        # Ensure no medical advice
        assert "should" not in summary.lower()
        assert "must" not in summary.lower()
        assert "recommend" not in summary.lower()
        assert "diagnos" not in summary.lower()
        assert "prescri" not in summary.lower()

        # Check key metrics are included
        assert "85" in summary  # Sleep performance
        assert "90" in summary  # Sleep efficiency
        assert "8.0" in summary  # Hours
        assert "75" in summary  # Recovery score

    def test_notification_not_sent_when_disabled(self):
        """Test that notifications are not sent when disabled in settings."""
        mock_memory = Mock()
        mock_memory.get_whoop_settings.return_value = {
            "sleep_notifications_enabled": False
        }

        service = WHOOPSleepService(mock_memory)
        result = service.check_and_notify(user_id=1)

        assert result is False
        mock_memory.store_proactive_message.assert_not_called()

    def test_notification_not_duplicated(self):
        """Test that notifications are not sent twice for same sleep record."""
        mock_memory = Mock()
        mock_memory.get_whoop_settings.return_value = {
            "sleep_notifications_enabled": True
        }
        mock_memory.get_whoop_credentials.return_value = {
            "is_valid": True,
            "access_token": "test_token",
            "user_id": 1
        }
        mock_memory.has_whoop_data_been_notified.return_value = True

        with patch('backend.services.whoop_client.WHOOPClientFactory.create_client') as mock_factory:
            mock_client = Mock()
            mock_client.get_latest_sleep.return_value = {"id": "sleep_123"}
            mock_factory.return_value = mock_client

            service = WHOOPSleepService(mock_memory)
            result = service.check_and_notify(user_id=1)

            assert result is False
            mock_memory.track_whoop_data.assert_not_called()


class TestWHOOPStressService:
    """Test WHOOP stress notification service."""

    def test_stress_summary_includes_disclaimer(self):
        """Test that stress summaries include medical disclaimer."""
        mock_memory = Mock()
        service = WHOOPStressService(mock_memory)

        mock_recovery = {
            "id": "recovery_123",
            "score": {
                "recovery_score": 65,
                "hrv_rmssd_milli": 42.0,
                "resting_heart_rate": 58,
                "spo2_percentage": 97.5
            },
            "created_at": "2026-01-05T14:00:00Z"
        }

        summary = service._generate_stress_summary(mock_recovery)

        # Check for medical disclaimer
        assert "not medical advice" in summary.lower() or "observational data only" in summary.lower()
        assert "consult" in summary.lower() or "healthcare" in summary.lower()

    def test_stress_interpretation_ranges(self):
        """Test that recovery score interpretations are observational."""
        mock_memory = Mock()
        service = WHOOPStressService(mock_memory)

        # High recovery (>= 67%)
        high_recovery = {
            "id": "r1",
            "score": {"recovery_score": 80},
            "created_at": "2026-01-05T14:00:00Z"
        }
        summary_high = service._generate_stress_summary(high_recovery)
        assert "well-recovered" in summary_high.lower()

        # Medium recovery (34-66%)
        medium_recovery = {
            "id": "r2",
            "score": {"recovery_score": 50},
            "created_at": "2026-01-05T14:00:00Z"
        }
        summary_medium = service._generate_stress_summary(medium_recovery)
        assert "moderate" in summary_medium.lower()

        # Low recovery (< 34%)
        low_recovery = {
            "id": "r3",
            "score": {"recovery_score": 25},
            "created_at": "2026-01-05T14:00:00Z"
        }
        summary_low = service._generate_stress_summary(low_recovery)
        assert "rest" in summary_low.lower()


class TestWHOOPWorkoutService:
    """Test WHOOP workout notification service."""

    def test_sport_name_mapping(self):
        """Test that sport IDs are correctly mapped to names."""
        mock_memory = Mock()
        service = WHOOPWorkoutService(mock_memory)

        assert service._get_sport_name(1) == "Running"
        assert service._get_sport_name(45) == "Weightlifting"
        assert service._get_sport_name(44) == "Yoga"
        assert service._get_sport_name(999) == "Activity (ID: 999)"

    def test_workout_summary_format(self):
        """Test workout summary includes all key metrics."""
        mock_memory = Mock()
        service = WHOOPWorkoutService(mock_memory)

        mock_workout = {
            "id": "workout_123",
            "sport_id": 1,  # Running
            "score": {
                "strain": 15.2,
                "duration_milli": 3600000,  # 1 hour
                "average_heart_rate": 150,
                "max_heart_rate": 180,
                "kilojoule": 2000
            },
            "end": "2026-01-05T10:00:00Z"
        }

        summary = service._generate_workout_summary(mock_workout)

        assert "Running" in summary
        assert "15.2" in summary  # Strain
        assert "60" in summary  # Duration in minutes
        assert "150" in summary  # Avg HR
        assert "180" in summary  # Max HR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
