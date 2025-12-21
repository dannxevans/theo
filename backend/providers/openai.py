import requests
import json


class OpenAIProvider:
    """
    OpenAI provider adapter for THEO.

    Notes:
    - Supports any model string provided by the frontend (no hardcoding).
    - Non-streaming implementation for stability.
    - Matches the same interface shape as other providers.
    """

    name = "openai"
    maxContextTokens = 128000
    costTier = "medium"
    supportsStreaming = False

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or "https://api.openai.com/v1"
        self.model = model

        if not self.api_key:
            raise ValueError("OpenAIProvider requires an api_key")

    def chat(self, **kwargs):
        """
        Execute a chat completion against OpenAI.

        Parameters:
        - model: string (passed directly from frontend config)
        - system: system prompt string
        - messages: list of {role, content}
        - temperature: float

        Returns:
        - str (assistant text only)
        """

        model = kwargs.get("model") or getattr(self, "model", None) or "gpt-4o-mini"
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if kwargs.get("debug"):
            print("[DEBUG][OpenAI] model =", model)
            print("[DEBUG][OpenAI] system injected =", bool(system))
            if system:
                print("[DEBUG][OpenAI] system preview =", system[:200])

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

        resp = requests.post(url, headers=headers, json=payload, timeout=60)

        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenAI API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected OpenAI response: {data}")

        return text

    def chat_stream(self, **kwargs):
        model = kwargs.get("model") or getattr(self, "model", None) or "gpt-4o-mini"
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if kwargs.get("debug"):
            print("[DEBUG][OpenAI] model =", model)
            print("[DEBUG][OpenAI] system injected =", bool(system))
            if system:
                print("[DEBUG][OpenAI] system preview =", system[:200])

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
                f"OpenAI API error {resp.status_code}: {resp.text}"
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