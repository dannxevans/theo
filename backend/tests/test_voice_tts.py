"""
Tests for OpenAI TTS provider.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from voice.tts_openai import OpenAITTSProvider


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    with patch('voice.tts_openai.OpenAI') as mock:
        yield mock


@pytest.fixture
def tts_provider(mock_openai_client):
    """Create a TTS provider instance."""
    return OpenAITTSProvider(api_key="test-api-key", model="tts-1-hd")


class TestOpenAITTSProvider:
    """Test suite for OpenAI TTS provider."""

    def test_initialization(self, tts_provider):
        """Test provider initialization."""
        assert tts_provider.model == "tts-1-hd"
        assert tts_provider.default_voice == "alloy"
        assert len(tts_provider.VOICES) == 6

    def test_list_voices(self, tts_provider):
        """Test listing available voices."""
        voices = tts_provider.list_voices()

        assert len(voices) == 6
        assert all('id' in v and 'name' in v and 'description' in v for v in voices)

        # Check specific voices
        voice_ids = [v['id'] for v in voices]
        assert 'alloy' in voice_ids
        assert 'echo' in voice_ids
        assert 'nova' in voice_ids

    def test_synthesize_success(self, tts_provider, mock_openai_client):
        """Test successful text synthesis."""
        # Mock the API response
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data_bytes"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        # Synthesize text
        audio_bytes = tts_provider.synthesize(
            text="Hello world",
            voice="alloy",
            speed=1.0
        )

        # Verify result
        assert audio_bytes == b"audio_data_bytes"

        # Verify API was called correctly
        mock_client.audio.speech.create.assert_called_once_with(
            model="tts-1-hd",
            voice="alloy",
            input="Hello world",
            speed=1.0,
            response_format="mp3"
        )

    def test_synthesize_with_different_voice(self, tts_provider, mock_openai_client):
        """Test synthesis with different voice."""
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        tts_provider.synthesize("Test", voice="nova", speed=1.5)

        call_args = mock_client.audio.speech.create.call_args
        assert call_args.kwargs['voice'] == "nova"
        assert call_args.kwargs['speed'] == 1.5

    def test_synthesize_invalid_voice_fallback(self, tts_provider, mock_openai_client):
        """Test that invalid voice falls back to default."""
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        tts_provider.synthesize("Test", voice="invalid_voice")

        # Should use default voice (alloy)
        call_args = mock_client.audio.speech.create.call_args
        assert call_args.kwargs['voice'] == "alloy"

    def test_synthesize_speed_clamping(self, tts_provider, mock_openai_client):
        """Test that speed is clamped to valid range."""
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        # Test speed too low
        tts_provider.synthesize("Test", speed=0.1)
        call_args = mock_client.audio.speech.create.call_args
        assert call_args.kwargs['speed'] == 0.25

        # Test speed too high
        tts_provider.synthesize("Test", speed=5.0)
        call_args = mock_client.audio.speech.create.call_args
        assert call_args.kwargs['speed'] == 4.0

    def test_synthesize_empty_text_raises_error(self, tts_provider):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            tts_provider.synthesize("")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            tts_provider.synthesize("   ")

    def test_synthesize_api_error(self, tts_provider, mock_openai_client):
        """Test handling of API errors."""
        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="TTS synthesis failed"):
            tts_provider.synthesize("Test")

    def test_check_health_success(self, tts_provider, mock_openai_client):
        """Test health check with successful synthesis."""
        mock_response = Mock()
        mock_response.read.return_value = b"test_audio"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        health = tts_provider.check_health()

        assert health['healthy'] is True
        assert health['provider'] == "openai_tts"
        assert health['model'] == "tts-1-hd"
        assert health['voices_available'] == 6

    def test_check_health_failure(self, tts_provider, mock_openai_client):
        """Test health check with API failure."""
        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.side_effect = Exception("Connection error")

        health = tts_provider.check_health()

        assert health['healthy'] is False
        assert health['provider'] == "openai_tts"
        assert 'error' in health

    def test_synthesize_different_formats(self, tts_provider, mock_openai_client):
        """Test synthesis with different output formats."""
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        for fmt in ["mp3", "opus", "aac", "flac"]:
            tts_provider.synthesize("Test", output_format=fmt)
            call_args = mock_client.audio.speech.create.call_args
            assert call_args.kwargs['response_format'] == fmt

    def test_synthesize_invalid_format_fallback(self, tts_provider, mock_openai_client):
        """Test that invalid format falls back to mp3."""
        mock_response = Mock()
        mock_response.read.return_value = b"audio_data"

        mock_client = mock_openai_client.return_value
        mock_client.audio.speech.create.return_value = mock_response

        tts_provider.synthesize("Test", output_format="invalid")

        call_args = mock_client.audio.speech.create.call_args
        assert call_args.kwargs['response_format'] == "mp3"
