"""
Intent Reasoning Engine - LLM-powered intent classification with structured output.

This module provides an AI-powered reasoning layer that analyzes user input to:
- Classify intent with confidence scoring
- Extract rich entities (locations, times, people, activities, items)
- Signal relevant services for orchestration
- Provide reasoning explanations for debugging

Design principles:
- Token efficient: <500 tokens per resolution
- Fast: <2 second latency target
- Graceful degradation: Falls back to existing system
- Observable: All decisions logged for debugging
- Agentic-ready: Outputs service signals for orchestration
"""

import logging
import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List, Any


@dataclass
class ServiceSignal:
    """Indicates a service that may be relevant to the user's request."""
    service: str       # "calendar", "location", "weather", "search", "tasks"
    relevance: float   # 0.0-1.0 how relevant this service is
    reason: str        # Brief explanation of why this service might help


@dataclass
class ExtractedEntities:
    """All entities extracted from user input, regardless of intent."""
    locations: List[str] = field(default_factory=list)       # "Sainsburys", "home", "Manchester"
    datetimes: List[str] = field(default_factory=list)       # "today", "3pm", "tomorrow morning"
    people: List[str] = field(default_factory=list)          # "John", "my wife", "the team"
    activities: List[str] = field(default_factory=list)      # "shopping", "meeting", "workout"
    items: List[str] = field(default_factory=list)           # "groceries", "report", "car"
    durations: List[str] = field(default_factory=list)       # "an hour", "30 minutes"
    urls: List[str] = field(default_factory=list)            # Any URLs mentioned
    raw: Dict[str, Any] = field(default_factory=dict)        # Any other extracted data


@dataclass
class IntentReasoningResult:
    """Complete reasoning output for a user message."""

    # Core classification
    intent: str                          # Classified intent name
    confidence: float                    # 0.0-1.0 confidence score
    reasoning: str                       # Brief explanation of decision

    # Rich entity extraction (NEW - for agentic workflows)
    entities: ExtractedEntities          # All entities, not just intent params

    # Service relevance signals (NEW - for agentic orchestration)
    service_signals: List[ServiceSignal] # Which services might be relevant

    # Intent-specific parameters (existing concept, kept for compatibility)
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Ambiguity handling
    is_ambiguous: bool = False
    clarification_question: Optional[str] = None

    # Metadata
    token_count: int = 0
    latency_ms: int = 0
    source: str = "reasoning"  # "reasoning" | "fallback" | "cache"

    # Provider information (for attribution)
    provider_id: Optional[str] = None
    provider_model: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "entities": asdict(self.entities),
            "service_signals": [asdict(s) for s in self.service_signals],
            "parameters": self.parameters,
            "is_ambiguous": self.is_ambiguous,
            "clarification_question": self.clarification_question,
            "token_count": self.token_count,
            "latency_ms": self.latency_ms,
            "source": self.source,
            "provider_id": self.provider_id,
            "provider_model": self.provider_model
        }


class IntentReasoningEngine:
    """
    LLM-powered intent reasoning with structured output.

    Design principles:
    - Token efficient: <500 tokens per resolution
    - Fast: <2 second latency target
    - Graceful degradation: Falls back to existing system
    - Observable: All decisions logged for debugging
    - Agentic-ready: Outputs service signals for orchestration
    - Uses Lightweight LLM System Intent: Leverages existing system routing
      configuration (Settings → Routing → System intent) for provider selection
    """

    TIMEOUT_MS = 2000  # 2 second timeout

    def __init__(self, provider_registry, memory=None, cache_ttl=300, user_id=None):
        self.provider_registry = provider_registry
        self.memory = memory
        self.cache = {}
        self.cache_ttl = cache_ttl
        self.cache_timestamps = {}
        self.user_id = user_id

    def reason(
        self,
        text: str,
        mode: str = None,
        subtab: str = None,
        user_id: int = None,
        conversation_history: list = None
    ) -> IntentReasoningResult:
        """
        Analyze user input and return structured intent reasoning.

        Args:
            text: Current user message
            mode: Current mode (personal/work)
            subtab: Current subtab context
            user_id: User ID
            conversation_history: Recent conversation turns for context (list of {"role": str, "content": str})

        Returns IntentReasoningResult with:
        - Intent classification with confidence
        - Rich entity extraction
        - Service relevance signals
        - Reasoning explanation
        """
        start_time = time.time()

        # Check cache first (don't cache when there's conversation history as context matters)
        cache_key = self._cache_key(text, mode, subtab)
        if not conversation_history:
            if cached := self._get_cached(cache_key):
                cached.source = "cache"
                cached.latency_ms = int((time.time() - start_time) * 1000)
                return cached

        # Try LLM reasoning
        try:
            result = self._llm_reason(text, mode, subtab, conversation_history)
            result.latency_ms = int((time.time() - start_time) * 1000)
            # Only cache if no conversation history
            if not conversation_history:
                self._cache_result(cache_key, result)
            return result
        except Exception as e:
            logging.warning(f"[INTENT_REASONING] LLM failed, using fallback: {e}")
            result = self._fallback_classify(text, mode, subtab, user_id)
            result.latency_ms = int((time.time() - start_time) * 1000)
            return result

    def _cache_key(self, text: str, mode: str, subtab: str) -> str:
        """Generate cache key from inputs."""
        key_str = f"{text}|{mode}|{subtab}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[IntentReasoningResult]:
        """Get cached result if still valid."""
        if cache_key not in self.cache:
            return None
        timestamp = self.cache_timestamps.get(cache_key, 0)
        if time.time() - timestamp > self.cache_ttl:
            del self.cache[cache_key]
            del self.cache_timestamps[cache_key]
            return None
        return self.cache[cache_key]

    def _cache_result(self, cache_key: str, result: IntentReasoningResult):
        """Cache reasoning result."""
        self.cache[cache_key] = result
        self.cache_timestamps[cache_key] = time.time()

    def _llm_reason(self, text: str, mode: str, subtab: str, conversation_history: list = None) -> IntentReasoningResult:
        """
        Use LLM to perform reasoning.

        Leverages the Lightweight LLM System Intent routing configuration.
        This uses the user's configured system provider (Settings → Routing → System intent)
        rather than hardcoding a specific model. Benefits:
        - User can choose cost vs quality tradeoff
        - Consistent with other system tasks (summarization, formatting, etc.)
        - Respects fallback provider configuration
        """
        from core.router import select_provider, instantiate_provider
        from core.user_utils import normalize_user_id

        # Use the system intent routing to get the configured provider
        # This respects user's Settings → Routing → System intent configuration
        user_id = normalize_user_id(self.user_id)

        provider_cfg = select_provider(
            intent="system",  # Use system intent routing
            memory=self.memory,
            forced_provider=None,
            user_id=user_id
        )

        provider = instantiate_provider(provider_cfg)

        if not provider:
            raise RuntimeError(f"Could not instantiate system provider: {provider_cfg.get('id')}")

        logging.info(f"[INTENT_REASONING] Using system provider: {provider_cfg.get('id')} ({provider_cfg.get('model')})")

        system_prompt, user_message = self._build_prompt(text, mode, subtab, conversation_history)

        # Build messages array with conversation history
        messages = []
        if conversation_history:
            # Include recent conversation turns for context
            # Limit to last 3 turns to keep token count low
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            messages.extend(recent_history)
            logging.info(f"[INTENT_REASONING] Including {len(recent_history)} conversation turns for context")

        messages.append({"role": "user", "content": user_message})

        response = provider.chat(system_prompt, messages)

        # Parse response and add provider information
        result = self._parse_response(response, text)
        result.provider_id = provider_cfg.get("id")
        result.provider_model = provider_cfg.get("model")

        return result

    def _build_prompt(self, text: str, mode: str, subtab: str, conversation_history: list = None) -> tuple:
        """Build token-efficient prompt for reasoning. Returns (system_prompt, user_message)."""
        system_prompt = '''Analyze user messages and return structured JSON for intent classification.

IMPORTANT: The assistant is named "Theo". When users say things like "Hi Theo", "Hey Theo", "...Theo?", they are addressing the assistant, NOT referring to a person. Do NOT extract "Theo" as a person entity in these cases.

CRITICAL CONVERSATION CONTEXT RULES:
1. If the assistant asked a CLARIFICATION QUESTION (e.g., "Which location?", "What time?") and the user is providing the MISSING INFORMATION, maintain the ORIGINAL intent.
   Example: User asks about weather → Theo asks "which location?" → User says "London" → STILL weather intent

2. If the assistant COMPLETED A REQUEST (provided data, executed action) and the user is making a CONVERSATIONAL RESPONSE (acknowledgment, opinion, decision), classify as "general" intent.
   Example: User asks for Plex suggestions → Theo shows list → User says "I'll watch Fallout" → general intent (NOT plex)
   Example: User asks for weather → Theo provides weather → User says "thanks!" → general intent (NOT weather)

3. QUERIES vs STATEMENTS:
   - Query (action intent): "what should I watch?", "show me X", "get me Y" - user wants information/action
   - Statement (general intent): "I think I'll watch X", "X is great", "thanks", "perfect" - user is commenting/responding

Intent Distinctions:
- book_appointment: Adding events TO CALENDAR with specific times (e.g., "add lunch to my calendar at 3pm", "schedule meeting tomorrow")
- create_task: Adding TO-DO items WITHOUT specific times (e.g., "add buy milk to my tasks", "remind me to call John")
- read_calendar: Checking calendar/schedule (e.g., "what's on my calendar", "am I free tomorrow")
- read_tasks: Viewing task/to-do list (e.g., "show my tasks", "what do I need to do")
- compose_email: Sending/drafting emails (e.g., "email John about meeting")
- read_email: Reading inbox (e.g., "check my email", "any new messages")
- weather: Weather queries (e.g., "what's the weather", "will it rain")
- routing: Directions/navigation (e.g., "how do I get to", "route from home to work")
- plex: Plex Media Server QUERIES only (e.g., "what should I watch", "anything new on plex", "what was I watching", "what's on deck")
  NOT statements like "I'll watch X", "I'm watching X", "X is a great show"
- whoop: WHOOP fitness tracker QUERIES only (e.g., "how did I sleep", "what's my recovery", "strain score")
  NOT statements like "I slept well", "my recovery was good"
- general: Conversational responses, acknowledgments, opinions, decisions, statements about actions rather than requests for actions

Available Services: calendar, location, weather, search, tasks, email, memory, plex

Entity Extraction Examples:
- "add Lunch at Mums tomorrow at 3pm" → activities:["Lunch at Mums"], datetimes:["tomorrow","3pm"], locations:["Mums"]
- "schedule meeting with John next Tuesday" → activities:["meeting"], people:["John"], datetimes:["next Tuesday"]
- "buy milk and bread" → items:["milk","bread"]

IMPORTANT: For calendar/appointment intents, extract the FULL event description as an activity (e.g., "Lunch at Mums", "Meeting with John", "Doctor appointment")

Return ONLY this JSON structure:
{"intent":"<id>","confidence":0.0-1.0,"entities":{"locations":[],"datetimes":[],"people":[],"activities":[],"items":[]},"services":[{"service":"<id>","relevance":0.0-1.0,"reason":"<brief>"}],"params":{},"reasoning":"<brief>","ambiguous":false,"clarify":null}'''

        # Build user message with conversation context hint if available
        context_note = ""
        if conversation_history and len(conversation_history) > 0:
            context_note = "\n\nNote: Conversation history is provided above. Analyze the current message in context of the ongoing conversation."

        user_message = f'''Context: mode={mode or "personal"}, tab={subtab or "conversation"}

Message: "{text}"{context_note}

Analyze and return JSON.'''

        return system_prompt, user_message

    def _parse_response(self, response: str, original_text: str) -> IntentReasoningResult:
        """Parse LLM response into structured result."""
        try:
            # Clean response - find JSON object
            response = response.strip()
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                response = response[start:end]

            data = json.loads(response)

            # Build entities
            entities_data = data.get("entities", {})
            entities = ExtractedEntities(
                locations=entities_data.get("locations", []),
                datetimes=entities_data.get("datetimes", []),
                people=entities_data.get("people", []),
                activities=entities_data.get("activities", []),
                items=entities_data.get("items", []),
                durations=entities_data.get("durations", []),
                urls=entities_data.get("urls", []),
                raw=entities_data
            )

            # Build service signals
            services_data = data.get("services", [])
            service_signals = [
                ServiceSignal(
                    service=s.get("service", ""),
                    relevance=float(s.get("relevance", 0.5)),
                    reason=s.get("reason", "")
                )
                for s in services_data
            ]

            return IntentReasoningResult(
                intent=data.get("intent", "general"),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=data.get("reasoning", ""),
                entities=entities,
                service_signals=service_signals,
                parameters=data.get("params", {}),
                is_ambiguous=data.get("ambiguous", False),
                clarification_question=data.get("clarify"),
                source="reasoning"
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logging.error(f"[INTENT_REASONING] Failed to parse response: {e}")
            # Return minimal valid result
            return IntentReasoningResult(
                intent="general",
                confidence=0.5,
                reasoning=f"Parse error: {str(e)}",
                entities=ExtractedEntities(),
                service_signals=[],
                source="reasoning"
            )

    def _fallback_classify(
        self,
        text: str,
        mode: str,
        subtab: str,
        user_id: int
    ) -> IntentReasoningResult:
        """Fall back to existing classification system."""
        from core.intent_classifier import IntentClassifier

        classifier = IntentClassifier(self.memory, self.provider_registry)
        intent, confidence = classifier.classify(text, user_id, mode, subtab)

        # Basic entity extraction via regex (fallback)
        entities = self._extract_entities_fallback(text)

        # Basic service signal generation (fallback)
        service_signals = self._generate_service_signals_fallback(text)

        return IntentReasoningResult(
            intent=intent,
            confidence=confidence,
            reasoning="Fallback to keyword classification",
            entities=entities,
            service_signals=service_signals,
            parameters={},
            source="fallback"
        )

    def _extract_entities_fallback(self, text: str) -> ExtractedEntities:
        """Basic regex-based entity extraction for fallback."""
        import re

        entities = ExtractedEntities()
        text_l = text.lower()

        # Extract datetimes
        datetime_patterns = [
            r'\b(today|tomorrow|yesterday)\b',
            r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
            r'\b(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b',
            r'\b(this\s+(?:morning|afternoon|evening|week|weekend))\b',
        ]
        for pattern in datetime_patterns:
            entities.datetimes.extend(re.findall(pattern, text_l))

        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        entities.urls = re.findall(url_pattern, text)

        return entities

    def _generate_service_signals_fallback(self, text: str) -> List[ServiceSignal]:
        """Generate basic service signals from keyword matching."""
        signals = []
        text_l = text.lower()

        service_keywords = {
            "calendar": ["today", "tomorrow", "schedule", "meeting", "appointment", "free", "busy"],
            "location": ["near", "directions", "where", "how far", "closest"],
            "weather": ["weather", "rain", "sunny", "cold", "hot", "umbrella"],
            "search": ["what is", "who is", "find", "look up", "search", "hours", "open"],
            "tasks": ["list", "task", "todo", "remind", "shopping list"],
        }

        for service, keywords in service_keywords.items():
            matches = sum(1 for kw in keywords if kw in text_l)
            if matches > 0:
                relevance = min(0.9, 0.3 + (matches * 0.2))
                signals.append(ServiceSignal(
                    service=service,
                    relevance=relevance,
                    reason=f"Matched {matches} keyword(s)"
                ))

        return signals
