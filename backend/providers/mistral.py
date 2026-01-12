import requests
import json
import logging


def _is_debug_enabled():
    """Check if debug logging is enabled in user preferences."""
    try:
        from core.memory import MemoryStore
        memory = MemoryStore()
        prefs = memory.get_all(DEFAULT_USER_ID)
        return str(prefs.get("debug_enabled", "false")).lower() == "true"
    except Exception:
        return False


class MistralProvider:
    """
    Mistral AI provider adapter for THEO.

    Notes:
    - Supports any model string provided by the frontend (no hardcoding).
    - OpenAI-compatible API format.
    - Matches the same interface shape as other providers.
    """

    name = "mistral"
    maxContextTokens = 128000
    costTier = "medium"
    supportsStreaming = True

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.mistral.ai/v1"
        self.model = model

        if not self.api_key:
            raise ValueError("MistralProvider requires an api_key")

    def chat(self, system, messages, **kwargs):
        """
        Execute a chat completion against Mistral AI.

        Parameters:
        - system: system prompt string
        - messages: list of {role, content}
        - **kwargs: Additional options (model, temperature, debug, etc.)

        Returns:
        - str (assistant text only)
        """

        model = kwargs.get("model") or getattr(self, "model", None)
        temperature = kwargs.get("temperature", 0.2)

        if not model:
            raise ValueError("MistralProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][Mistral] model =", model)
            print("[DEBUG][Mistral] system injected =", bool(system))
            if system:
                print("[DEBUG][Mistral] system preview =", system[:200])

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [],
        }

        # Build conversation messages, injecting authoritative memory before the current user message
        num_messages = len(messages)
        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue
            # Detect the final user message (the current turn)
            if (
                system
                and m.get("role") == "user"
                and idx == num_messages - 1
            ):
                # Prepend authoritative persistent memory to the user message content
                payload["messages"].append({
                    "role": m["role"],
                    "content": (
                        "IMPORTANT PERSISTENT CONTEXT (AUTHORITATIVE):\n"
                        f"{system}\n\n"
                        "You must use this information when answering questions.\n\n"
                        f"{m['content']}"
                    ),
                })
            else:
                payload["messages"].append({
                    "role": m["role"],
                    "content": m["content"],
                })

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if _is_debug_enabled():
            logging.info(f"[DEBUG][Mistral] Sending request to {url} with model={model}")

        resp = requests.post(url, headers=headers, json=payload, timeout=60)

        if _is_debug_enabled():
            logging.info(f"[DEBUG][Mistral] Response status: {resp.status_code}")

        if resp.status_code != 200:
            logging.error(f"[Mistral][ERROR] Error response: {resp.text}")
            raise RuntimeError(
                f"Mistral API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()

        try:
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Mistral response: {data}")

        # Store usage data in instance for router to access
        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens
        }

        return text

    def stream_chat(self, **kwargs):
        model = kwargs.get("model") or getattr(self, "model", None)
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if not model:
            raise ValueError("MistralProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][Mistral] model =", model)
            print("[DEBUG][Mistral] system injected =", bool(system))
            if system:
                print("[DEBUG][Mistral] system preview =", system[:200])

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "temperature": temperature,
            "stream": True,
            "messages": [],
        }

        # Build conversation messages, injecting authoritative memory before the current user message
        num_messages = len(messages)
        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue
            # Detect the final user message (the current turn)
            if (
                system
                and m.get("role") == "user"
                and idx == num_messages - 1
            ):
                # Prepend authoritative persistent memory to the user message content
                payload["messages"].append({
                    "role": m["role"],
                    "content": (
                        "IMPORTANT PERSISTENT CONTEXT (AUTHORITATIVE):\n"
                        f"{system}\n\n"
                        "You must use this information when answering questions.\n\n"
                        f"{m['content']}"
                    ),
                })
            else:
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
                f"Mistral API error {resp.status_code}: {resp.text}"
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
