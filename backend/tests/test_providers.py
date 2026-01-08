"""
Comprehensive tests for all LLM provider modules.

Tests cover:
- Provider instantiation
- Chat method (non-streaming)
- Stream chat method
- Error handling
- Token usage tracking
- API response parsing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestAnthropicProvider:
    """Tests for providers/anthropic.py"""

    def test_init_success(self):
        """Test successful provider initialization."""
        from providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(
            api_key="sk-ant-test",
            model="claude-3-opus"
        )

        assert provider.api_key == "sk-ant-test"
        assert provider.model == "claude-3-opus"
        assert provider.base_url == "https://api.anthropic.com/v1/messages"

    def test_init_custom_base_url(self):
        """Test initialization with custom base URL."""
        from providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(
            api_key="sk-ant-test",
            base_url="https://custom.api.com/v1/messages",
            model="claude-3-opus"
        )

        assert provider.base_url == "https://custom.api.com/v1/messages"

    def test_init_missing_model(self):
        """Test initialization fails without model."""
        from providers.anthropic import AnthropicProvider

        with pytest.raises(ValueError, match="requires a valid model name"):
            AnthropicProvider(api_key="sk-ant-test")

    def test_init_invalid_model(self):
        """Test initialization fails with invalid model."""
        from providers.anthropic import AnthropicProvider

        with pytest.raises(ValueError, match="requires a valid model name"):
            AnthropicProvider(api_key="sk-ant-test", model=None)

    @patch('providers.anthropic.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        from providers.anthropic import AnthropicProvider

        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "Hello! How can I help you?"}
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20
            }
        }
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")
        result = provider.chat(
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": "Hello"}
            ]
        )

        assert result == "Hello! How can I help you?"
        assert provider._last_usage["input_tokens"] == 10
        assert provider._last_usage["output_tokens"] == 20

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "claude-3-opus"
        assert call_args[1]["json"]["system"] == "You are a helpful assistant."

    @patch('providers.anthropic.requests.post')
    def test_chat_filters_empty_messages(self, mock_post):
        """Test that empty messages are filtered out."""
        from providers.anthropic import AnthropicProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Response"}],
            "usage": {"input_tokens": 5, "output_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")
        provider.chat(
            system="Test",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": ""},  # Empty
                {"role": "user", "content": "   "},  # Whitespace only
                {"role": "user", "content": "World"}
            ]
        )

        # Verify only non-empty messages were sent
        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]
        assert len(sent_messages) == 2
        assert sent_messages[0]["content"] == "Hello"
        assert sent_messages[1]["content"] == "World"

    @patch('providers.anthropic.requests.post')
    def test_chat_filters_system_messages(self, mock_post):
        """Test that system role messages are filtered from message list."""
        from providers.anthropic import AnthropicProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Response"}],
            "usage": {"input_tokens": 5, "output_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")
        provider.chat(
            system="System prompt",
            messages=[
                {"role": "system", "content": "Old system message"},
                {"role": "user", "content": "Hello"}
            ]
        )

        # Verify system role message was filtered out
        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]
        assert len(sent_messages) == 1
        assert sent_messages[0]["role"] == "user"

    @patch('providers.anthropic.requests.post')
    def test_chat_multiple_content_blocks(self, mock_post):
        """Test handling multiple content blocks in response."""
        from providers.anthropic import AnthropicProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "text", "text": "First part. "},
                {"type": "text", "text": "Second part."}
            ],
            "usage": {"input_tokens": 5, "output_tokens": 10}
        }
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")
        result = provider.chat(system="Test", messages=[{"role": "user", "content": "Hi"}])

        assert result == "First part. \nSecond part."

    @patch('providers.anthropic.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error responses."""
        from providers.anthropic import AnthropicProvider

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")

        with pytest.raises(RuntimeError, match="Anthropic API error 500"):
            provider.chat(system="Test", messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.anthropic.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming chat."""
        from providers.anthropic import AnthropicProvider

        # Mock SSE streaming response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        sse_lines = [
            "event: content_block_start",
            'data: {"type":"content_block_start"}',
            "",
            "event: content_block_delta",
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
            "",
            "event: content_block_delta",
            'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":" world"}}',
            "",
            "event: content_block_stop",
            "data: [DONE]"
        ]
        mock_response.iter_lines.return_value = sse_lines
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")
        chunks = list(provider.stream_chat(
            system="Test",
            messages=[{"role": "user", "content": "Hi"}]
        ))

        assert chunks == ["Hello", " world"]

    @patch('providers.anthropic.requests.post')
    def test_stream_chat_api_error(self, mock_post):
        """Test streaming with API error."""
        from providers.anthropic import AnthropicProvider

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_post.return_value = mock_response

        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-opus")

        with pytest.raises(RuntimeError, match="Anthropic API error 429"):
            list(provider.stream_chat(system="Test", messages=[{"role": "user", "content": "Hi"}]))


class TestOpenAIProvider:
    """Tests for providers/openai.py"""

    def test_init_success(self):
        """Test successful provider initialization."""
        from providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key="sk-test")

        assert provider.api_key == "sk-test"
        assert provider.base_url == "https://api.openai.com/v1"
        assert provider.model is None

    def test_init_with_custom_settings(self):
        """Test initialization with custom settings."""
        from providers.openai import OpenAIProvider

        provider = OpenAIProvider(
            api_key="sk-test",
            base_url="https://custom.openai.com",
            model="gpt-4"
        )

        assert provider.base_url == "https://custom.openai.com"
        assert provider.model == "gpt-4"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        from providers.openai import OpenAIProvider

        with pytest.raises(ValueError, match="requires an api_key"):
            OpenAIProvider()

    @patch('providers.openai.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! How can I help?"
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25
            }
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test", model="gpt-4")
        result = provider.chat(
            system="You are helpful",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result == "Hello! How can I help?"
        assert provider._last_usage["input_tokens"] == 15
        assert provider._last_usage["output_tokens"] == 25

    @patch('providers.openai.requests.post')
    def test_chat_injects_system_to_last_message(self, mock_post):
        """Test that system prompt is injected into the last user message."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")
        provider.chat(
            system="Remember: You are THEO",
            messages=[
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "OK"},
                {"role": "user", "content": "Second message"}
            ]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # First user message should NOT have system injected
        assert "THEO" not in sent_messages[0]["content"]

        # Last user message SHOULD have system injected
        assert "IMPORTANT PERSISTENT CONTEXT" in sent_messages[2]["content"]
        assert "THEO" in sent_messages[2]["content"]
        assert "Second message" in sent_messages[2]["content"]

    @patch('providers.openai.requests.post')
    def test_chat_model_fallback(self, mock_post):
        """Test model fallback to gpt-4o-mini."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")  # No model specified
        provider.chat(messages=[{"role": "user", "content": "Hi"}])

        call_args = mock_post.call_args
        assert call_args[1]["json"]["model"] == "gpt-4o-mini"

    @patch('providers.openai.requests.post')
    def test_chat_filters_empty_and_system_messages(self, mock_post):
        """Test filtering of empty and system messages."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")
        provider.chat(
            messages=[
                {"role": "system", "content": "System message"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": ""},  # Empty
                {"role": "user", "content": None}  # None content
            ]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]
        assert len(sent_messages) == 1
        assert sent_messages[0]["content"] == "Hello"

    @patch('providers.openai.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-invalid")

        with pytest.raises(RuntimeError, match="OpenAI API error 401"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.openai.requests.post')
    def test_chat_unexpected_response_format(self, mock_post):
        """Test handling unexpected response format."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "format"}
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")

        with pytest.raises(RuntimeError, match="Unexpected OpenAI response"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.openai.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 200

        stream_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" there"}}]}',
            b'data: {"choices":[{"delta":{}}]}',
            b'data: [DONE]'
        ]
        mock_response.iter_lines.return_value = stream_lines
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")
        chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == ["Hello", " there"]

    @patch('providers.openai.requests.post')
    def test_stream_chat_api_error(self, mock_post):
        """Test streaming with API error."""
        from providers.openai import OpenAIProvider

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="sk-test")

        with pytest.raises(RuntimeError, match="OpenAI API error 500"):
            list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))


class TestGoogleProvider:
    """Tests for providers/gemini.py"""

    def test_init_success(self):
        """Test successful initialization."""
        from providers.gemini import GoogleProvider

        provider = GoogleProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.base_url == "https://generativelanguage.googleapis.com/v1beta"

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        from providers.gemini import GoogleProvider

        provider = GoogleProvider(
            api_key="test-key",
            base_url="https://custom.google.com",
            model="gemini-pro"
        )

        assert provider.base_url == "https://custom.google.com"
        assert provider.model == "gemini-pro"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        from providers.gemini import GoogleProvider

        with pytest.raises(ValueError, match="requires an api_key"):
            GoogleProvider()

    @patch('providers.gemini.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Hello from Gemini!"}
                        ]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 12,
                "candidatesTokenCount": 18
            }
        }
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")
        result = provider.chat(
            system="You are helpful",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result == "Hello from Gemini!"
        assert provider._last_usage["input_tokens"] == 12
        assert provider._last_usage["output_tokens"] == 18

    @patch('providers.gemini.requests.post')
    def test_chat_missing_model(self, mock_post):
        """Test chat fails without model."""
        from providers.gemini import GoogleProvider

        provider = GoogleProvider(api_key="test-key")

        with pytest.raises(ValueError, match="requires a model to be specified"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.gemini.requests.post')
    def test_chat_role_mapping(self, mock_post):
        """Test role mapping (assistant -> model, user -> user)."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Response"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 5}
        }
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")
        provider.chat(
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "How are you?"}
            ]
        )

        call_args = mock_post.call_args
        contents = call_args[1]["json"]["contents"]

        assert contents[0]["role"] == "user"
        assert contents[1]["role"] == "model"  # Mapped from assistant
        assert contents[2]["role"] == "user"

    @patch('providers.gemini.requests.post')
    def test_chat_system_injection_to_last_message(self, mock_post):
        """Test system prompt injection into last user message."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Response"}]}}],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 5}
        }
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")
        provider.chat(
            system="You are GEMINI",
            messages=[
                {"role": "user", "content": "First"},
                {"role": "user", "content": "Second"}
            ]
        )

        call_args = mock_post.call_args
        contents = call_args[1]["json"]["contents"]

        # First message should not have system
        first_text = contents[0]["parts"][0]["text"]
        assert "GEMINI" not in first_text

        # Last message should have system injected
        last_text = contents[1]["parts"][0]["text"]
        assert "IMPORTANT PERSISTENT CONTEXT" in last_text
        assert "GEMINI" in last_text

    @patch('providers.gemini.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")

        with pytest.raises(RuntimeError, match="Gemini API error 400"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.gemini.requests.post')
    def test_chat_unexpected_response(self, mock_post):
        """Test handling unexpected response format."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected": "format"}
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")

        with pytest.raises(RuntimeError, match="Unexpected Gemini response"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.gemini.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 200

        stream_lines = [
            b'{"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            b'{"candidates":[{"content":{"parts":[{"text":" world"}]}}]}',
            b'{"candidates":[{"content":{"parts":[{"text":"!"}]}}]}'
        ]
        mock_response.iter_lines.return_value = stream_lines
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")
        chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == ["Hello", " world", "!"]

    @patch('providers.gemini.requests.post')
    def test_stream_chat_api_error(self, mock_post):
        """Test streaming with API error."""
        from providers.gemini import GoogleProvider

        mock_response = Mock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        mock_post.return_value = mock_response

        provider = GoogleProvider(api_key="test-key", model="gemini-pro")

        with pytest.raises(RuntimeError, match="Gemini API error 503"):
            list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))


class TestXAIProvider:
    """Tests for providers/grok.py (XAI/Grok provider)"""

    def test_init_success(self):
        """Test successful initialization."""
        from providers.grok import XAIProvider

        provider = XAIProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.x.ai/v1"

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        from providers.grok import XAIProvider

        provider = XAIProvider(
            api_key="test-key",
            base_url="https://custom.xai.com",
            model="grok-beta"
        )

        assert provider.base_url == "https://custom.xai.com"
        assert provider.model == "grok-beta"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        from providers.grok import XAIProvider

        with pytest.raises(ValueError, match="requires an api_key"):
            XAIProvider()

    @patch('providers.grok.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        from providers.grok import XAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from Grok!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15}
        }
        mock_post.return_value = mock_response

        provider = XAIProvider(api_key="test-key", model="grok-beta")
        result = provider.chat(
            system="You are helpful",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result == "Hello from Grok!"
        assert provider._last_usage["input_tokens"] == 10
        assert provider._last_usage["output_tokens"] == 15

    @patch('providers.grok.requests.post')
    def test_chat_adds_system_message_separately(self, mock_post):
        """Test that system prompt is added as separate system message."""
        from providers.grok import XAIProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = XAIProvider(api_key="test-key", model="grok-beta")
        provider.chat(
            system="You are Grok",
            messages=[{"role": "user", "content": "Hello"}]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # First message should be system message
        assert sent_messages[0]["role"] == "system"
        assert sent_messages[0]["content"] == "You are Grok"

        # Second message should be user message
        assert sent_messages[1]["role"] == "user"
        assert sent_messages[1]["content"] == "Hello"

    @patch('providers.grok.requests.post')
    def test_chat_missing_model(self, mock_post):
        """Test chat fails without model."""
        from providers.grok import XAIProvider

        provider = XAIProvider(api_key="test-key")

        with pytest.raises(ValueError, match="requires a model to be specified"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.grok.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error."""
        from providers.grok import XAIProvider

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_post.return_value = mock_response

        provider = XAIProvider(api_key="test-key", model="grok-beta")

        with pytest.raises(RuntimeError, match="xAI API error 500"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.grok.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming."""
        from providers.grok import XAIProvider

        mock_response = Mock()
        mock_response.status_code = 200

        stream_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" from Grok"}}]}',
            b'data: [DONE]'
        ]
        mock_response.iter_lines.return_value = stream_lines
        mock_post.return_value = mock_response

        provider = XAIProvider(api_key="test-key", model="grok-beta")
        chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == ["Hello", " from Grok"]


class TestMistralProvider:
    """Tests for providers/mistral.py"""

    def test_init_success(self):
        """Test successful initialization."""
        from providers.mistral import MistralProvider

        provider = MistralProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.mistral.ai/v1"

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        from providers.mistral import MistralProvider

        provider = MistralProvider(
            api_key="test-key",
            base_url="https://custom.mistral.com",
            model="mistral-medium"
        )

        assert provider.base_url == "https://custom.mistral.com"
        assert provider.model == "mistral-medium"

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        from providers.mistral import MistralProvider

        with pytest.raises(ValueError, match="requires an api_key"):
            MistralProvider()

    @patch('providers.mistral.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        from providers.mistral import MistralProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Bonjour from Mistral!"}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 12}
        }
        mock_post.return_value = mock_response

        provider = MistralProvider(api_key="test-key", model="mistral-small")
        result = provider.chat(
            system="You are helpful",
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result == "Bonjour from Mistral!"
        assert provider._last_usage["input_tokens"] == 8
        assert provider._last_usage["output_tokens"] == 12

    @patch('providers.mistral.requests.post')
    def test_chat_injects_system_to_last_message(self, mock_post):
        """Test system prompt injection into last user message."""
        from providers.mistral import MistralProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = MistralProvider(api_key="test-key", model="mistral-small")
        provider.chat(
            system="You are Mistral",
            messages=[
                {"role": "user", "content": "First"},
                {"role": "user", "content": "Second"}
            ]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # First message should not have system
        assert "Mistral" not in sent_messages[0]["content"]

        # Last message should have system injected
        assert "IMPORTANT PERSISTENT CONTEXT" in sent_messages[1]["content"]
        assert "Mistral" in sent_messages[1]["content"]

    @patch('providers.mistral.requests.post')
    def test_chat_missing_model(self, mock_post):
        """Test chat fails without model."""
        from providers.mistral import MistralProvider

        provider = MistralProvider(api_key="test-key")

        with pytest.raises(ValueError, match="requires a model to be specified"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.mistral.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error."""
        from providers.mistral import MistralProvider

        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_post.return_value = mock_response

        provider = MistralProvider(api_key="test-key", model="mistral-small")

        with pytest.raises(RuntimeError, match="Mistral API error 429"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.mistral.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming."""
        from providers.mistral import MistralProvider

        mock_response = Mock()
        mock_response.status_code = 200

        stream_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" from Mistral"}}]}',
            b'data: [DONE]'
        ]
        mock_response.iter_lines.return_value = stream_lines
        mock_post.return_value = mock_response

        provider = MistralProvider(api_key="test-key", model="mistral-small")
        chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == ["Hello", " from Mistral"]


class TestPerplexityProvider:
    """Tests for providers/perplexity.py"""

    def test_init_success(self):
        """Test successful initialization with defaults."""
        from providers.perplexity import PerplexityProvider

        provider = PerplexityProvider(api_key="test-key")

        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.perplexity.ai"
        assert provider.model == "llama-3.1-sonar-small-128k-online"
        assert provider.search_mode is True

    def test_init_custom_settings(self):
        """Test initialization with custom settings."""
        from providers.perplexity import PerplexityProvider

        provider = PerplexityProvider(
            api_key="test-key",
            base_url="https://custom.perplexity.com",
            model="llama-3.1-sonar-large-128k-online",
            search_mode=False
        )

        assert provider.base_url == "https://custom.perplexity.com"
        assert provider.model == "llama-3.1-sonar-large-128k-online"
        assert provider.search_mode is False

    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        from providers.perplexity import PerplexityProvider

        with pytest.raises(ValueError, match="requires an api_key"):
            PerplexityProvider()

    @patch('providers.perplexity.requests.post')
    def test_chat_success_with_search(self, mock_post):
        """Test successful chat with search mode enabled."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Here's what I found..."}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            "citations": ["https://example.com/source1", "https://example.com/source2"]
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="test-key", search_mode=True)
        result = provider.chat(messages=[{"role": "user", "content": "Latest news?"}])

        assert result == "Here's what I found..."
        assert provider._last_usage["input_tokens"] == 20
        assert provider._last_usage["output_tokens"] == 30
        assert provider._last_usage["citations"] == ["https://example.com/source1", "https://example.com/source2"]
        assert provider._last_usage["web_grounded"] is True

        # Verify search params were sent
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["return_citations"] is True
        assert payload["country"] == "GB"

    @patch('providers.perplexity.requests.post')
    def test_chat_message_alternation(self, mock_post):
        """Test that consecutive messages with same role are merged."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="test-key")
        provider.chat(
            messages=[
                {"role": "user", "content": "First message"},
                {"role": "user", "content": "Second message"},
                {"role": "assistant", "content": "Response 1"},
                {"role": "assistant", "content": "Response 2"}
            ]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # Should have merged consecutive messages
        assert len(sent_messages) == 2
        assert "First message" in sent_messages[0]["content"]
        assert "Second message" in sent_messages[0]["content"]
        assert "Response 1" in sent_messages[1]["content"]
        assert "Response 2" in sent_messages[1]["content"]

    @patch('providers.perplexity.requests.post')
    def test_chat_removes_leading_assistant_messages(self, mock_post):
        """Test that leading assistant messages are removed."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="test-key")
        provider.chat(
            messages=[
                {"role": "assistant", "content": "I'm here"},
                {"role": "user", "content": "Hello"}
            ]
        )

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # Should start with user message
        assert sent_messages[0]["role"] == "user"
        assert sent_messages[0]["content"] == "Hello"

    @patch('providers.perplexity.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test handling API error."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="invalid-key")

        with pytest.raises(RuntimeError, match="Perplexity API error 401"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.perplexity.requests.post')
    def test_chat_timeout(self, mock_post):
        """Test handling request timeout."""
        from providers.perplexity import PerplexityProvider
        import requests

        mock_post.side_effect = requests.exceptions.Timeout()

        provider = PerplexityProvider(api_key="test-key")

        with pytest.raises(RuntimeError, match="timed out"):
            provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming with citations."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 200

        stream_lines = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: {"citations":["https://example.com"],"usage":{"prompt_tokens":10,"completion_tokens":5},"choices":[{"delta":{}}]}',
            b'data: [DONE]'
        ]
        mock_response.iter_lines.return_value = stream_lines
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="test-key", search_mode=True)
        chunks = list(provider.stream_chat(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == ["Hello", " world"]
        assert provider._last_usage["citations"] == ["https://example.com"]
        assert provider._last_usage["input_tokens"] == 10
        assert provider._last_usage["output_tokens"] == 5

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_with_uk_context(self, mock_post):
        """Test streaming adds UK context in search mode."""
        from providers.perplexity import PerplexityProvider

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="test-key", search_mode=True)
        list(provider.stream_chat(
            system="Context",
            messages=[{"role": "user", "content": "Weather today?"}]
        ))

        call_args = mock_post.call_args
        sent_messages = call_args[1]["json"]["messages"]

        # Should add UK context to user message in search mode
        assert "UK" in sent_messages[0]["content"]
        assert "Weather today?" in sent_messages[0]["content"]
