from core.memory import MemoryStore
from core.context import ContextManager
from typing import Optional, Iterable
from providers.mock import MockProvider
from providers.anthropic import AnthropicProvider
from providers.openai import OpenAIProvider
from core.provider_registry import ProviderRegistry
from core.action_router import ActionRouter
from actions.action_registry import ActionProviderRegistry
from core.intent_classifier import classify_intent_enhanced
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
action_router: Optional[ActionRouter] = None
action_registry: Optional[ActionProviderRegistry] = None


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


def set_action_router(router: ActionRouter):
    global action_router
    action_router = router


def set_action_registry(registry: ActionProviderRegistry):
    global action_registry
    action_registry = registry


def classify_intent(text: str, memory: Optional[MemoryStore] = None, user_id: Optional[int] = None) -> str:
    """
    Dynamic intent classification based on user-defined intents.
    Checks action intents first (highest priority), then user-defined intents.

    Args:
        text: User's input text
        memory: Optional MemoryStore instance
        user_id: Optional user ID for checking pending confirmations
    """
    if not text:
        return "general"

    text_l = text.lower()

    # =============================
    # Priority 1: Action Intents
    # =============================
    # These take precedence over conversation intents
    # IMPORTANT: Check write actions before read actions to avoid false positives
    # e.g., "add to calendar" should match book_appointment, not read_calendar

    # Confirmation keywords (highest priority - process before other actions)
    CONFIRMATION_KEYWORDS = {
        "approve_confirmation": ["approve", "yes", "confirm", "ok", "looks good", "go ahead", "do it"],
        "reject_confirmation": ["reject", "no", "don't", "nevermind", "never mind"],
    }

    # Calendar context words - must be present with generic verbs
    CALENDAR_CONTEXT = ["calendar", "diary", "schedule", "appointment", "meeting", "lunch", "dinner",
                        "breakfast", "call", "event", "reminder", "today", "tomorrow", "monday", "tuesday",
                        "wednesday", "thursday", "friday", "saturday", "sunday", "am", "pm"]

    # Write-action keywords (high priority)
    # Email keywords checked FIRST to avoid false matches with generic words
    EMAIL_KEYWORDS = ["send email", "draft email", "compose", "write email", "email to", "send an email", "reply to", "reply", "respond to"]

    WRITE_ACTION_KEYWORDS = {
        "book_appointment": ["schedule", "book", "set up", "arrange", "appointment", "schedule me", "reserve"],
        "update_appointment": ["move", "reschedule", "change time"],
        "cancel_appointment": ["cancel", "delete", "remove"],
        "compose_email": EMAIL_KEYWORDS,
    }

    # Generic appointment words that need calendar context
    APPOINTMENT_GENERIC_KEYWORDS = {
        "update_appointment": ["update"],
    }

    # Read-action keywords (lower priority)
    READ_ACTION_KEYWORDS = {
        "read_calendar": ["calendar", "availability", "available", "free", "busy",
                         "when am i", "what's on", "whats on", "schedule for", "flight", "train", "travel"],
        "read_email": ["my emails", "my email", "inbox", "unread", "check email", "email summary", "what emails", "any emails"],
    }

    # First check for confirmation intents (approve/reject)
    # Only trigger if there are pending confirmations AND specific keywords match
    if memory and user_id:
        from core.confirmation_manager import ConfirmationManager
        import logging
        import re

        conf_manager = ConfirmationManager(memory)

        # Only check confirmation keywords if there are pending confirmations
        pending = conf_manager.get_pending_confirmations(user_id)
        logging.info(f"[ROUTER] user_id={user_id}, text='{text}', text_l='{text_l}', pending confirmations: {len(pending) if pending else 0}")

        if pending:
            logging.info(f"[ROUTER] Checking confirmation keywords against text: '{text_l}'")
            for confirmation_intent, keywords in CONFIRMATION_KEYWORDS.items():
                logging.info(f"[ROUTER] Checking intent '{confirmation_intent}' with keywords: {keywords}")
                for keyword in keywords:
                    # Use word boundaries for common words to avoid false matches
                    if keyword in ["no", "yes", "ok"]:
                        # For very common words, require them as standalone words
                        pattern = rf'\b{re.escape(keyword)}\b'
                        match = re.search(pattern, text_l)
                        logging.info(f"[ROUTER] Testing keyword '{keyword}' with pattern '{pattern}': match={match is not None}")
                        if match:
                            logging.info(f"[ROUTER] ✓ MATCHED confirmation intent '{confirmation_intent}' via keyword '{keyword}'")
                            _debug(memory, f"Matched confirmation intent '{confirmation_intent}' via keyword '{keyword}'")
                            return confirmation_intent
                    else:
                        # For specific phrases, use substring match
                        is_match = keyword in text_l
                        logging.info(f"[ROUTER] Testing keyword '{keyword}' in text: match={is_match}")
                        if is_match:
                            logging.info(f"[ROUTER] ✓ MATCHED confirmation intent '{confirmation_intent}' via keyword '{keyword}'")
                            _debug(memory, f"Matched confirmation intent '{confirmation_intent}' via keyword '{keyword}'")
                            return confirmation_intent

            logging.info(f"[ROUTER] No confirmation keywords matched for text: '{text_l}'")

    # Check email keywords FIRST (before other write actions)
    # This prevents false matches with generic words like "update", "reply", etc.
    for keyword in EMAIL_KEYWORDS:
        if keyword in text_l:
            _debug(memory, f"Matched compose_email via keyword '{keyword}'")
            return "compose_email"

    # Check for generic verbs that need calendar context (add, create, make)
    generic_calendar_verbs = ["add", "create", "make", "put"]
    for verb in generic_calendar_verbs:
        if verb in text_l:
            # Check if there's calendar context
            has_calendar_context = any(ctx_word in text_l for ctx_word in CALENDAR_CONTEXT)
            if has_calendar_context:
                _debug(memory, f"Matched book_appointment via generic verb '{verb}' with calendar context")
                return "book_appointment"

    # Then check for write actions (schedule, book, etc.)
    for action_intent, keywords in WRITE_ACTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_l:
                _debug(memory, f"Matched write action intent '{action_intent}' via keyword '{keyword}'")
                return action_intent

    # Check generic appointment keywords ONLY with calendar context
    has_calendar_context = any(ctx_word in text_l for ctx_word in CALENDAR_CONTEXT)
    if has_calendar_context:
        for action_intent, keywords in APPOINTMENT_GENERIC_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_l:
                    _debug(memory, f"Matched {action_intent} via generic keyword '{keyword}' with calendar context")
                    return action_intent

    # Then check for read actions (calendar, availability, etc.)
    for action_intent, keywords in READ_ACTION_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_l:
                _debug(memory, f"Matched read action intent '{action_intent}' via keyword '{keyword}'")
                return action_intent

    # =============================
    # Priority 2: User-Defined Intents
    # =============================
    # If no memory provided, fall back to general
    if not memory:
        return "general"

    # Get user intents, ordered by priority
    intents = memory.list_intents("local")

    # Filter to enabled intents only
    enabled_intents = [i for i in intents if i.get("enabled", True)]

    if not enabled_intents:
        return "general"  # No intents configured

    # Check each intent's keywords in priority order
    for intent in enabled_intents:
        keywords = intent.get("keywords", "")

        # Skip empty keywords (usually the "general" catch-all)
        if not keywords or not keywords.strip():
            continue

        # Split keywords by comma and check if any match
        keyword_list = [k.strip().lower() for k in keywords.split(",") if k.strip()]

        for keyword in keyword_list:
            if keyword in text_l:
                _debug(memory, f"Matched intent '{intent['id']}' via keyword '{keyword}'")
                return intent["id"]

    # If no keywords matched, return the lowest priority intent (usually "general")
    # or fall back to "general" if no intents exist
    fallback = enabled_intents[-1] if enabled_intents else None
    if fallback:
        _debug(memory, f"No keyword match, using fallback intent '{fallback['id']}'")
        return fallback["id"]

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

    # Use enhanced intent classification with mode and subtab awareness
    intent = classify_intent_enhanced(
        text=text,
        memory=memory,
        user_id=context.get("user_id"),
        mode=context.get("mode"),
        subtab=context.get("subtab"),
        provider_registry=provider_registry
    )
    forced = context.get("forced_provider")

    _debug(memory, "Final intent locked", intent=intent)
    _debug(memory, f"Incoming text: {text}")
    _debug(memory, f"Classified intent: {intent}")
    _debug(memory, f"Forced provider: {forced}")

    # =============================
    # Action Intent Routing
    # =============================
    # Route action intents to ActionRouter instead of LLM providers
    ACTION_INTENTS = ["read_calendar", "book_appointment", "update_appointment", "cancel_appointment", "read_email", "compose_email", "approve_confirmation", "reject_confirmation"]

    if intent in ACTION_INTENTS:
        _debug(memory, f"Routing to ActionRouter for intent: {intent}")

        # Block personal actions (M365 calendar/email) in work mode
        PERSONAL_ACTIONS = ["read_calendar", "book_appointment", "update_appointment", "cancel_appointment", "read_email", "compose_email"]
        current_mode = context.get("mode", "personal")

        if current_mode == "work" and intent in PERSONAL_ACTIONS:
            _debug(memory, f"Blocked personal action '{intent}' in work mode")
            return {
                "text": "Calendar and email actions are not available in Work mode. These are personal actions. Please switch to Personal mode to use these features.",
                "provider": "error",
                "model": None,
                "task_type": intent,
                "fallback_reason": "personal_action_in_work_mode",
            }

        if not action_router:
            return {
                "text": "Action system is not initialized. Please contact support.",
                "provider": "error",
                "model": None,
                "task_type": intent,
                "fallback_reason": "action_router not initialized",
            }

        # Build action context
        action_context = {
            "text": text,
            "session_id": context.get("session_id"),
            "user_id": context.get("user_id", 1),
            "intent": intent,
        }

        # Route to ActionRouter
        try:
            result = action_router.route_action_request(action_context)
            _debug(memory, f"ActionRouter returned: {result.get('provider')}")
            return result
        except Exception as e:
            logging.error(f"[ROUTER] ActionRouter failed: {e}")
            return {
                "text": f"I encountered an error processing your action request: {str(e)}",
                "provider": "error",
                "model": None,
                "task_type": intent,
                "fallback_reason": f"action_router_error: {str(e)}",
            }

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

    # Check for mode-specific system prompt override
    system_prompt_override = context.get("system_prompt_override")
    subtab_context_prefix = context.get("subtab_context_prefix")

    context_obj = context_manager.build_context(
        session_id=context.get("session_id"),
        user_text=text,
        system_prompt_override=system_prompt_override,
        subtab_context_prefix=subtab_context_prefix,
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