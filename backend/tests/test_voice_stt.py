"""
Tests for OpenAI Whisper STT provider.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, mock_open
from voice.stt_openai import OpenAIWhisperProvider


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    with patch('voice.stt_openai.OpenAI') as mock:
        yield mock


@pytest.fixture
def stt_provider(mock_openai_client):
    """Create a STT provider instance."""
    return OpenAIWhisperProvider(api_key="test-api-key", model="whisper-1")


class TestOpenAIWhisperProvider:
    """Test suite for OpenAI Whisper STT provider."""

    def test_initialization(self, stt_provider):
        """Test provider initialization."""
        assert stt_provider.model == "whisper-1"

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_success(self, mock_unlink, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test successful transcription."""
        # Mock temp file
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.webm"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        # Mock API response
        mock_response = Mock()
        mock_response.text = "Hello, this is a test transcription"
        mock_response.language = "en"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        # Transcribe
        result = stt_provider.transcribe(
            audio_data=b"audio_bytes",
            audio_format="webm"
        )

        # Verify result
        assert result['text'] == "Hello, this is a test transcription"
        assert result['language'] == "en"

        # Verify temp file was created and written
        mock_temp_file.write.assert_called_once_with(b"audio_bytes")

        # Verify API was called
        mock_client.audio.transcriptions.create.assert_called_once()

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_with_language(self, mock_unlink, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test transcription with specified language."""
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.mp3"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_response = Mock()
        mock_response.text = "Hola, esto es una prueba"
        mock_response.language = "es"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        result = stt_provider.transcribe(
            audio_data=b"audio_bytes",
            audio_format="mp3",
            language="es"
        )

        # Verify language was passed to API
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs['language'] == "es"
        assert result['language'] == "es"

    def test_transcribe_empty_audio_raises_error(self, stt_provider):
        """Test that empty audio raises ValueError."""
        with pytest.raises(ValueError, match="Audio data cannot be empty"):
            stt_provider.transcribe(audio_data=b"")

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open)
    def test_transcribe_api_error(self, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test handling of API errors."""
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.webm"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="STT transcription failed"):
            stt_provider.transcribe(b"audio_data")

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.path.exists')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_temp_file_cleanup(self, mock_unlink, mock_exists, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test that temporary files are cleaned up."""
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.webm"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_response = Mock()
        mock_response.text = "Test"
        mock_response.language = "en"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        mock_exists.return_value = True

        stt_provider.transcribe(b"audio_data")

        # Verify temp file was deleted
        mock_unlink.assert_called_once_with("/tmp/test.webm")

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_different_formats(self, mock_unlink, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test transcription with different audio formats."""
        mock_response = Mock()
        mock_response.text = "Test"
        mock_response.language = "en"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        for fmt in ["webm", "mp3", "wav", "m4a"]:
            mock_temp_file = Mock()
            mock_temp_file.name = f"/tmp/test.{fmt}"
            mock_temp.return_value.__enter__.return_value = mock_temp_file

            result = stt_provider.transcribe(b"audio_data", audio_format=fmt)

            # Verify correct file extension
            assert mock_temp_file.name.endswith(f".{fmt}")
            assert result['text'] == "Test"

    def test_check_health(self, stt_provider):
        """Test health check."""
        health = stt_provider.check_health()

        assert health['healthy'] is True
        assert health['provider'] == "openai_whisper"
        assert health['model'] == "whisper-1"
        assert 'note' in health

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_strips_whitespace(self, mock_unlink, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test that transcription result is stripped of whitespace."""
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.webm"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_response = Mock()
        mock_response.text = "  Test with whitespace  "
        mock_response.language = "en"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        result = stt_provider.transcribe(b"audio_data")

        assert result['text'] == "Test with whitespace"

    @patch('voice.stt_openai.tempfile.NamedTemporaryFile')
    @patch('builtins.open', new_callable=mock_open, read_data=b'audio_data')
    @patch('voice.stt_openai.os.unlink')
    def test_transcribe_verbose_json_format(self, mock_unlink, mock_file, mock_temp, stt_provider, mock_openai_client):
        """Test that verbose_json format is requested."""
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.webm"
        mock_temp.return_value.__enter__.return_value = mock_temp_file

        mock_response = Mock()
        mock_response.text = "Test"
        mock_response.language = "en"

        mock_client = mock_openai_client.return_value
        mock_client.audio.transcriptions.create.return_value = mock_response

        stt_provider.transcribe(b"audio_data")

        # Verify verbose_json was requested
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs['response_format'] == "verbose_json"
