import requests
import json


class GoogleProvider:
    """
    Google Gemini provider adapter for THEO.

    Notes:
    - Supports any model string provided by the frontend (no hardcoding).
    - Uses Google's generativelanguage API format (different from OpenAI).
    - Role mapping: 'assistant' -> 'model', 'user' -> 'user'.
    - Matches the same interface shape as other providers.
    """

    name = "google"
    maxContextTokens = 128000
    costTier = "low"
    supportsStreaming = True

    def __init__(self, api_key=None, base_url=None, model=None):
        self.api_key = api_key
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.model = model

        if not self.api_key:
            raise ValueError("GoogleProvider requires an api_key")

    def chat(self, **kwargs):
        """
        Execute a chat completion against Google Gemini.

        Parameters:
        - model: string (passed directly from frontend config)
        - system: system prompt string
        - messages: list of {role, content}
        - temperature: float

        Returns:
        - str (assistant text only)
        """

        model = kwargs.get("model") or getattr(self, "model", None)
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)

        if not model:
            raise ValueError("GoogleProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][Gemini] model =", model)
            print("[DEBUG][Gemini] system injected =", bool(system))
            if system:
                print("[DEBUG][Gemini] system preview =", system[:200])

        url = f"{self.base_url}/models/{model}:generateContent?key={self.api_key}"

        # Build Gemini-format messages
        gemini_messages = []
        num_messages = len(messages)

        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue

            # Map roles: assistant -> model, user -> user
            role = "model" if m.get("role") == "assistant" else "user"

            # Detect the final user message (the current turn)
            if (
                system
                and m.get("role") == "user"
                and idx == num_messages - 1
            ):
                # Prepend authoritative persistent memory to the user message content
                content = (
                    "IMPORTANT PERSISTENT CONTEXT (AUTHORITATIVE):\n"
                    f"{system}\n\n"
                    "You must use this information when answering questions.\n\n"
                    f"{m['content']}"
                )
            else:
                content = m["content"]

            gemini_messages.append({
                "role": role,
                "parts": [{"text": content}]
            })

        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
            }
        }

        headers = {
            "Content-Type": "application/json",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Gemini API error {resp.status_code}: {resp.text}"
            )

        data = resp.json()

        try:
            # Gemini response format: candidates[0].content.parts[0].text
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            # Gemini usage format: usageMetadata
            usage = data.get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount", 0)
            output_tokens = usage.get("candidatesTokenCount", 0)
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected Gemini response: {data}")

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
            raise ValueError("GoogleProvider requires a model to be specified")

        if kwargs.get("debug"):
            print("[DEBUG][Gemini] model =", model)
            print("[DEBUG][Gemini] system injected =", bool(system))
            if system:
                print("[DEBUG][Gemini] system preview =", system[:200])

        url = f"{self.base_url}/models/{model}:streamGenerateContent?key={self.api_key}"

        # Build Gemini-format messages
        gemini_messages = []
        num_messages = len(messages)

        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue

            # Map roles: assistant -> model, user -> user
            role = "model" if m.get("role") == "assistant" else "user"

            # Detect the final user message (the current turn)
            if (
                system
                and m.get("role") == "user"
                and idx == num_messages - 1
            ):
                # Prepend authoritative persistent memory to the user message content
                content = (
                    "IMPORTANT PERSISTENT CONTEXT (AUTHORITATIVE):\n"
                    f"{system}\n\n"
                    "You must use this information when answering questions.\n\n"
                    f"{m['content']}"
                )
            else:
                content = m["content"]

            gemini_messages.append({
                "role": role,
                "parts": [{"text": content}]
            })

        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
            }
        }

        headers = {
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
                f"Gemini API error {resp.status_code}: {resp.text}"
            )

        for line in resp.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8")

            try:
                chunk = json.loads(decoded)
                # Gemini streaming format: candidates[0].content.parts[0].text
                text = chunk["candidates"][0]["content"]["parts"][0]["text"]
                if text:
                    yield text
            except Exception:
                continue
