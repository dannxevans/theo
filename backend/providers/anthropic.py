import requests
import json
from providers.base import LLMProvider
from typing import Optional


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider adapter.

    Supports:
    - synchronous full-response calls
    - real token streaming via SSE

    Streaming yields text chunks as they arrive.
    """

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if not model or not isinstance(model, str):
            raise ValueError("AnthropicProvider requires a valid model name")

        self.api_key = api_key
        self.base_url = base_url or "https://api.anthropic.com/v1/messages"
        self.model = model

    def chat(self, system, messages):
        """
        system: string system prompt
        messages: list of {role, content}
        """

        # Anthropic expects system separately and messages without system role
        user_messages = []
        for m in messages:
            if m["role"] == "system":
                continue
            user_messages.append({
                "role": m["role"],
                "content": m["content"]
            })

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.3,
            "system": system,
            "messages": user_messages,
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        response = requests.post(
            self.base_url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Anthropic API error {response.status_code}: {response.text}"
            )

        data = response.json()

        # Claude returns a list of content blocks
        text_parts = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "\n".join(text_parts)

    def stream_chat(self, system, messages):
        """
        Real streaming using Anthropic SSE.
        Yields text chunks as they arrive.
        """

        user_messages = []
        for m in messages:
            if m["role"] == "system":
                continue
            user_messages.append({
                "role": m["role"],
                "content": m["content"]
            })

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0.3,
            "system": system,
            "messages": user_messages,
            "stream": True,
        }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        with requests.post(
            self.base_url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=30,
        ) as response:

            if response.status_code != 200:
                raise RuntimeError(
                    f"Anthropic API error {response.status_code}: {response.text}"
                )

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue

                if not line.startswith("data:"):
                    continue

                data = line[len("data:"):].strip()

                if data == "[DONE]":
                    break

                try:
                    event = json.loads(data)
                except Exception:
                    continue

                # Anthropic Messages API streaming format
                if event.get("type") == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text")
                        if text:
                            yield text