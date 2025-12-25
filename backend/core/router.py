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
    "openai": {"general", "planning", "creative", "coding", "reasoning"},
    "anthropic": {"general", "coding", "reasoning", "planning", "creative"},
    "mock": {"general", "coding", "reasoning", "planning", "creative"},
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
    Step 2: Enhanced memory extraction with type detection.
    Returns (type, key, value) or (None, None, None).

    Types: fact, preference, goal, context
    """
    text_l = text.lower().strip()

    # Detect "remember that X is Y"
    if text_l.startswith("remember that"):
        content = text.strip()[len("remember that"):].strip()

        # Determine memory type
        memory_type = "fact"  # default
        if "prefer" in text_l or "like" in text_l:
            memory_type = "preference"
        elif "goal" in text_l or "working on" in text_l or "building" in text_l:
            memory_type = "goal"

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

            return memory_type, key, value

    # Detect "remember X" (store as context)
    if text_l.startswith("remember "):
        content = text.strip()[len("remember "):].strip()
        if content:
            # Use first few words as key
            words = content.split()
            key = " ".join(words[:3])
            return "context", key, content

    return None, None, None


def resolve_from_memory(text: str, memory: Optional[MemoryStore]) -> Optional[str]:
    """
    Step 2: Attempt to directly answer from structured memory.
    Returns an answer string if resolved, otherwise None.
    """
    if not memory or not text:
        return None

    text_l = text.lower().strip()

    # Try structured memory first
    relevant_memories = memory.get_relevant_memories("local", text, max_results=3)

    for mem in relevant_memories:
        key_l = mem['key'].lower()

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
            return f"Your {mem['key']} is {mem['value']}."

    # Legacy fallback to preferences table
    facts = memory.get_all("local") or {}
    for key, value in facts.items():
        key_l = key.lower()

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
    routing_explanation = []

    # Step 3: Check health status and circuit breaker
    health_summary = memory.get_provider_health_summary() if memory else {}

    def is_provider_healthy(provider_id):
        health = health_summary.get(provider_id, {})
        if health.get("circuit_breaker_open"):
            return False, "circuit breaker open (5+ consecutive failures)"
        if health.get("health_status") == "unhealthy":
            return False, f"unhealthy (failure rate: {health.get('failure_rate', 0)}%)"
        return True, None

    if forced_provider and provider_registry:
        provider_by_id = provider_registry.get(forced_provider)
        if provider_by_id:
            healthy, reason = is_provider_healthy(provider_by_id.get("id"))
            if healthy:
                selected_provider = provider_by_id
                routing_explanation.append(f"User forced provider: {forced_provider}")
            else:
                fallback_reason = f"Forced provider {forced_provider} unavailable: {reason}"
                routing_explanation.append(fallback_reason)
        else:
            provider_by_model = provider_registry.get_by_model(forced_provider)
            if provider_by_model:
                healthy, reason = is_provider_healthy(provider_by_model.get("id"))
                if healthy:
                    selected_provider = provider_by_model
                    routing_explanation.append(f"User forced model: {forced_provider}")
                else:
                    fallback_reason = f"Forced model {forced_provider} unavailable: {reason}"
                    routing_explanation.append(fallback_reason)

    if not selected_provider and memory:
        routed = memory.get_routing_provider("local", intent)
        if routed and provider_registry:
            routed_provider = provider_registry.get(routed)
            if routed_provider:
                healthy, reason = is_provider_healthy(routed)
                if healthy:
                    selected_provider = routed_provider
                    routing_explanation.append(f"User routing rule: {intent} → {routed}")
                else:
                    fallback_reason = f"Routing rule provider {routed} unavailable: {reason}"
                    routing_explanation.append(fallback_reason)

    if not selected_provider and provider_registry:
        preferred_type = INTENT_TO_PROVIDER_TYPE.get(intent, "openai")
        p = provider_registry.get_by_type(preferred_type)
        if p and p.get("api_key"):
            healthy, reason = is_provider_healthy(p.get("id"))
            if healthy:
                selected_provider = p
                routing_explanation.append(f"Intent match: {intent} → {preferred_type}")
            else:
                fallback_reason = f"{preferred_type} unhealthy: {reason}"
                routing_explanation.append(fallback_reason)
        else:
            fallback_reason = f"{preferred_type} skipped: missing api_key or provider disabled"
            routing_explanation.append(fallback_reason)

        if not selected_provider:
            other_type = "openai" if preferred_type == "anthropic" else "anthropic"
            p = provider_registry.get_by_type(other_type)
            if p and p.get("api_key"):
                healthy, reason = is_provider_healthy(p.get("id"))
                if healthy:
                    selected_provider = p
                    routing_explanation.append(f"Fallback to {other_type}")
                else:
                    fallback_reason = f"{fallback_reason}; {other_type} unhealthy: {reason}"
                    routing_explanation.append(f"{other_type} unhealthy: {reason}")
            else:
                fallback_reason = f"{fallback_reason}; {other_type} skipped: missing api_key or provider disabled"
                routing_explanation.append(f"{other_type} unavailable")

    # Enforce provider capability constraints and fallback if needed
    if selected_provider:
        if not provider_supports_intent(selected_provider, intent):
            fallback_reason = "provider does not support intent"
            routing_explanation.append(f"{selected_provider.get('type')} cannot handle {intent}")
            if provider_registry:
                current_type = selected_provider.get("type")
                other_type = "openai" if current_type == "anthropic" else "anthropic"
                p = provider_registry.get_by_type(other_type)
                if p and p.get("api_key") and provider_supports_intent(p, intent):
                    healthy, reason = is_provider_healthy(p.get("id"))
                    if healthy:
                        selected_provider = p
                        fallback_reason = None
                        routing_explanation.append(f"Switched to {other_type}")
                    else:
                        routing_explanation.append(f"{other_type} unhealthy: {reason}")
                        selected_provider = {
                            "id": "mock",
                            "type": "mock",
                            "api_key": None,
                            "base_url": None,
                            "model": None,
                            "fallback_reason": fallback_reason,
                        }
                        routing_explanation.append("Using mock provider (all providers unavailable)")
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
                    routing_explanation.append("Using mock provider (no capable providers)")
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
        routing_explanation.append("Using mock provider (no providers available)")

    if isinstance(selected_provider, dict):
        selected_provider["routing_explanation"] = " → ".join(routing_explanation)
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
            "routing_explanation": " → ".join(routing_explanation),
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
    # Explicit memory write handling (Step 2)
    # =============================
    if memory:
        memory_type, key, value = extract_explicit_memory(text)
        if key and value:
            # Use structured memory API
            memory.store_memory("local", memory_type, key, value)
            _debug(memory, "Explicit memory write", type=memory_type, key=key, value=value)

            # Return immediate confirmation
            return {
                "text": f"I'll remember that your {key} is {value}.",
                "provider": "memory",
                "model": None,
                "task_type": "memory_write",
                "fallback_reason": None,
            }

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

    # Step 3: Add request timing and error handling with fallback
    import time
    start_time = time.time()
    session_id = context.get("session_id", "default")

    try:
        raw = provider.chat(
            system=system_prompt,
            messages=messages,
        )
        latency_ms = int((time.time() - start_time) * 1000)

        # Log successful request
        logging.info(f"[ROUTER] Request successful for provider {provider_cfg['id']}, latency: {latency_ms}ms")
        if memory:
            logging.info(f"[ROUTER] Updating health for provider {provider_cfg['id']}")
            memory.update_provider_health(provider_cfg["id"], success=True, latency_ms=latency_ms)
            # Estimate tokens (rough approximation based on character count)
            input_tokens = (len(system_prompt) + sum(len(m.get("content", "")) for m in messages)) // 4
            output_tokens = 0  # Will be updated after response
            memory.log_request(
                session_id=session_id,
                provider_id=provider_cfg["id"],
                intent=intent,
                success=True,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=0,
            )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)

        # Always log provider failures
        logging.error(f"[ROUTER] Provider {provider_cfg['id']} failed: {error_msg}")
        _debug(memory, f"Provider {provider_cfg['id']} failed", error=error_msg)

        # Log failure
        if memory:
            memory.update_provider_health(provider_cfg["id"], success=False, latency_ms=latency_ms)
            memory.log_request(
                session_id=session_id,
                provider_id=provider_cfg["id"],
                intent=intent,
                success=False,
                latency_ms=latency_ms,
                error_message=error_msg,
            )

        # Step 3: Smart fallback - try alternative provider
        _debug(memory, "Attempting fallback to alternative provider")

        # Select alternative provider (excluding the failed one)
        alternative_cfg = select_provider(intent, memory, forced_provider=None)

        if alternative_cfg["id"] != provider_cfg["id"] and alternative_cfg["id"] != "mock":
            _debug(memory, f"Fallback to {alternative_cfg['id']}")
            provider = instantiate_provider(alternative_cfg)

            try:
                raw = provider.chat(
                    system=system_prompt,
                    messages=messages,
                )
                fallback_latency = int((time.time() - start_time) * 1000)

                if memory:
                    memory.update_provider_health(alternative_cfg["id"], success=True, latency_ms=fallback_latency)

                # Update metadata to reflect fallback
                meta["provider"] = alternative_cfg["id"]
                meta["model"] = alternative_cfg["model"]
                meta["fallback_reason"] = f"Primary provider failed: {error_msg[:100]}"
                meta["routing"]["fallback_used"] = True

            except Exception as fallback_error:
                _debug(memory, f"Fallback also failed", error=str(fallback_error))
                if memory:
                    memory.update_provider_health(alternative_cfg["id"], success=False)

                # Return error message instead of raising
                return {
                    "text": f"Error: All providers failed. Primary: {error_msg}. Fallback: {str(fallback_error)}",
                    "provider": "error",
                    "model": None,
                    "task_type": intent,
                    "fallback_reason": "all providers failed",
                    "routing": routing_decision,
                }
        else:
            # No alternative available
            return {
                "text": f"Error: Provider failed and no fallback available. {error_msg}",
                "provider": "error",
                "model": None,
                "task_type": intent,
                "fallback_reason": "no fallback available",
                "routing": routing_decision,
            }

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