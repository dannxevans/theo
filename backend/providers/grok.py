import requests
import json
import logging


def _is_debug_enabled():
    """Check if debug logging is enabled in user preferences."""
    try:
        from core.memory import MemoryStore
        memory = MemoryStore()
        prefs = memory.get_all("local")
        return str(prefs.get("debug_enabled", "false")).lower() == "true"
    except Exception:
        return False


class XAIProvider:
    """
    xAI Grok provider adapter for THEO.

    Notes:
    - Supports any model string provided by the frontend (no hardcoding).
    - OpenAI-compatible API format.
    - Matches the same interface shape as other providers.
    """

    name = "xai"
    maxContextTokens = 128000
    costTier = "medium"
    supportsStreaming = False

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.x.ai/v1"
        self.model = model

        if not self.api_key:
            raise ValueError("XAIProvider requires an api_key")

    def chat(self, **kwargs):
        """
        Execute a chat completion against xAI.

        Parameters:
        - model: string (passed directly from frontend config)
        - system: system prompt string
        - messages: list of {role, content}
        - temperature: float

        Returns:
        - str (assistant text only)
        """
        if _is_debug_enabled():
            logging.info(f"[DEBUG][XAI] chat() method called with kwargs keys: {list(kwargs.keys())}")

        model = kwargs.get("model") or getattr(self, "model", None)
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if _is_debug_enabled():
            logging.info(f"[DEBUG][XAI] Using model: {model}, base_url: {self.base_url}, has_api_key: {bool(self.api_key)}")

        if not model:
            raise ValueError("XAIProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][xAI] model =", model)
            print("[DEBUG][xAI] system injected =", bool(system))
            if system:
                print("[DEBUG][xAI] system preview =", system[:200])

        url = f"{self.base_url}/chat/completions"

        if _is_debug_enabled():
            logging.info(f"[DEBUG][XAI] Making request to: {url}")

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [],
        }

        # Add system message if provided (xAI supports system role)
        if system:
            payload["messages"].append({
                "role": "system",
                "content": system,
            })

        # Build conversation messages
        for m in messages:
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue  # Already added above
            payload["messages"].append({
                "role": m["role"],
                "content": m["content"],
            })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if _is_debug_enabled():
            logging.info(f"[DEBUG][XAI] Sending request with {len(payload['messages'])} messages")

        resp = requests.post(url, headers=headers, json=payload, timeout=60)

        if _is_debug_enabled():
            logging.info(f"[DEBUG][XAI] Response status code: {resp.status_code}")

        if resp.status_code != 200:
            logging.error(f"[XAI][ERROR] API error {resp.status_code}: {resp.text}")
            raise RuntimeError(
                f"xAI API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()

        try:
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected xAI response: {data}")

        # Store usage data in instance for router to access
        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }

        return text

    def chat_stream(self, **kwargs):
        model = kwargs.get("model") or getattr(self, "model", None)
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if not model:
            raise ValueError("XAIProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][xAI] model =", model)
            print("[DEBUG][xAI] system injected =", bool(system))
            if system:
                print("[DEBUG][xAI] system preview =", system[:200])

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "temperature": temperature,
            "stream": True,
            "messages": [],
        }

        # Add system message if provided (xAI supports system role)
        if system:
            payload["messages"].append({
                "role": "system",
                "content": system,
            })

        # Build conversation messages
        for m in messages:
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue  # Already added above
            payload["messages"].append({
                "role": m["role"],
                "content": m["content"],
            })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=60,
        )

        if resp.status_code != 200:
            raise RuntimeError(
                f"xAI API error {resp.status_code}: {resp.text}"
            )

        for line in resp.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8")

            if decoded.startswith("data: "):
                data = decoded[len("data: "):]

                if data.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"]
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception:
                    continue
