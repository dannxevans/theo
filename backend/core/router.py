from core.memory import MemoryStore
from core.context import ContextManager
from typing import Optional, Iterable
from providers.mock import MockProvider
from providers.anthropic import AnthropicProvider
from providers.openai import OpenAIProvider
from providers.grok import XAIProvider
from providers.mistral import MistralProvider
from providers.gemini import GoogleProvider
from providers.perplexity import PerplexityProvider
from core.provider_registry import ProviderRegistry
from core.action_router import ActionRouter
from actions.action_registry import ActionProviderRegistry
from core.intent_classifier import classify_intent_enhanced
import logging


from core.user_utils import normalize_user_id, DEFAULT_USER_ID

def _debug_log(memory: Optional[MemoryStore], message: str):
    """Log debug messages only if debug mode is enabled in user preferences."""
    if not memory:
        return
    try:
        prefs = memory.get_all(DEFAULT_USER_ID)
        enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"
        if enabled:
            logging.info(f"[DEBUG] {message}")
    except Exception:
        pass  # Silently fail if we can't check debug preference

INTENT_TO_PROVIDER_TYPE = {
    "coding": "anthropic",
    "general": "openai",
    "planning": "openai",
    "reasoning": "anthropic",
    "creative": "openai",
    "search": "perplexity",
}

PROVIDER_CAPABILITIES = {
    "openai": {"general", "planning", "creative", "coding", "reasoning"},
    "anthropic": {"general", "coding", "reasoning", "planning", "creative"},
    "xai": {"general", "coding", "reasoning", "planning", "creative"},
    "mistral": {"general", "coding", "reasoning", "planning", "creative"},
    "google": {"general", "coding", "reasoning", "planning", "creative"},
    "perplexity": {"general", "search", "reasoning", "planning"},
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
            prefs = memory.get_all(DEFAULT_USER_ID)
            value = prefs.get("debug_enabled")
            if isinstance(value, str):
                debug_enabled = value.lower() == "true"
            elif isinstance(value, bool):
                debug_enabled = value
        if debug_enabled:
            ctx_str = ""
            if context:
                # Sanitize context - only log safe metadata, not sensitive data
                safe_context = {}
                for k, v in context.items():
                    # Skip sensitive fields
                    if k in ('text', 'messages', 'system', 'response', 'api_key', 'token', 'password'):
                        safe_context[k] = '[REDACTED]'
                    # Truncate long values
                    elif isinstance(v, str) and len(v) > 100:
                        safe_context[k] = f"{v[:97]}..."
                    else:
                        safe_context[k] = v
                ctx_str = " | " + " ".join(f"{k}={v}" for k, v in safe_context.items())
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
    # Normalize user_id (handles "local" string, None, and integers)
    lookup_user_id = normalize_user_id(user_id)
    intents = memory.list_intents(lookup_user_id)

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


def provider_supports_intent(provider_cfg: dict, intent: str, memory: Optional[MemoryStore] = None, user_id: Optional[int] = None) -> bool:
    """
    Check if a provider supports a given intent.

    For hardcoded intents (coding, general, etc.), check PROVIDER_CAPABILITIES.
    For custom user-defined intents, assume all providers can handle them via LLM.
    """
    # Normalize user_id
    if user_id is not None:
        user_id = normalize_user_id(user_id)

    ptype = provider_cfg.get("type")
    allowed = PROVIDER_CAPABILITIES.get(ptype)
    if not allowed:
        return False

    # Check if this is a hardcoded intent
    if intent in allowed:
        return True

    # For custom intents, check if it's an action intent (M365, calendar, etc.)
    # Action intents should NOT go to LLM providers
    # Get action intents dynamically from database if memory is available
    action_intents = []
    if memory:
        try:
            action_intents = memory.get_action_intents(user_id)
        except Exception as e:
            logging.warning(f"Failed to get action intents: {e}")
            action_intents = []

    if intent in action_intents:
        # Action intents can only be handled by action providers (not LLM providers)
        return False

    # For all other custom intents, allow any LLM provider to handle them
    return True


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


def resolve_from_memory(text: str, memory: Optional[MemoryStore], user_id: Optional[int] = None) -> Optional[str]:
    """
    Step 2: Attempt to directly answer from structured memory.
    Returns an answer string if resolved, otherwise None.
    """
    if not memory or not text:
        return None

    text_l = text.lower().strip()

    # Try structured memory first
    relevant_memories = memory.get_relevant_memories(normalize_user_id(user_id), text, max_results=3)

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
    facts = memory.get_all(normalize_user_id(user_id)) or {}
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


def _log_feature_provider_usage(memory: Optional[MemoryStore], user_id: str, provider_type: str, success: bool, latency_ms: int = None, error_message: str = None):
    """
    Log feature provider usage to database.

    Args:
        memory: MemoryStore instance
        user_id: User ID
        provider_type: Type of provider (e.g., 'openweather', 'here')
        success: Whether the request succeeded
        latency_ms: Request latency in milliseconds
        error_message: Error message if request failed
    """
    if not memory:
        return

    try:
        import sqlite3
        from config import Config

        db_path = Config.DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO feature_provider_usage_logs (user_id, provider_type, success, latency_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (str(user_id), provider_type, int(success), latency_ms, error_message))

        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"[ROUTER] Failed to log feature provider usage: {e}")


def _generate_friendly_weather_response(raw_weather: str, user_text: str, memory: Optional[MemoryStore], user_id: str) -> Optional[str]:
    """
    Use system LLM to generate a friendly, conversational weather response.

    Args:
        raw_weather: Raw weather data formatted as text
        user_text: Original user query
        memory: MemoryStore instance
        user_id: User ID

    Returns:
        Friendly weather response or None if LLM unavailable
    """
    try:
        # Get system provider for lightweight tasks (configurable)
        registry = ProviderRegistry(memory)

        # First check for "system" routing preference
        system_provider_id = memory.get_routing_provider(user_id, "system") if memory else None
        provider_cfg = None

        if system_provider_id:
            # Use configured system provider
            provider_cfg = registry.get(system_provider_id)
            logging.info(f"[WEATHER] Using configured system provider: {system_provider_id}")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Try configured fallback provider for system intent
            fallback_provider_id = memory.get_fallback_provider(user_id, "system") if memory else None
            if fallback_provider_id:
                provider_cfg = registry.get(fallback_provider_id)
                if provider_cfg and provider_cfg.get("api_key"):
                    logging.info(f"[WEATHER] Using configured fallback provider: {fallback_provider_id}")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Fallback to OpenAI provider
            provider_cfg = registry.get_by_type("openai")
            logging.info("[WEATHER] Using fallback OpenAI provider for weather formatting")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # No LLM available at all
            logging.warning("[WEATHER] No LLM provider available, using raw weather data")
            return None

        # Instantiate appropriate provider based on type
        provider_type = provider_cfg.get("type")
        api_key = provider_cfg.get("api_key")
        model = provider_cfg.get("model")

        if provider_type == "openai":
            provider = OpenAIProvider(api_key=api_key, model=model)
        elif provider_type == "anthropic":
            provider = AnthropicProvider(api_key=api_key, model=model)
        elif provider_type == "google":
            provider = GoogleProvider(api_key=api_key, model=model)
        elif provider_type == "xai":
            provider = XAIProvider(api_key=api_key, model=model)
        elif provider_type == "mistral":
            provider = MistralProvider(api_key=api_key, model=model)
        else:
            logging.warning(f"[WEATHER] Unknown provider type: {provider_type}")
            return None

        # Generate friendly response using LLM
        system_prompt = """You are a friendly weather assistant. Your job is to present weather information in a natural, conversational way.

Guidelines:
- Be concise and friendly
- Use natural language instead of bullet points
- Include relevant details based on the conditions (e.g., mention wind if it's strong, humidity if it's high)
- Don't repeat the location unnecessarily
- Keep it to 1-2 sentences unless the user asks for more detail"""

        user_prompt = f"""User asked: "{user_text}"

Weather data:
{raw_weather}

Present this weather information in a friendly, natural way:"""

        response = provider.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

        if response_text:
            logging.info(f"[WEATHER] Generated friendly response ({len(response_text)} chars)")
            return response_text
        else:
            logging.warning("[WEATHER] LLM returned empty response")
            return None

    except Exception as e:
        logging.error(f"[WEATHER] Failed to generate friendly response: {e}")
        return None


def _generate_friendly_routing_response(raw_route: str, user_text: str, memory: Optional[MemoryStore], user_id: str) -> Optional[str]:
    """
    Use system LLM to generate a friendly, conversational routing response.

    Args:
        raw_route: Raw routing data formatted as text
        user_text: Original user query
        memory: MemoryStore instance
        user_id: User ID

    Returns:
        Friendly routing response or None if LLM unavailable
    """
    try:
        # Get system provider for lightweight tasks (configurable)
        registry = ProviderRegistry(memory)

        # First check for "system" routing preference
        system_provider_id = memory.get_routing_provider(user_id, "system") if memory else None
        provider_cfg = None

        if system_provider_id:
            # Use configured system provider
            provider_cfg = registry.get(system_provider_id)
            logging.info(f"[ROUTING] Using configured system provider: {system_provider_id}")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Try configured fallback provider for system intent
            fallback_provider_id = memory.get_fallback_provider(user_id, "system") if memory else None
            if fallback_provider_id:
                provider_cfg = registry.get(fallback_provider_id)
                if provider_cfg and provider_cfg.get("api_key"):
                    logging.info(f"[ROUTING] Using configured fallback provider: {fallback_provider_id}")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # Fallback to OpenAI provider
            provider_cfg = registry.get_by_type("openai")
            logging.info("[ROUTING] Using fallback OpenAI provider for routing formatting")

        if not provider_cfg or not provider_cfg.get("api_key"):
            # No LLM available at all
            logging.warning("[ROUTING] No LLM provider available, using raw routing data")
            return None

        # Instantiate appropriate provider based on type
        provider_type = provider_cfg.get("type")
        api_key = provider_cfg.get("api_key")
        model = provider_cfg.get("model")

        if provider_type == "openai":
            provider = OpenAIProvider(api_key=api_key, model=model)
        elif provider_type == "anthropic":
            provider = AnthropicProvider(api_key=api_key, model=model)
        elif provider_type == "google":
            provider = GoogleProvider(api_key=api_key, model=model)
        elif provider_type == "xai":
            provider = XAIProvider(api_key=api_key, model=model)
        elif provider_type == "mistral":
            provider = MistralProvider(api_key=api_key, model=model)
        else:
            logging.warning(f"[ROUTING] Unknown provider type: {provider_type}")
            return None

        # Generate friendly response using LLM
        system_prompt = """You are a friendly navigation assistant. Your job is to present routing information in a natural, conversational way.

Guidelines:
- Be concise and friendly
- Use natural language instead of bullet points
- Convert distance and time into easy-to-understand phrases
- Don't repeat coordinates unnecessarily
- Keep it to 1-2 sentences unless the user asks for more detail"""

        user_prompt = f"""User asked: "{user_text}"

Routing data:
{raw_route}

Present this routing information in a friendly, natural way:"""

        response = provider.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

        if response_text:
            logging.info(f"[ROUTING] Generated friendly response ({len(response_text)} chars)")
            return response_text
        else:
            logging.warning("[ROUTING] LLM returned empty response")
            return None

    except Exception as e:
        logging.error(f"[ROUTING] Failed to generate friendly response: {e}")
        return None


def select_provider(intent: str, memory: Optional[MemoryStore], forced_provider: Optional[str] = None, user_id: Optional[int] = None):
    fallback_reason = None
    selected_provider = None
    routing_explanation = []

    # Normalize user_id
    user_id = normalize_user_id(user_id)

    # Step 3: Check health status and circuit breaker
    health_summary = memory.get_provider_health_summary() if memory else {}

    def is_provider_healthy(provider_id):
        health = health_summary.get(provider_id, {})
        if health.get("circuit_breaker_open"):
            # Check if cooldown period has elapsed (half-open state)
            opened_at = health.get("circuit_breaker_opened_at")
            cooldown_minutes = health.get("circuit_breaker_cooldown_minutes", 60)

            if opened_at:
                from datetime import datetime, timedelta
                if isinstance(opened_at, str):
                    opened_at = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))

                elapsed = datetime.utcnow() - opened_at
                cooldown_delta = timedelta(minutes=cooldown_minutes)

                if elapsed >= cooldown_delta:
                    # Cooldown period has elapsed - enter half-open state
                    # Allow this request to try the provider
                    logging.info(f"[ROUTER] Circuit breaker cooldown elapsed for {provider_id} ({elapsed.total_seconds()/60:.1f} minutes). Entering half-open state - will retry provider.")
                    return True, None

            return False, f"circuit breaker open (cooldown: {cooldown_minutes} min)"
        if health.get("health_status") == "unhealthy":
            return False, f"unhealthy (failure rate: {health.get('failure_rate', 0)}%)"
        return True, None

    if forced_provider and provider_registry:
        _debug_log(memory, f"[ROUTER] Forced provider requested: {forced_provider}")
        provider_by_id = provider_registry.get(forced_provider)
        _debug_log(memory, f"[ROUTER] Provider by ID lookup result: {provider_by_id}")
        if provider_by_id:
            healthy, reason = is_provider_healthy(provider_by_id.get("id"))
            _debug_log(memory, f"[ROUTER] Provider health check: healthy={healthy}, reason={reason}")
            if healthy:
                selected_provider = provider_by_id
                routing_explanation.append(f"User forced provider: {forced_provider}")
            else:
                fallback_reason = f"Forced provider {forced_provider} unavailable: {reason}"
                routing_explanation.append(fallback_reason)
        else:
            _debug_log(memory, f"[ROUTER] Provider not found by ID, trying model lookup")
            provider_by_model = provider_registry.get_by_model(forced_provider)
            _debug_log(memory, f"[ROUTER] Provider by model lookup result: {provider_by_model}")
            if provider_by_model:
                healthy, reason = is_provider_healthy(provider_by_model.get("id"))
                if healthy:
                    selected_provider = provider_by_model
                    routing_explanation.append(f"User forced model: {forced_provider}")
                else:
                    fallback_reason = f"Forced model {forced_provider} unavailable: {reason}"
                    routing_explanation.append(fallback_reason)
            else:
                _debug_log(memory, f"[ROUTER] Forced provider '{forced_provider}' not found by ID or model")

    if not selected_provider and memory:
        routed = memory.get_routing_provider(user_id, intent)
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

                    # Check for user-configured fallback provider
                    fallback_provider_id = memory.get_fallback_provider(user_id, intent)
                    if fallback_provider_id and provider_registry:
                        fallback_provider = provider_registry.get(fallback_provider_id)
                        if fallback_provider:
                            healthy_fallback, fallback_health_reason = is_provider_healthy(fallback_provider_id)
                            if healthy_fallback:
                                selected_provider = fallback_provider
                                routing_explanation.append(f"User configured fallback: {routed} → {fallback_provider_id}")
                                fallback_reason = f"Primary provider {routed} failed: {reason}, using configured fallback"
                            else:
                                routing_explanation.append(f"Configured fallback {fallback_provider_id} also unhealthy: {fallback_health_reason}")
                                fallback_reason = f"Both primary ({routed}) and configured fallback ({fallback_provider_id}) unavailable"

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
        if not provider_supports_intent(selected_provider, intent, memory, user_id):
            fallback_reason = "provider does not support intent"
            routing_explanation.append(f"{selected_provider.get('type')} cannot handle {intent}")
            if provider_registry:
                current_type = selected_provider.get("type")
                other_type = "openai" if current_type == "anthropic" else "anthropic"
                p = provider_registry.get_by_type(other_type)
                if p and p.get("api_key") and provider_supports_intent(p, intent, memory, user_id):
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
    if ptype == "xai":
        return XAIProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
        )
    if ptype == "mistral":
        return MistralProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
        )
    if ptype == "google":
        return GoogleProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
        )
    if ptype == "perplexity":
        return PerplexityProvider(
            api_key=provider_cfg["api_key"],
            base_url=provider_cfg.get("base_url"),
            model=provider_cfg.get("model"),
            search_mode=provider_cfg.get("search_mode", True),
        )
    return MockProvider()


def route_request(context: dict, stream: bool = False):
    # CRITICAL DEBUG: Log function entry with parameter types
    logging.info(f"[ROUTER] route_request called with context type={type(context)}, stream={stream}")

    text = context.get("text", "")
    memory = context.get("memory")

    # =============================
    # Memory-first resolution
    # =============================
    answer = resolve_from_memory(text, memory, user_id=context.get("user_id"))
    if answer:
        _debug(memory, "Resolved directly from memory", answer=answer)
        return {
            "text": answer,
            "provider": "memory",
            "model": None,
            "task_type": "memory",
            "fallback_reason": None,
        }

    # Check if intent is being forced (used for internal summarization to prevent loops)
    force_intent = context.get("force_intent")

    # =============================
    # Confirmation Handling (BEFORE intent reasoning)
    # =============================
    # Check for pending confirmations and approval/rejection keywords
    if memory and context.get("user_id") and not force_intent:
        from core.confirmation_manager import ConfirmationManager

        conf_manager = ConfirmationManager(memory)
        pending = conf_manager.get_pending_confirmations(context.get("user_id"))

        if pending:
            text_l = text.lower().strip()
            CONFIRMATION_KEYWORDS = {
                "approve_confirmation": ["yes", "approve", "confirm", "ok", "sure", "go ahead", "do it", "y"],
                "reject_confirmation": ["no", "reject", "cancel", "don't", "stop", "n"],
            }

            # Check if user is responding to confirmation
            for confirmation_intent, keywords in CONFIRMATION_KEYWORDS.items():
                if any(keyword == text_l or text_l.startswith(keyword + " ") for keyword in keywords):
                    logging.info(f"[ROUTER] Detected confirmation response: {confirmation_intent}")
                    force_intent = confirmation_intent
                    break

    # =============================
    # NEW: Intent Reasoning Layer
    # =============================
    reasoning_result = None
    if provider_registry and not force_intent:
        try:
            from core.intent_reasoning import IntentReasoningEngine

            # Get conversation history for context-aware intent reasoning
            conversation_history = []
            session_id = context.get("session_id")
            if memory and session_id:
                recent_turns = memory.get_recent_turns(session_id, limit=6)
                conversation_history = [
                    {"role": turn["role"], "content": turn["content"]}
                    for turn in recent_turns
                ]
                logging.info(f"[ROUTER] Passing {len(conversation_history)} conversation turns to intent reasoning")

            reasoning_engine = IntentReasoningEngine(
                provider_registry,
                memory,
                user_id=context.get("user_id")
            )
            reasoning_result = reasoning_engine.reason(
                text=text,
                mode=context.get("mode"),
                subtab=context.get("subtab"),
                user_id=context.get("user_id"),
                conversation_history=conversation_history
            )

            # Log reasoning for debugging
            logging.info(f"[ROUTER] Reasoning result: intent={reasoning_result.intent}, "
                         f"confidence={reasoning_result.confidence}, "
                         f"services={[s.service for s in reasoning_result.service_signals]}")

            # Store reasoning trace
            if memory:
                try:
                    memory.store_reasoning_trace(
                        user_id=context.get("user_id"),
                        reasoning_result=reasoning_result,
                        session_id=context.get("session_id"),
                        mode=context.get("mode"),
                        subtab=context.get("subtab"),
                        user_text=text
                    )
                except Exception as trace_err:
                    logging.warning(f"[ROUTER] Failed to store reasoning trace: {trace_err}")

            # Handle ambiguous requests
            # BUT: defer clarification if multiple services detected - let orchestrator handle it
            # ALSO: defer clarification for appointment booking - orchestrator can find available slots
            has_multiple_services = len(reasoning_result.service_signals) > 1
            is_appointment_booking = reasoning_result.intent in ['book_appointment', 'calendar_create']

            if reasoning_result.is_ambiguous and reasoning_result.clarification_question and not has_multiple_services and not is_appointment_booking:
                logging.info("[ROUTER] Returning clarification question (single service, not appointment)")
                return {
                    "text": reasoning_result.clarification_question,
                    "provider": reasoning_result.provider_id or "intent_reasoning",
                    "model": reasoning_result.provider_model,
                    "task_type": "clarification",
                    "metadata": {
                        "reasoning_trace": reasoning_result.reasoning,
                        "suspected_intent": reasoning_result.intent,
                        "confidence": reasoning_result.confidence,
                        "entities": reasoning_result.entities.raw if hasattr(reasoning_result.entities, 'raw') else {},
                        "service_signals": [s.service for s in reasoning_result.service_signals]
                    }
                }
            elif is_appointment_booking:
                logging.info(f"[ROUTER] Deferring clarification to orchestrator (appointment booking: {reasoning_result.intent})")
            elif reasoning_result.is_ambiguous and reasoning_result.clarification_question and has_multiple_services:
                logging.info(f"[ROUTER] Deferring clarification to orchestrator (multiple services: {[s.service for s in reasoning_result.service_signals]})")

            # Use reasoning result if high confidence
            if reasoning_result.confidence >= 0.85:
                intent = reasoning_result.intent
                _debug(memory, f"Intent from reasoning: {intent} (confidence: {reasoning_result.confidence})")

                # Store entities and service signals in context for downstream use
                context["reasoning_entities"] = reasoning_result.entities
                context["reasoning_service_signals"] = reasoning_result.service_signals
            else:
                # Low confidence - don't use the intent, but preserve service_signals for orchestration
                logging.info(f"[ROUTER] Low reasoning confidence ({reasoning_result.confidence}), using fallback for intent")
                logging.info(f"[ROUTER] Preserving service signals: {[s.service for s in reasoning_result.service_signals]}")

                # Store service signals even for low confidence - orchestrator will decide if they warrant orchestration
                context["reasoning_entities"] = reasoning_result.entities
                context["reasoning_service_signals"] = reasoning_result.service_signals
                # Note: We keep reasoning_result for orchestration check, but won't use its intent field

        except Exception as e:
            logging.warning(f"[ROUTER] Intent reasoning failed: {e}")
            reasoning_result = None

    # =============================
    # NEW: Orchestration Check
    # =============================
    # Check if we should orchestrate based on Intent Reasoning output
    # Skip orchestration if called recursively from within orchestration
    skip_orchestration = context.get("_skip_orchestration", False)

    # Check if agentic AI is disabled (user preference)
    user_id_for_pref = normalize_user_id(context.get("user_id"))
    agentic_disabled = memory.get_user_preference(user_id_for_pref, "agentic_ai_disabled", "false") == "true"

    if agentic_disabled:
        logging.info("[ROUTER] Agentic AI disabled by user preference - skipping orchestration")
        skip_orchestration = True

    if reasoning_result and not force_intent and not skip_orchestration:
        try:
            from core.orchestration.orchestrator import Orchestrator

            orchestrator = Orchestrator(memory)

            # Check if this is a clarification response BEFORE deciding whether to orchestrate
            session_id = context.get("session_id")
            user_id = context.get("user_id")
            clarification_context = orchestrator._get_clarification_context(user_id, session_id)

            if clarification_context:
                logging.info(f"[ROUTER] Detected clarification response, forcing orchestration")
                # Force orchestration for clarification responses
                orch_decision = type('obj', (object,), {'should_orchestrate': True})()
            else:
                orch_decision = orchestrator.should_orchestrate(reasoning_result)

            if orch_decision.should_orchestrate:
                logging.info("[ROUTER] Orchestration triggered")

                # Get conversation history for orchestration
                conversation_history = []
                session_id = context.get("session_id")
                if memory and session_id:
                    recent_turns = memory.get_recent_turns(session_id, limit=6)
                    conversation_history = [
                        {"role": turn["role"], "content": turn["content"]}
                        for turn in recent_turns
                    ]

                # Execute orchestration
                orch_result = orchestrator.orchestrate(
                    user_query=text,
                    user_id=context.get("user_id"),
                    session_id=session_id,
                    reasoning_result=reasoning_result,
                    conversation_history=conversation_history
                )

                # Check if orchestration needs clarification
                if hasattr(orch_result, 'needs_clarification') and orch_result.needs_clarification:
                    logging.info("[ROUTER] Orchestration needs clarification, returning question")
                    return {
                        "text": orch_result.text,
                        "provider": "orchestration",
                        "model": None,
                        "task_type": "clarification",
                        "metadata": {
                            "reason": orch_result.skip_reason,
                            "needs_clarification": True
                        }
                    }

                # Return orchestration result
                # Phase 4: Includes action confirmations with frontend-compatible metadata
                # Footer format: "Sonnet-4.5 · Multi-Service · Orchestration"
                # provider = synthesis_provider_name, model = synthesis_model_id
                synthesis_model = orch_result.metadata.get("synthesis_model", "Unknown")
                synthesis_provider = orch_result.metadata.get("synthesis_provider", "system")

                # Transform confirmations for frontend compatibility
                # Frontend expects M365-style confirmation metadata
                confirmations = orch_result.metadata.get("confirmations", [])

                # Build metadata with orchestration-specific confirmation format
                response_metadata = orch_result.metadata.copy()

                # If confirmations exist, add frontend-compatible format
                if confirmations:
                    # Transform each confirmation to match M365 confirmation structure
                    orchestration_confirmations = []
                    for conf in confirmations:
                        orchestration_confirmations.append({
                            "confirmation_id": conf["confirmation_id"],
                            "action_id": conf["action_id"],
                            "confirmation_message": conf["message"],
                            "expires_at": conf["expires_at"].isoformat() if hasattr(conf["expires_at"], "isoformat") else str(conf["expires_at"]),
                            "status": conf["status"],
                            "approved": False,
                            "rejected": False
                        })

                    # Add to metadata in frontend-compatible format
                    response_metadata["orchestration_confirmations"] = orchestration_confirmations
                    response_metadata["has_confirmations"] = True

                    # CRITICAL: Remove raw confirmations field to prevent JSON serialization error
                    # The raw confirmations contain datetime objects which can't be JSON serialized
                    if "confirmations" in response_metadata:
                        del response_metadata["confirmations"]

                    logging.info(f"[ROUTER] Transformed {len(orchestration_confirmations)} confirmation(s) for frontend")

                return {
                    "text": orch_result.text,
                    "provider": synthesis_provider,  # Provider name (e.g., "claude-sonnet")
                    "model": synthesis_model,  # Full model ID (e.g., "claude-sonnet-4-5-20250929")
                    "task_type": "orchestration",
                    "metadata": response_metadata
                }
            else:
                logging.info(f"[ROUTER] Orchestration skipped: {orch_decision.skip_reason}")

        except Exception as e:
            logging.warning(f"[ROUTER] Orchestration check failed: {e}")
            # Fall through to normal routing on error

    # =============================
    # Existing Intent Classification
    # =============================
    # Use enhanced intent classification with mode and subtab awareness
    if force_intent:
        intent = force_intent
        _debug(memory, f"Intent forced to: {force_intent}")
    elif reasoning_result is None or reasoning_result.confidence < 0.85:
        # Use keyword classification if no reasoning or low confidence reasoning
        intent = classify_intent_enhanced(
            text=text,
            memory=memory,
            user_id=context.get("user_id"),
            mode=context.get("mode"),
            subtab=context.get("subtab"),
            provider_registry=provider_registry
        )
    else:
        # High confidence reasoning - intent was already set at line 1003
        pass
    forced = context.get("forced_provider")

    _debug(memory, "Final intent locked", intent=intent)
    _debug(memory, f"Incoming text: {text}")
    _debug(memory, f"Classified intent: {intent}")
    _debug(memory, f"Forced provider: {forced}")

    # =============================
    # Weather Intent Handling
    # =============================
    if intent == "weather":
        _debug(memory, "Handling weather request")

        # Get user_id from context
        user_id = normalize_user_id(context.get("user_id"))

        # Get weather API key from user preferences
        prefs = memory.get_all(user_id) if memory else {}
        api_key = prefs.get("feature_provider_openweather_api_key")

        if not api_key:
            return {
                "text": "Weather service is not configured. Please add your OpenWeather API key in Settings > Feature Providers.",
                "provider": "error",
                "model": None,
                "task_type": "weather",
                "fallback_reason": "missing_api_key",
            }

        # Extract location from the message
        import re  # Import at top since it's used later for postcode extraction too

        # First, check if intent reasoning extracted location entities
        location = None
        reasoning_entities = context.get("reasoning_entities")

        if reasoning_entities and hasattr(reasoning_entities, 'locations') and reasoning_entities.locations:
            # Use the first location extracted by intent reasoning
            location = reasoning_entities.locations[0]
            _debug(memory, f"Using location from intent reasoning: {location}")
        else:
            # Fallback to regex-based extraction
            text_l = text.lower()

            # Try to extract location using patterns
            location_patterns = [
                r'weather (?:in|for|at) ([^?]+)',
                r'temperature (?:in|for|at) ([^?]+)',
                r'forecast (?:in|for|at) ([^?]+)',
            ]

            for pattern in location_patterns:
                match = re.search(pattern, text_l)
                if match:
                    location = match.group(1).strip()
                    break

        # If no location found, ask for it
        if not location:
            return {
                "text": "I can get the weather for you! Which location would you like to know about?",
                "provider": "weather",
                "model": None,
                "task_type": "weather",
                "fallback_reason": "missing_location",
            }

        # Resolve location aliases (home, work, etc.) from memory
        if memory:
            location_lower = location.lower()
            logging.info(f"[WEATHER] Checking location alias: '{location}' (user_id: {user_id})")

            # Memory facts now use integer user_id
            memory_user_id = normalize_user_id(user_id)

            if location_lower in ["home", "my home"]:
                # Query memory facts for Home Location
                memories = memory.get_relevant_memories(memory_user_id, "home location", max_results=5)
                home_mem = next((m for m in memories if m.get('key') == 'Home Location'), None)
                if home_mem:
                    home_location = home_mem.get('value')
                    logging.info(f"[WEATHER] Resolved 'home' → '{home_location}'")
                    location = home_location
                else:
                    logging.warning(f"[WEATHER] Home Location not found in memory facts")
            elif location_lower in ["work", "my work", "office", "my office"]:
                # Query memory facts for Work Location
                memories = memory.get_relevant_memories(memory_user_id, "work location", max_results=5)
                work_mem = next((m for m in memories if m.get('key') == 'Work Location'), None)
                if work_mem:
                    work_location = work_mem.get('value')
                    logging.info(f"[WEATHER] Resolved 'work' → '{work_location}'")
                    location = work_location
                else:
                    logging.warning(f"[WEATHER] Work Location not found in memory facts")
            else:
                logging.info(f"[WEATHER] Location '{location}' is not an alias, using as-is")

        # Fallback check after resolution
        if not location:
            return {
                "text": "I can get the weather for you! Which location would you like to know about?",
                "provider": "weather",
                "model": None,
                "task_type": "weather",
                "fallback_reason": "missing_location",
            }

        # Extract city from full address for OpenWeather API
        # OpenWeather expects ONLY city names like "Salford" or "Wirral" (NO postcodes)
        # Example: "Soapworks, Colgate Ln, Salford M5 3LZ" → "Salford"
        # Example: "8 Harefields Way, Wirral. CH494SB" → "Wirral"
        if location and ',' in location:
            parts = [p.strip() for p in location.split(',')]
            # UK postcode pattern: XX## #XX or X# #XX
            postcode_pattern = r'[A-Z]{1,2}\d{1,2}\s?\d?[A-Z]{2}'

            # Find the city (last part that's not a postcode and doesn't contain a postcode)
            for part in reversed(parts):
                # Skip empty parts
                if not part:
                    continue
                # Remove any postcode from this part
                part_clean = re.sub(postcode_pattern, '', part).strip().rstrip('.')
                # If there's meaningful text left after removing postcode, this is likely the city
                if part_clean and len(part_clean) > 2:
                    location = part_clean
                    logging.info(f"[WEATHER] Extracted city '{location}' from full address")
                    break

        # Fetch weather data
        from core.weather_service import WeatherService
        import time

        start_time = time.time()
        try:
            weather_service = WeatherService(api_key)
            weather_data = weather_service.get_weather(location)
            latency_ms = int((time.time() - start_time) * 1000)

            if weather_data:
                # Log successful usage
                _log_feature_provider_usage(memory, user_id, "openweather", success=True, latency_ms=latency_ms)

                # Get raw weather data formatted
                raw_weather = weather_service.format_weather_response(weather_data)

                # Use system LLM to make the response more conversational
                friendly_response = _generate_friendly_weather_response(
                    raw_weather,
                    user_text=text,
                    memory=memory,
                    user_id=user_id
                )

                if friendly_response:
                    response_text = friendly_response
                else:
                    # Fallback to raw format if LLM fails
                    response_text = raw_weather

                return {
                    "text": response_text,
                    "provider": "weather",
                    "model": "openweather",
                    "task_type": "weather",
                    "fallback_reason": None,
                }
            else:
                # Log failed usage
                _log_feature_provider_usage(memory, user_id, "openweather", success=False, latency_ms=latency_ms, error_message="Failed to fetch weather data")

                return {
                    "text": f"I couldn't fetch the weather for '{location}'. Please check the location name and try again.",
                    "provider": "weather",
                    "model": None,
                    "task_type": "weather",
                    "fallback_reason": "weather_fetch_failed",
                }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            _log_feature_provider_usage(memory, user_id, "openweather", success=False, latency_ms=latency_ms, error_message=str(e))

            logging.error(f"[ROUTER] Weather service error: {e}")
            return {
                "text": f"I encountered an error fetching the weather: {str(e)}",
                "provider": "error",
                "model": None,
                "task_type": "weather",
                "fallback_reason": f"weather_error: {str(e)}",
            }

    if intent == "routing":
        _debug(memory, "Handling routing request")

        # Get user_id from context
        user_id = normalize_user_id(context.get("user_id"))

        # Get HERE API key from user preferences
        prefs = memory.get_all(user_id) if memory else {}
        api_key = prefs.get("feature_provider_here_api_key")

        if not api_key:
            return {
                "text": "Routing service is not configured. Please add your HERE API key in Settings > Feature Providers.",
                "provider": "error",
                "model": None,
                "task_type": "routing",
                "fallback_reason": "missing_api_key",
            }

        # Extract origin and destination from the message
        import re
        text_l = text.lower()

        origin = None
        destination = None

        # First, try to use locations from intent reasoning
        reasoning_entities = context.get("reasoning_entities")
        if reasoning_entities and hasattr(reasoning_entities, 'locations') and reasoning_entities.locations:
            locations = reasoning_entities.locations
            logging.info(f"[ROUTING] Intent reasoning extracted locations: {locations}")

            # Use heuristics to determine origin vs destination
            if len(locations) == 1:
                # Only one location - use as destination, default to home as origin
                destination = locations[0]
                origin = "home"
                logging.info(f"[ROUTING] Single location extracted, using home as origin: '{origin}' → '{destination}'")
            elif len(locations) >= 2:
                # Multiple locations - use context clues to determine which is which
                # Check if "from" appears before "to" in the text
                from_index = text_l.find('from')
                to_index = text_l.find('to')

                if from_index != -1 and to_index != -1:
                    if from_index < to_index:
                        # "from X to Y" - first is origin, second is destination
                        origin = locations[0]
                        destination = locations[1] if len(locations) > 1 else locations[0]
                    else:
                        # "to Y from X" - reversed order
                        destination = locations[0]
                        origin = locations[1] if len(locations) > 1 else "home"
                else:
                    # No clear "from/to" - guess based on common patterns
                    # If one location is "home", it's usually the origin
                    if any(loc.lower() in ["home", "my home"] for loc in locations):
                        home_idx = next(i for i, loc in enumerate(locations) if loc.lower() in ["home", "my home"])
                        origin = locations[home_idx]
                        destination = locations[1 - home_idx] if len(locations) == 2 else locations[0]
                    else:
                        # Default: first is origin, second is destination
                        origin = locations[0]
                        destination = locations[1]

                logging.info(f"[ROUTING] Multiple locations, determined: '{origin}' → '{destination}'")

        # Fallback to regex-based extraction if intent reasoning didn't extract locations
        if not origin or not destination:
            # Pattern 1: Explicit "from X to Y"
            from_to_pattern = r'from\s+(.+?)\s+to\s+(.+?)(?:\?|$|\.)'
            match = re.search(from_to_pattern, text_l)
            if match:
                origin = match.group(1).strip()
                destination = match.group(2).strip()
                logging.info(f"[ROUTING] Regex extracted from/to: '{origin}' → '{destination}'")
            else:
                # Pattern 2: Only "to Y" (assume current location as origin)
                to_only_pattern = r'(?:route|traffic|directions|navigate|drive|commute)\s+(?:to|for)\s+(.+?)(?:\?|$|\.)'
                match = re.search(to_only_pattern, text_l)
                if match:
                    destination = match.group(1).strip()
                    # Try to get home location as default origin
                    if memory and not origin:
                        memories = memory.get_relevant_memories(normalize_user_id(user_id), "home location", max_results=5)
                        home_mem = next((m for m in memories if m.get('key') == 'Home Location'), None)
                        if home_mem:
                            origin = "home"
                            logging.info(f"[ROUTING] Regex extracted to-only pattern, using home as origin: '{origin}' → '{destination}'")

        # If no match, ask for clarification
        if not origin or not destination:
            return {
                "text": "I can provide routing information! Please specify the origin and destination (e.g., 'route from home to work').",
                "provider": "routing",
                "model": None,
                "task_type": "routing",
                "fallback_reason": "missing_locations",
            }

        # Resolve location aliases (home, work, etc.) from memory facts
        if memory:
            # Memory facts now use integer user_id
            memory_user_id = normalize_user_id(user_id)

            # Resolve origin
            origin_lower = origin.lower()
            if origin_lower in ["home", "my home"]:
                memories = memory.get_relevant_memories(memory_user_id, "home location", max_results=5)
                home_mem = next((m for m in memories if m.get('key') == 'Home Location'), None)
                if home_mem:
                    home_location = home_mem.get('value')
                    logging.info(f"[ROUTING] Resolved origin 'home' → '{home_location}'")
                    origin = home_location
            elif origin_lower in ["work", "my work", "office", "my office"]:
                memories = memory.get_relevant_memories(memory_user_id, "work location", max_results=5)
                work_mem = next((m for m in memories if m.get('key') == 'Work Location'), None)
                if work_mem:
                    work_location = work_mem.get('value')
                    logging.info(f"[ROUTING] Resolved origin 'work' → '{work_location}'")
                    origin = work_location

            # Resolve destination
            dest_lower = destination.lower()
            if dest_lower in ["home", "my home"]:
                memories = memory.get_relevant_memories(memory_user_id, "home location", max_results=5)
                home_mem = next((m for m in memories if m.get('key') == 'Home Location'), None)
                if home_mem:
                    home_location = home_mem.get('value')
                    logging.info(f"[ROUTING] Resolved destination 'home' → '{home_location}'")
                    destination = home_location
            elif dest_lower in ["work", "my work", "office", "my office"]:
                memories = memory.get_relevant_memories(memory_user_id, "work location", max_results=5)
                work_mem = next((m for m in memories if m.get('key') == 'Work Location'), None)
                if work_mem:
                    work_location = work_mem.get('value')
                    logging.info(f"[ROUTING] Resolved destination 'work' → '{work_location}'")
                    destination = work_location

        # Fallback check after resolution
        if not origin or not destination:
            return {
                "text": "I can provide routing information! Please specify the origin and destination.",
                "provider": "routing",
                "model": None,
                "task_type": "routing",
                "fallback_reason": "missing_locations",
            }

        # Extract city from full addresses for better geocoding accuracy
        # While HERE API can handle full addresses, simplified addresses work better
        # Example: "Soapworks, Colgate Ln, Salford M5 3LZ" → "Salford M5 3LZ"
        def extract_city_for_routing(location):
            if location and ',' in location:
                parts = [p.strip() for p in location.split(',')]
                # UK postcode pattern: XX## #XX or X# #XX
                postcode_pattern = r'[A-Z]{1,2}\d{1,2}\s?\d?[A-Z]{2}'

                # Find city with postcode (last 2 parts usually)
                # Example: "Salford M5 3LZ" from "Soapworks, Colgate Ln, Salford M5 3LZ"
                if len(parts) >= 2:
                    # Check if last part contains postcode
                    last_part = parts[-1]
                    if re.search(postcode_pattern, last_part):
                        # Return city + postcode (last 2 parts)
                        city_with_postcode = ", ".join(parts[-2:]) if len(parts) >= 2 else last_part
                        logging.info(f"[ROUTING] Extracted '{city_with_postcode}' from full address")
                        return city_with_postcode
            return location

        origin = extract_city_for_routing(origin)
        destination = extract_city_for_routing(destination)

        # Fetch route data
        from core.traffic_service import TrafficService
        import time

        start_time = time.time()
        try:
            traffic_service = TrafficService(api_key)
            # Traffic service handles geocoding automatically
            route_data = traffic_service.get_traffic_estimate(origin, destination)
            latency_ms = int((time.time() - start_time) * 1000)

            if route_data:
                # Log successful usage
                _log_feature_provider_usage(memory, user_id, "here", success=True, latency_ms=latency_ms)

                # Get raw route data formatted
                raw_route = traffic_service.format_traffic_response(route_data)

                # Use system LLM to make the response more conversational
                friendly_response = _generate_friendly_routing_response(
                    raw_route,
                    user_text=text,
                    memory=memory,
                    user_id=user_id
                )

                if friendly_response:
                    response_text = friendly_response
                else:
                    # Fallback to raw format if LLM fails
                    response_text = raw_route

                return {
                    "text": response_text,
                    "provider": "routing",
                    "model": "here",
                    "task_type": "routing",
                    "fallback_reason": None,
                }
            else:
                # Log failed usage
                _log_feature_provider_usage(memory, user_id, "here", success=False, latency_ms=latency_ms, error_message="No route data returned")

                return {
                    "text": f"I couldn't fetch the route from '{origin}' to '{destination}'. Please check the coordinates and try again.",
                    "provider": "routing",
                    "model": None,
                    "task_type": "routing",
                    "fallback_reason": "routing_fetch_failed",
                }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            # Log failed usage
            _log_feature_provider_usage(memory, user_id, "here", success=False, latency_ms=latency_ms, error_message=str(e))

            logging.error(f"[ROUTER] Routing service error: {e}")
            return {
                "text": f"I encountered an error fetching the route: {str(e)}",
                "provider": "error",
                "model": None,
                "task_type": "routing",
                "fallback_reason": f"routing_error: {str(e)}",
            }

    if intent == "planning":
        _debug(memory, "Handling planning request")

        # Get user_id from context
        user_id = normalize_user_id(context.get("user_id"))

        # Use PlanningHandlers to process the request
        from core.actions.planning_handlers import PlanningHandlers

        try:
            planning_handlers = PlanningHandlers(memory)
            result = planning_handlers.handle_planning_query(
                user_text=text,
                session_id=context.get("session_id", ""),
                user_id=int(user_id) if isinstance(user_id, str) and user_id.isdigit() else user_id,
                context=context
            )

            return result

        except Exception as e:
            logging.error(f"[ROUTER] Planning service error: {e}")
            return {
                "text": f"I encountered an error processing your planning request: {str(e)}",
                "provider": "error",
                "model": None,
                "task_type": "planning",
                "fallback_reason": f"planning_error: {str(e)}",
            }

    # =============================
    # Web Fetch Intent Handling
    # =============================
    if intent == "web_fetch":
        _debug(memory, "Handling web fetch request")

        try:
            from core.web_fetch_service import WebFetchService
            import re
            import time

            # Get user_id and session_id from context
            user_id = normalize_user_id(context.get("user_id"))
            session_id = context.get("session_id", "web_fetch_enrichment")

            # Extract URLs from message
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, text)

            if not urls:
                return {
                    "text": "I couldn't find any URLs in your message. Please provide a valid HTTPS URL to fetch.",
                    "provider": "error",
                    "model": None,
                    "task_type": "error",
                    "metadata": {"error_type": "no_url_found"}
                }

            # Fetch content from all URLs
            start_time = time.time()
            web_service = WebFetchService(memory)

            if len(urls) == 1:
                # Single URL - use simple fetch
                result = web_service.fetch_url(urls[0], user_id)
                latency_ms = int((time.time() - start_time) * 1000)

                # Log usage
                _log_feature_provider_usage(
                    memory, user_id, "web_fetch",
                    success=result["success"],
                    latency_ms=latency_ms,
                    error_message=result.get("error")
                )

                if not result["success"]:
                    return {
                        "text": f"I couldn't fetch that URL: {result['error']}",
                        "provider": "error",
                        "model": None,
                        "task_type": "error",
                        "metadata": {
                            "error_type": "fetch_failed",
                            "url": urls[0],
                            "error_message": result["error"]
                        }
                    }

                # Format content for LLM processing
                formatted_content = web_service.format_response(result["content"], urls[0])
            else:
                # Multiple URLs - fetch all
                multi_result = web_service.fetch_urls(urls, user_id)
                latency_ms = int((time.time() - start_time) * 1000)

                # Log usage for each URL
                for url_result in multi_result["results"]:
                    _log_feature_provider_usage(
                        memory, user_id, "web_fetch",
                        success=url_result["success"],
                        latency_ms=latency_ms // len(urls),  # Approximate per-URL time
                        error_message=url_result.get("error")
                    )

                if not multi_result["success"]:
                    return {
                        "text": f"I couldn't fetch any of the URLs. Summary: {multi_result['summary']}",
                        "provider": "error",
                        "model": None,
                        "task_type": "error",
                        "metadata": {
                            "error_type": "all_fetches_failed",
                            "urls": urls,
                            "summary": multi_result["summary"]
                        }
                    }

                # Format multiple URLs for LLM processing
                formatted_content = web_service.format_multi_response(multi_result["results"])

            # Use system LLM to generate friendly response from web content
            # Build prompt for LLM
            prompt = f"""User asked: "{text}"

Fetched web content:
{formatted_content}

Based on the webpage content above, provide a helpful answer to the user's question."""

            # Use system intent for lightweight content summarization
            system_message = """You are a helpful assistant that summarizes web content. Your job is to present fetched web information in a clear, useful way.

Guidelines:
- Be concise and informative
- Answer the user's question directly using the web content
- Cite specific information from the page when relevant
- If the page doesn't contain the answer, say so clearly
- Keep your response focused on what the user asked for"""

            router_context = {
                "text": prompt,
                "session_id": session_id,
                "memory": memory,
                "user_id": str(user_id),
                "forced_provider": None,
                "force_intent": "system",  # Use system intent for internal summarization
                "system_message": system_message
            }

            llm_result = route_request(router_context)
            response_text = llm_result.get("text", "").strip()

            return {
                "text": response_text,
                "provider": llm_result.get("provider", "web_fetch"),
                "model": llm_result.get("model"),
                "task_type": "web_fetch",
                "metadata": {
                    "urls": urls,
                    "url_count": len(urls),
                    "content_length": len(formatted_content),
                    "fetch_latency_ms": latency_ms,
                    "cached": result.get("cached", False) if len(urls) == 1 else None
                }
            }

        except Exception as e:
            logging.error(f"[ROUTER] Web fetch error: {e}", exc_info=True)
            return {
                "text": f"An error occurred while fetching the webpage: {str(e)}",
                "provider": "error",
                "model": None,
                "task_type": "error",
                "metadata": {"error_type": "exception", "error_message": str(e)}
            }

    # =============================
    # Action Intent Routing
    # =============================
    # Route action intents to ActionRouter instead of LLM providers
    # Get action intents from database (configurable per user)
    user_id = normalize_user_id(context.get("user_id"))
    action_intents = memory.get_action_intents(user_id) if memory else []

    # Add hardcoded task and plex intents that should always route to ActionRouter
    # These are not yet in the database migration but need to work
    TASK_INTENTS = ["read_tasks", "read_tasks_today", "read_tasks_week", "create_task", "complete_task", "update_task", "delete_task", "plex"]

    # Combine database intents with hardcoded task intents
    all_action_intents = action_intents + TASK_INTENTS

    logging.info(f"[ROUTER] user_id={user_id}, intent={intent}, action_intents={action_intents}, in_list={intent in all_action_intents}")

    if intent in all_action_intents:
        _debug(memory, f"Routing to ActionRouter for intent: {intent}")

        # Block personal actions (M365 calendar/email/tasks) in work mode
        PERSONAL_ACTIONS = ["read_calendar", "book_appointment", "update_appointment", "cancel_appointment", "read_email", "compose_email", "read_tasks", "read_tasks_today", "read_tasks_week", "create_task", "complete_task"]
        current_mode = context.get("mode", "personal")

        if current_mode == "work" and intent in PERSONAL_ACTIONS:
            _debug(memory, f"Blocked personal action '{intent}' in work mode")
            return {
                "text": "Calendar, email, and task actions are not available in Work mode. These are personal actions. Please switch to Personal mode to use these features.",
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
            memory.store_memory(DEFAULT_USER_ID, memory_type, key, value)
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

    provider_cfg = select_provider(intent, memory, forced, user_id)

    logging.info(f"[ROUTER] Selected provider config: id={provider_cfg.get('id')}, type={provider_cfg.get('type')}, model={provider_cfg.get('model')}")

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
            DEFAULT_USER_ID,
            "last_routing_decision",
            json.dumps(routing_decision),
        )

    _debug_log(memory, f"[ROUTER] About to instantiate provider type: {provider_cfg.get('type')}")
    try:
        provider = instantiate_provider(provider_cfg)
        _debug_log(memory, f"[ROUTER] Provider instantiated successfully")
    except Exception as e:
        logging.error(f"[ROUTER] Failed to instantiate provider: {e}")
        raise

    fallback_reason = provider_cfg.get("fallback_reason", None)
    if fallback_reason:
        _debug(memory, "Provider fallback", reason=fallback_reason)

    _debug(memory, f"Selected provider: {provider_cfg['id']}")


    # Get actual model from provider instance (falls back to config if not available)
    actual_model = getattr(provider, 'model', None) or provider_cfg.get("model")

    meta = {
        "provider": provider_cfg["id"],
        "provider_name": provider_cfg.get("name"),
        "provider_type": provider_cfg.get("type"),
        "model": actual_model,
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
        user_id=context.get("user_id"),
    )
    system_prompt = context_obj["system"]
    messages = context_obj["messages"]

    # Step 3: Add request timing and error handling with fallback
    import time
    start_time = time.time()
    session_id = context.get("session_id", "default")

    try:
        # Use stream_chat if available and streaming is requested
        if stream and hasattr(provider, 'stream_chat'):
            _debug_log(memory, f"[ROUTER] About to call provider.stream_chat() for {provider_cfg['id']} (type: {provider_cfg.get('type')}, model: {provider_cfg.get('model')})")
            raw = provider.stream_chat(
                system=system_prompt,
                messages=messages,
            )
        else:
            _debug_log(memory, f"[ROUTER] About to call provider.chat() for {provider_cfg['id']} (type: {provider_cfg.get('type')}, model: {provider_cfg.get('model')})")
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

            # Extract actual token usage from provider
            input_tokens = 0
            output_tokens = 0
            if hasattr(provider, '_last_usage'):
                input_tokens = provider._last_usage.get("input_tokens", 0)
                output_tokens = provider._last_usage.get("output_tokens", 0)
                logging.info(f"[ROUTER] Token usage: {input_tokens} input, {output_tokens} output")

            # Calculate cost
            estimated_cost = memory.estimate_cost(provider_cfg["id"], input_tokens, output_tokens)

            memory.log_request(
                session_id=session_id,
                provider_id=provider_cfg["id"],
                intent=intent,
                success=True,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
            )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_msg = str(e)

        # Always log provider failures
        logging.error(f"[ROUTER] Provider {provider_cfg['id']} failed: {error_msg}")
        _debug(memory, f"Provider {provider_cfg['id']} failed", error=error_msg)

        # Log failure
        if memory:
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

        # First check for user-configured fallback provider
        alternative_cfg = None
        if memory and user_id:
            fallback_provider_id = memory.get_fallback_provider(user_id, intent)
            if fallback_provider_id:
                from core.provider_registry import ProviderRegistry
                registry = ProviderRegistry(memory)
                alternative_cfg = registry.get(fallback_provider_id)
                if alternative_cfg:
                    _debug(memory, f"Using configured fallback provider: {fallback_provider_id}")

        # If no configured fallback, use automatic selection
        if not alternative_cfg:
            alternative_cfg = select_provider(intent, memory, forced_provider=None, user_id=user_id)

        if alternative_cfg["id"] != provider_cfg["id"] and alternative_cfg["id"] != "mock":
            _debug(memory, f"Fallback to {alternative_cfg['id']}")
            provider = instantiate_provider(alternative_cfg)

            try:
                # Use stream_chat if available and streaming is requested
                if stream and hasattr(provider, 'stream_chat'):
                    raw = provider.stream_chat(
                        system=system_prompt,
                        messages=messages,
                    )
                else:
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

    # CRITICAL DEBUG: Log stream parameter value before branching
    logging.info(f"[ROUTER] Checking stream parameter: stream={stream}, type={type(stream)}")

    if stream:
        def stream_generator():
            full_text = []
            # CodeQL suppression: meta['provider'] is provider name (e.g., "openai"), not sensitive data
            logging.info(f"[ROUTER STREAM] Starting stream generator for provider {meta['provider']}")  # nosemgrep: python.lang.security.audit.logging-sensitive-data

            for chunk in raw:
                if isinstance(chunk, dict):
                    token = chunk.get("token") or chunk.get("text")
                else:
                    token = chunk

                if token:
                    full_text.append(token)
                    # CodeQL suppression: token is AI response text, not sensitive credentials
                    logging.debug(f"[ROUTER STREAM] Yielding token: {token[:50]}...")  # nosemgrep: python.lang.security.audit.logging-sensitive-data
                    yield {
                        "token": token
                    }

            logging.info(f"[ROUTER STREAM] Stream complete, total length: {len(''.join(full_text))}")

            # Note: Memory persistence is handled by context_manager.update() in message_routes.py
            # Don't persist here to avoid duplicate saves

            # Construct full request context for debugging LLM responses
            full_request_context = [{"role": "system", "content": system_prompt}] + messages

            # ⬇️ THIS IS THE IMPORTANT PART ⬇️
            end_event = {
                "event": "end",
                "provider": meta["provider"],
                "model": meta["model"],
                "task_type": meta["task_type"],
                "fallback_reason": meta["fallback_reason"],
                "routing": meta["routing"],
                "full_request_context": full_request_context,
                "metadata": {
                    "provider_name": meta.get("provider_name"),
                    "provider_type": meta.get("provider_type"),
                }
            }

            # Include citations and other provider-specific metadata if available
            if hasattr(provider, '_last_usage'):
                citations = provider._last_usage.get("citations", [])
                web_grounded = provider._last_usage.get("web_grounded", False)
                if citations:
                    end_event["metadata"]["citations"] = citations
                if web_grounded:
                    end_event["metadata"]["web_grounded"] = web_grounded

            yield end_event

        return stream_generator()

    text_out = raw.get("text") if isinstance(raw, dict) else raw

    _debug(memory, f"Response length: {len(text_out) if isinstance(text_out, str) else 'unknown'}")

    # Check if message debug is enabled
    debug_instruction = None
    if memory:
        # Normalize user_id for unauthenticated users
        check_user_id = normalize_user_id(user_id)
        prefs = memory.get_all(check_user_id)
        message_debug_enabled = str(prefs.get("message_debug_enabled", "false")).lower() == "true"

        logging.info(f"[MESSAGE_DEBUG] check_user_id={check_user_id}, message_debug_enabled={message_debug_enabled}, prefs={prefs}")

        if message_debug_enabled:
            logging.info(f"[MESSAGE_DEBUG] Adding debug instruction to response")
            debug_instruction = {
                "system": system_prompt,
                "messages": messages
            }

    # Construct full request context for debugging LLM responses
    full_request_context = [{"role": "system", "content": system_prompt}] + messages

    result = {
        "text": text_out,
        "provider": meta["provider"],
        "model": meta["model"],
        "task_type": meta["task_type"],
        "fallback_reason": meta["fallback_reason"],
        "routing": meta["routing"],
        "full_request_context": full_request_context,
        "metadata": {
            "provider_name": meta.get("provider_name"),
            "provider_type": meta.get("provider_type"),
        }
    }

    # Include citations and other provider-specific metadata if available
    if hasattr(provider, '_last_usage'):
        citations = provider._last_usage.get("citations", [])
        web_grounded = provider._last_usage.get("web_grounded", False)
        if citations:
            result["metadata"]["citations"] = citations
        if web_grounded:
            result["metadata"]["web_grounded"] = web_grounded

    if debug_instruction:
        result["debug_instruction"] = debug_instruction

    # CRITICAL DEBUG: Log return type before returning
    logging.info(f"[ROUTER] route_request returning type={type(result)}, keys={result.keys()}")
    return result