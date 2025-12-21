from core.memory import MemoryStore
from typing import Optional, Iterable
from providers.mock import MockProvider
from providers.anthropic import AnthropicProvider
from providers.openai import OpenAIProvider
from core.provider_registry import ProviderRegistry
import logging

INTENT_TO_PROVIDER_TYPE = {
    "coding": "anthropic",
    "general": "openai",
    "planning": "openai",
    "reasoning": "anthropic",
    "creative": "openai",
}

provider_registry: Optional[ProviderRegistry] = None


def _debug(memory: Optional[MemoryStore], msg: str, **context):
    try:
        debug_enabled = False
        if memory:
            prefs = memory.get_routing_preferences("local")
            value = prefs.get("debug_enabled")
            if isinstance(value, str):
                debug_enabled = value.lower() == "true"
            elif isinstance(value, bool):
                debug_enabled = value
        if debug_enabled:
            ctx_str = ""
            if context:
                ctx_str = " | " + " ".join(f"{k}={v}" for k, v in context.items())
            logging.info(f"[THEO][ROUTER][DEBUG] {msg}{ctx_str}")
    except Exception:
        pass


def set_provider_registry(registry: ProviderRegistry):
    global provider_registry
    provider_registry = registry


def classify_intent(text: str) -> str:
    text_l = text.lower()
    if any(k in text_l for k in ["code", "script", "python", "javascript"]):
        return "coding"
    if any(k in text_l for k in ["plan", "planning", "schedule", "organize", "design"]):
        return "planning"
    if any(k in text_l for k in ["why", "how", "reason", "explain", "analyze"]):
        return "reasoning"
    if any(k in text_l for k in ["write", "story", "poem", "creative", "imagine"]):
        return "creative"
    return "general"


def extract_explicit_memory(text: str):
    """
    Detect explicit 'remember that X is Y' style instructions.
    Returns (key, value) or (None, None).
    """
    text_l = text.lower().strip()

    if text_l.startswith("remember that"):
        content = text.strip()[len("remember that"):].strip()
        # naive split: "<thing> is <value>"
        if " is " in content:
            key, value = content.split(" is ", 1)

            key = key.strip()
            value = value.strip()

            # Normalize keys like "my project" -> "project"
            if key.lower().startswith("my "):
                key = key[3:].strip()

            # Normalize values like "called Atlas" -> "Atlas"
            if value.lower().startswith("called "):
                value = value[7:].strip()

            return key, value

    return None, None


def resolve_from_memory(text: str, memory: Optional[MemoryStore]) -> Optional[str]:
    """
    Attempt to directly answer the user's question from stored memory.
    Returns an answer string if resolved, otherwise None.
    """
    if not memory or not text:
        return None

    text_l = text.lower().strip()
    facts = memory.get_all("local") or {}

    # Simple generic recall patterns
    for key, value in facts.items():
        key_l = key.lower()

        # Examples:
        # "what is my project called"
        # "what is my X"
        if (
            f"what is my {key_l}" in text_l
            or f"what's my {key_l}" in text_l
            or f"what is the {key_l}" in text_l
            or f"what is my {key_l} called" in text_l
            or f"what's my {key_l} called" in text_l
        ):
            return f"Your {key} is {value}."

    return None


def select_provider(intent: str, memory: Optional[MemoryStore], forced_provider: Optional[str] = None):
    fallback_reason = None

    if not forced_provider and memory:
        routed = memory.get_routing_provider("local", intent)
        if routed:
            forced_provider = routed

    # Forced provider takes precedence over routing heuristics
    if forced_provider and provider_registry:
        p = provider_registry.get(forced_provider)
        if not p:
            fallback_reason = f"{forced_provider} skipped: provider not found"
        elif not p.get("api_key") and p.get("type") != "mock":
            fallback_reason = f"{forced_provider} skipped: missing api_key"
        else:
            try:
                provider_type = p.get("type")

                if provider_type == "anthropic":
                    return AnthropicProvider(
                        api_key=p.get("api_key"),
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
                if provider_type == "openai":
                    return OpenAIProvider(
                        api_key=p.get("api_key"),
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
                if provider_type == "mock":
                    return MockProvider()
            except Exception as e:
                fallback_reason = f"{forced_provider} skipped: {str(e)}"

    if provider_registry:
        preferred_type = INTENT_TO_PROVIDER_TYPE.get(intent, "openai")
        # Try preferred provider first
        p = provider_registry.get_by_type(preferred_type)
        if p and p.get("api_key"):
            try:
                if preferred_type == "anthropic":
                    return AnthropicProvider(
                        api_key=p["api_key"],
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
                if preferred_type == "openai":
                    return OpenAIProvider(
                        api_key=p["api_key"],
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
            except Exception as e:
                fallback_reason = f"{preferred_type} skipped: {str(e)}"
        else:
            fallback_reason = f"{preferred_type} skipped: missing api_key or provider disabled"

        # Fallback to the other provider type
        other_type = "openai" if preferred_type == "anthropic" else "anthropic"
        p = provider_registry.get_by_type(other_type)
        if p and p.get("api_key"):
            try:
                if other_type == "anthropic":
                    return AnthropicProvider(
                        api_key=p["api_key"],
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
                if other_type == "openai":
                    return OpenAIProvider(
                        api_key=p["api_key"],
                        base_url=p.get("base_url"),
                        model=p.get("model"),
                    )
            except Exception as e:
                fallback_reason = f"{other_type} skipped: {str(e)}"

    mp = MockProvider()
    mp.fallback_reason = fallback_reason
    return mp


def route_request(context: dict):
    text = context.get("text", "")
    memory = context.get("memory")

    # =============================
    # Memory-first resolution
    # =============================
    answer = resolve_from_memory(text, memory)
    if answer:
        _debug(memory, "Resolved directly from memory", answer=answer)
        return {
            "text": answer,
            "provider": "memory",
            "model": None,
            "task_type": "memory",
            "fallback_reason": None,
        }

    intent = classify_intent(text)
    forced = context.get("forced_provider")

    _debug(memory, f"Incoming text: {text}")
    _debug(memory, f"Classified intent: {intent}")
    _debug(memory, f"Forced provider: {forced}")

    # =============================
    # Explicit memory write handling
    # =============================
    if memory:
        key, value = extract_explicit_memory(text)
        if key and value:
            memory.remember("local", key, value)
            _debug(memory, "Explicit memory write", key=key, value=value)

    _debug(memory, "Selecting provider...")

    provider = select_provider(intent, memory, forced)

    fallback_reason = getattr(provider, "fallback_reason", None)
    if fallback_reason:
        _debug(memory, "Provider fallback", reason=fallback_reason)

    _debug(memory, f"Selected provider: {provider.name}")

    system_prompt = "You are THEO, a professional personal AI assistant."
    messages = [{"role": "user", "content": text}]

    meta = {
        "provider": provider.name,
        "model": getattr(provider, "model", None),
        "task_type": intent,
        "fallback_reason": getattr(provider, "fallback_reason", None),
    }

    _debug(memory, f"Calling provider.chat with model={getattr(provider, 'model', None)}")

    raw = provider.chat(
        system=system_prompt,
        messages=messages,
    )

    text_out = raw.get("text") if isinstance(raw, dict) else raw

    _debug(memory, f"Response length: {len(text_out) if isinstance(text_out, str) else 'unknown'}")

    return {
        "text": text_out,
        "provider": meta["provider"],
        "model": meta["model"],
        "task_type": meta["task_type"],
        "fallback_reason": meta["fallback_reason"],
    }