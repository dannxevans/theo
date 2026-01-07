import requests
import json


class PerplexityProvider:
    """
    Perplexity AI provider adapter for THEO with native search capability.

    Features:
    - Supports Perplexity Sonar models with real-time web search
    - Returns web-grounded responses with citations
    - Compatible with THEO's provider interface
    - Supports both chat and streaming modes

    Models:
    - llama-3.1-sonar-small-128k-online: Fast, cost-effective search
    - llama-3.1-sonar-large-128k-online: Balanced performance and accuracy
    - llama-3.1-sonar-huge-128k-online: Maximum accuracy and depth
    """

    name = "perplexity"
    maxContextTokens = 128000
    costTier = "medium"
    supportsStreaming = True

    def __init__(self, api_key=None, base_url=None, model=None, search_mode=True):
        """
        Initialize Perplexity provider.

        Args:
            api_key: Perplexity API key (required)
            base_url: API endpoint (default: https://api.perplexity.ai)
            model: Model to use (default: llama-3.1-sonar-small-128k-online)
            search_mode: Enable web-grounded search (default: True)
        """
        self.api_key = api_key
        self.base_url = base_url or "https://api.perplexity.ai"
        self.model = model or "llama-3.1-sonar-small-128k-online"
        self.search_mode = search_mode

        if not self.api_key:
            raise ValueError("PerplexityProvider requires an api_key")

    def chat(self, **kwargs):
        """
        Execute a chat completion with Perplexity.

        Parameters:
        - model: string (model identifier)
        - system: system prompt string
        - messages: list of {role, content}
        - temperature: float (default: 0.2)
        - search_domain_filter: list of domains to restrict search (optional)
        - return_citations: bool (default: True for search mode)

        Returns:
        - str (assistant response text)

        Note:
        - Citations are stored in metadata but not included in text response
        - Use search_mode=True for web-grounded responses
        """

        model = kwargs.get("model") or getattr(self, "model", None) or "llama-3.1-sonar-small-128k-online"
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)
        search_domain_filter = kwargs.get("search_domain_filter", [])
        return_citations = kwargs.get("return_citations", self.search_mode)

        if kwargs.get("debug"):
            print("[DEBUG][Perplexity] model =", model)
            print("[DEBUG][Perplexity] search_mode =", self.search_mode)
            print("[DEBUG][Perplexity] system injected =", bool(system))
            if system:
                print("[DEBUG][Perplexity] system preview =", system[:200])

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "temperature": temperature,
            "messages": [],
        }

        # Add search configuration if enabled
        if self.search_mode:
            payload["return_citations"] = return_citations
            payload["country"] = "GB"  # UK country code for regional search results
            if search_domain_filter:
                payload["search_domain_filter"] = search_domain_filter

        # Build conversation messages with proper alternation
        # Perplexity requires strict user/assistant message alternation
        filtered_messages = []
        num_messages = len(messages)

        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue

            role = m.get("role")
            content = m.get("content")

            # Apply context injection for last user message if needed
            if system and role == "user" and idx == num_messages - 1:
                if not self.search_mode:
                    # For non-search mode: include context (standard chat behavior)
                    content = (
                        "Context:\n"
                        f"{system}\n\n"
                        f"Query: {content}"
                    )
                # For search mode: keep it clean, no context injection

            # Ensure message alternation: merge consecutive messages with same role
            if filtered_messages and filtered_messages[-1]["role"] == role:
                # Merge with previous message
                filtered_messages[-1]["content"] += "\n\n" + content
            else:
                filtered_messages.append({
                    "role": role,
                    "content": content,
                })

        # Ensure we start with user message (Perplexity requirement)
        if filtered_messages and filtered_messages[0]["role"] != "user":
            # Remove leading assistant messages
            while filtered_messages and filtered_messages[0]["role"] == "assistant":
                filtered_messages.pop(0)

        payload["messages"] = filtered_messages

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Perplexity API error {resp.status_code}: {resp.text}"
                )

            data = resp.json()

            try:
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)

                # Extract citations if available
                citations = data.get("citations", [])

            except (KeyError, IndexError) as e:
                raise RuntimeError(f"Unexpected Perplexity response: {data}")

            # Store usage data and citations for router to access
            self._last_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "citations": citations,
                "web_grounded": self.search_mode
            }

            return text

        except requests.exceptions.Timeout:
            raise RuntimeError("Perplexity API request timed out (30s)")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Perplexity API request failed: {str(e)}")

    def stream_chat(self, **kwargs):
        """
        Execute a streaming chat completion with Perplexity.

        Yields:
        - str (text chunks as they arrive)

        Note:
        - Same parameters as chat() method
        - Citations available at end of stream
        """

        model = kwargs.get("model") or getattr(self, "model", None) or "llama-3.1-sonar-small-128k-online"
        system = kwargs.get("system_prompt") or kwargs.get("system")
        messages = kwargs.get("messages") or []
        temperature = kwargs.get("temperature", 0.2)
        search_domain_filter = kwargs.get("search_domain_filter", [])
        return_citations = kwargs.get("return_citations", self.search_mode)

        if kwargs.get("debug"):
            print("[DEBUG][Perplexity] Streaming mode")
            print("[DEBUG][Perplexity] model =", model)
            print("[DEBUG][Perplexity] search_mode =", self.search_mode)

        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": model,
            "temperature": temperature,
            "stream": True,
            "messages": [],
        }

        # Add search configuration if enabled
        if self.search_mode:
            payload["return_citations"] = return_citations
            payload["country"] = "GB"  # UK country code for regional search results
            if search_domain_filter:
                payload["search_domain_filter"] = search_domain_filter

        # Build conversation messages with proper alternation
        # Perplexity requires strict user/assistant message alternation
        filtered_messages = []
        num_messages = len(messages)

        for idx, m in enumerate(messages):
            if not m.get("content"):
                continue
            if m.get("role") == "system":
                continue

            role = m.get("role")
            content = m.get("content")

            # Apply context injection for last user message if needed
            if system and role == "user" and idx == num_messages - 1:
                if self.search_mode:
                    # For search: add UK location bias for relevant results
                    uk_context = "Search from UK perspective: "
                    content = uk_context + content
                else:
                    # For non-search mode: include context (standard chat behavior)
                    content = (
                        "Context:\n"
                        f"{system}\n\n"
                        f"Query: {content}"
                    )

            # Ensure message alternation: merge consecutive messages with same role
            if filtered_messages and filtered_messages[-1]["role"] == role:
                # Merge with previous message
                filtered_messages[-1]["content"] += "\n\n" + content
            else:
                filtered_messages.append({
                    "role": role,
                    "content": content,
                })

        # Ensure we start with user message (Perplexity requirement)
        if filtered_messages and filtered_messages[0]["role"] != "user":
            # Remove leading assistant messages
            while filtered_messages and filtered_messages[0]["role"] == "assistant":
                filtered_messages.pop(0)

        payload["messages"] = filtered_messages

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                stream=True,
                timeout=30,
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Perplexity API error {resp.status_code}: {resp.text}"
                )

            # Track citations and usage from streaming response
            citations = []
            input_tokens = 0
            output_tokens = 0

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

                        # Extract citations if present in this chunk
                        if "citations" in chunk:
                            citations = chunk["citations"]

                        # Extract usage if present
                        if "usage" in chunk:
                            usage = chunk["usage"]
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)

                        # Yield content
                        delta = chunk["choices"][0]["delta"]
                        content = delta.get("content")
                        if content:
                            yield content
                    except Exception:
                        continue

            # Store usage data and citations for router to access
            self._last_usage = {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "citations": citations,
                "web_grounded": self.search_mode
            }

        except requests.exceptions.Timeout:
            raise RuntimeError("Perplexity API streaming request timed out (30s)")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Perplexity API streaming request failed: {str(e)}")
