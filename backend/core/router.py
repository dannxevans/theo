from core.memory import MemoryStore
from core.context import ContextManager
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

PROVIDER_CAPABILITIES = {
    "openai": {"general", "planning", "creative"},
    "anthropic": {"coding", "reasoning"},
    "mock": {"general"},
}

provider_registry: Optional[ProviderRegistry] = None
context_manager: Optional[ContextManager] = None


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


def set_context_manager(manager: ContextManager):
    global context_manager
    context_manager = manager


def classify_intent(text: str) -> str:
    """
    Deterministic intent classification.
    Order matters: more specific intents must win.
    """
    if not text:
        return "general"

    text_l = text.lower()

    # Explicit coding / technical tasks
    if any(k in text_l for k in [
        "code", "coding", "script", "function",
        "python", "javascript", "js", "api", "bug", "error"
    ]):
        return "coding"

    # Deep explanation / analysis
    if any(k in text_l for k in [
        "why", "how does", "explain", "analyze",
        "analysis", "reasoning", "logic"
    ]):
        return "reasoning"

    # Planning / structuring work
    if any(k in text_l for k in [
        "plan", "planning", "roadmap", "schedule",
        "organize", "design", "steps", "approach"
    ]):
        return "planning"

    # Creative generation
    if any(k in text_l for k in [
        "write", "story", "poem", "creative",
        "imagine", "fiction", "lyrics"
    ]):
        return "creative"

    return "general"


def provider_supports_intent(provider_cfg, intent: str) -> bool:
    ptype = provider_cfg.get("type")
    allowed = PROVIDER_CAPABILITIES.get(ptype)
    if not allowed:
        return False
    return intent in allowed


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
    selected_provider = None

    if forced_provider and provider_registry:
        provider_by_id = provider_registry.get(forced_provider)
        if provider_by_id:
            selected_provider = provider_by_id
        else:
            provider_by_model = provider_registry.get_by_model(forced_provider)
            if provider_by_model:
                selected_provider = provider_by_model

    if not selected_provider and memory:
        routed = memory.get_routing_provider("local", intent)
        if routed and provider_registry:
            routed_provider = provider_registry.get(routed)
            if routed_provider:
                selected_provider = routed_provider

    if not selected_provider and provider_registry:
        preferred_type = INTENT_TO_PROVIDER_TYPE.get(intent, "openai")
        p = provider_registry.get_by_type(preferred_type)
        if p and p.get("api_key"):
            selected_provider = p
        else:
            fallback_reason = f"{preferred_type} skipped: missing api_key or provider disabled"
            other_type = "openai" if preferred_type == "anthropic" else "anthropic"
            p = provider_registry.get_by_type(other_type)
            if p and p.get("api_key"):
                selected_provider = p
            else:
                fallback_reason = f"{fallback_reason}; {other_type} skipped: missing api_key or provider disabled"

    # Enforce provider capability constraints and fallback if needed
    if selected_provider:
        if not provider_supports_intent(selected_provider, intent):
            fallback_reason = "provider does not support intent"
            if provider_registry:
                current_type = selected_provider.get("type")
                other_type = "openai" if current_type == "anthropic" else "anthropic"
                p = provider_registry.get_by_type(other_type)
                if p and p.get("api_key") and provider_supports_intent(p, intent):
                    selected_provider = p
                    fallback_reason = None
                else:
                    # no provider supports intent, fall back to mock
                    selected_provider = {
                        "id": "mock",
                        "type": "mock",
                        "api_key": None,
                        "base_url": None,
                        "model": None,
                        "fallback_reason": fallback_reason,
                    }
        else:
            selected_provider["fallback_reason"] = fallback_reason
    else:
        selected_provider = {
            "id": "mock",
            "type": "mock",
            "api_key": None,
            "base_url": None,
            "model": None,
            "fallback_reason": fallback_reason,
        }

    if isinstance(selected_provider, dict):
        return selected_provider
    else:
        # convert to dict if it's a provider object
        return {
            "id": selected_provider.get("id"),
            "type": selected_provider.get("type"),
            "api_key": selected_provider.get("api_key"),
            "base_url": selected_provider.get("base_url"),
            "model": selected_provider.get("model"),
            "fallback_reason": selected_provider.get("fallback_reason", fallback_reason),
        }


def instantiate_provider(provider_cfg):
    ptype = provider_cfg["type"]
    if ptype == "anthropic":
        return AnthropicProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
        )
    if ptype == "openai":
        return OpenAIProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
        )
    return MockProvider()


def route_request(context: dict, stream: bool = False):
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

    _debug(memory, "Final intent locked", intent=intent)
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

    provider_cfg = select_provider(intent, memory, forced)

    # Step 1.5: Add routing decision audit record
    import json

    routing_decision = {
        "intent": intent,
        "forced_provider": forced,
        "selected_provider_id": provider_cfg.get("id"),
        "selected_provider_type": provider_cfg.get("type"),
        "model": provider_cfg.get("model"),
        "fallback_reason": provider_cfg.get("fallback_reason"),
    }
    if memory:
        memory.remember(
            "local",
            "last_routing_decision",
            json.dumps(routing_decision),
        )

    provider = instantiate_provider(provider_cfg)

    fallback_reason = provider_cfg.get("fallback_reason", None)
    if fallback_reason:
        _debug(memory, "Provider fallback", reason=fallback_reason)

    _debug(memory, f"Selected provider: {provider_cfg['id']}")


    meta = {
        "provider": provider_cfg["id"],
        "model": provider_cfg["model"],
        "task_type": intent,
        "fallback_reason": fallback_reason,
        "routing": routing_decision,
    }

    _debug(memory, f"Calling provider.chat with model={provider_cfg['model']}")

    if not context_manager:
        raise RuntimeError("ContextManager not configured")

    context_obj = context_manager.build_context(
        session_id=context.get("session_id"),
        user_text=text,
    )
    system_prompt = context_obj["system"]
    messages = context_obj["messages"]

    raw = provider.chat(
        system=system_prompt,
        messages=messages,
    )

    if stream:
        def stream_generator():
            full_text = []

            for chunk in raw:
                if isinstance(chunk, dict):
                    token = chunk.get("token") or chunk.get("text")
                else:
                    token = chunk

                if token:
                    full_text.append(token)
                    yield {
                        "token": token
                    }

            # Persist full response
            final_text = "".join(full_text)
            if memory:
                memory.append("local", text, final_text)

            # ⬇️ THIS IS THE IMPORTANT PART ⬇️
            yield {
                "event": "end",
                "provider": meta["provider"],
                "model": meta["model"],
                "task_type": meta["task_type"],
                "fallback_reason": meta["fallback_reason"],
                "routing": meta["routing"],
            }

        return stream_generator()

    text_out = raw.get("text") if isinstance(raw, dict) else raw

    _debug(memory, f"Response length: {len(text_out) if isinstance(text_out, str) else 'unknown'}")

    return {
        "text": text_out,
        "provider": meta["provider"],
        "model": meta["model"],
        "task_type": meta["task_type"],
        "fallback_reason": meta["fallback_reason"],
        "routing": meta["routing"],
    }