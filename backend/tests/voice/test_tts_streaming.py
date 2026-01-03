"""
Tests for streaming TTS functionality.

Verifies that OpenAI TTS provider can stream audio chunks
for progressive playback instead of buffering complete files.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from voice.tts_openai import OpenAITTSProvider


class TestOpenAITTSStreaming:
    """Test suite for OpenAI TTS streaming functionality."""

    @pytest.fixture
    def provider(self):
        """Create a test TTS provider instance."""
        return OpenAITTSProvider(api_key="test-key", model="tts-1")

    def test_synthesize_stream_yields_chunks(self, provider):
        """Test that synthesize_stream yields audio chunks."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            # Mock context manager and response
            mock_context = MagicMock()
            mock_response = Mock()
            chunks = [b'chunk1', b'chunk2', b'chunk3']
            mock_response.iter_bytes = Mock(return_value=iter(chunks))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            # Collect all chunks
            result_chunks = list(provider.synthesize_stream(
                text="Test text",
                voice="alloy",
                speed=1.0
            ))

            # Verify we got chunks
            assert len(result_chunks) == 3
            assert result_chunks[0] == b'chunk1'
            assert result_chunks[1] == b'chunk2'
            assert result_chunks[2] == b'chunk3'

    def test_synthesize_stream_matches_buffered_size(self, provider):
        """Test that total streamed bytes match buffered synthesis."""
        test_text = "This is a test message for TTS"

        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            # Mock response for streaming
            total_audio = b'complete_audio_data_here'
            chunk_size = 4096

            # For streaming: return chunks via iter_bytes
            mock_context = MagicMock()
            mock_response = Mock()
            stream_chunks = [
                total_audio[i:i+chunk_size]
                for i in range(0, len(total_audio), chunk_size)
            ]
            mock_response.iter_bytes = Mock(return_value=iter(stream_chunks))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            # Test streaming
            streamed_chunks = list(provider.synthesize_stream(text=test_text))
            streamed_total = b''.join(streamed_chunks)

            # Verify size
            assert len(streamed_total) == len(total_audio)

    def test_synthesize_stream_validates_voice(self, provider):
        """Test that invalid voice falls back to default."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            mock_context = MagicMock()
            mock_response = Mock()
            mock_response.iter_bytes = Mock(return_value=iter([b'audio']))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            # Use invalid voice
            list(provider.synthesize_stream(
                text="Test",
                voice="invalid_voice",
                speed=1.0
            ))

            # Verify call was made with default voice
            call_kwargs = mock_streaming.create.call_args[1]
            assert call_kwargs['voice'] == 'alloy'  # default voice

    def test_synthesize_stream_validates_speed(self, provider):
        """Test that speed is clamped to valid range (0.25-4.0)."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            mock_context = MagicMock()
            mock_response = Mock()
            mock_response.iter_bytes = Mock(return_value=iter([b'audio']))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            # Test speed too high
            list(provider.synthesize_stream(text="Test", speed=10.0))
            call_kwargs = mock_streaming.create.call_args[1]
            assert call_kwargs['speed'] == 4.0

            # Test speed too low
            list(provider.synthesize_stream(text="Test", speed=0.1))
            call_kwargs = mock_streaming.create.call_args[1]
            assert call_kwargs['speed'] == 0.25

    def test_synthesize_stream_empty_text_raises_error(self, provider):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            list(provider.synthesize_stream(text=""))

        with pytest.raises(ValueError, match="Text cannot be empty"):
            list(provider.synthesize_stream(text="   "))

    def test_synthesize_stream_api_error_handling(self, provider):
        """Test graceful handling of API errors."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            # Simulate API error
            mock_streaming.create.side_effect = Exception("API error")

            with pytest.raises(Exception, match="TTS streaming failed"):
                list(provider.synthesize_stream(text="Test"))

    def test_synthesize_stream_uses_correct_model(self, provider):
        """Test that streaming uses the configured model (tts-1)."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            mock_context = MagicMock()
            mock_response = Mock()
            mock_response.iter_bytes = Mock(return_value=iter([b'audio']))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            list(provider.synthesize_stream(text="Test"))

            # Verify correct model was used
            call_kwargs = mock_streaming.create.call_args[1]
            assert call_kwargs['model'] == 'tts-1'

    def test_synthesize_stream_output_format(self, provider):
        """Test that output format is correctly passed to API."""
        with patch.object(provider.client.audio.speech, 'with_streaming_response') as mock_streaming:
            mock_context = MagicMock()
            mock_response = Mock()
            mock_response.iter_bytes = Mock(return_value=iter([b'audio']))
            mock_context.__enter__ = Mock(return_value=mock_response)
            mock_context.__exit__ = Mock(return_value=False)
            mock_streaming.create = Mock(return_value=mock_context)

            list(provider.synthesize_stream(
                text="Test",
                output_format="opus"
            ))

            # Verify format was passed
            call_kwargs = mock_streaming.create.call_args[1]
            assert call_kwargs['response_format'] == 'opus'
