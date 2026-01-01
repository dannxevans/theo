"""
Enhanced Intent Classification with LLM-assisted disambiguation.

This module provides a tiered approach to intent classification:
1. Context-aware keyword matching (free, fast)
2. Mode and sub-tab awareness (free, fast)
3. LLM-assisted disambiguation (cheap Haiku, only when ambiguous)
"""

import logging
from typing import Optional, Dict, List, Tuple
import re


class IntentClassifier:
    """
    Hybrid intent classifier that uses keywords + LLM for ambiguous cases.

    Cost-conscious design:
    - Tier 1: Free context checks (work mode, sub-tab, message length)
    - Tier 2: Free keyword matching with mode-aware weighting
    - Tier 3: Cheap LLM clarification (Haiku, only when confidence < 70%)
    """

    def __init__(self, memory=None, provider_registry=None):
        self.memory = memory
        self.provider_registry = provider_registry

    def classify(
        self,
        text: str,
        user_id: Optional[int] = None,
        mode: Optional[str] = None,
        subtab: Optional[str] = None
    ) -> Tuple[str, float]:
        """
        Classify user intent with confidence score.

        Args:
            text: User's message
            user_id: User ID for pending confirmations check
            mode: Work mode (work/personal)
            subtab: Sub-tab in work mode (code/email/conversation)

        Returns:
            Tuple of (intent, confidence_score)
            confidence_score: 0.0-1.0, where 1.0 is 100% confident
        """
        if not text:
            return "general", 1.0

        text_l = text.lower()

        # =============================
        # Tier 1: Context-Based Filtering
        # =============================
        context_result = self._check_context_signals(text, text_l, mode, subtab)
        if context_result:
            intent, confidence = context_result
            logging.info(f"[INTENT] Context check → {intent} (confidence: {confidence:.2f})")
            if confidence >= 0.9:  # Very high confidence from context
                return intent, confidence

        # =============================
        # Tier 2: Keyword Matching
        # =============================
        keyword_result = self._keyword_match(
            text, text_l, user_id, mode, subtab
        )
        intent, confidence = keyword_result

        logging.info(f"[INTENT] Keyword match → {intent} (confidence: {confidence:.2f})")

        # If high confidence, return immediately
        if confidence >= 0.8:
            return intent, confidence

        # =============================
        # Tier 3: LLM Disambiguation
        # =============================
        # Only use LLM if:
        # 1. Confidence is low (< 0.8)
        # 2. Intent is an action (not general conversation)
        # 3. Provider registry is available

        action_intents = [
            "book_appointment", "update_appointment", "cancel_appointment",
            "read_calendar", "compose_email", "read_email", "weather", "routing", "planning"
        ]

        if confidence < 0.8 and intent in action_intents and self.provider_registry:
            logging.info(f"[INTENT] Low confidence ({confidence:.2f}), using LLM to clarify...")
            llm_intent, llm_confidence = self._llm_clarify(
                text, intent, mode, subtab
            )
            if llm_confidence > confidence:
                logging.info(f"[INTENT] LLM override → {llm_intent} (confidence: {llm_confidence:.2f})")
                return llm_intent, llm_confidence

        return intent, confidence

    def _check_context_signals(
        self,
        text: str,
        text_l: str,
        mode: Optional[str],
        subtab: Optional[str]
    ) -> Optional[Tuple[str, float]]:
        """
        Check context signals that strongly indicate intent.

        Returns None if no strong signal, otherwise (intent, confidence)
        """
        # If in Work Mode > Code Development
        if mode == "work" and subtab == "code":
            # Check for strong technical indicators
            technical_keywords = [
                "function", "script", "automation", "code", "api", "endpoint",
                "database", "query", "sql", "javascript", "python", "servicenow",
                "workflow", "implement", "algorithm", "refactor", "debug"
            ]

            technical_count = sum(1 for kw in technical_keywords if kw in text_l)

            # If multiple technical keywords, it's definitely coding
            if technical_count >= 2:
                return "coding", 0.95

            # If long technical message (>200 chars) with code context
            if len(text) > 200 and technical_count >= 1:
                return "coding", 0.90

        # If in Work Mode > Email
        if mode == "work" and subtab == "email":
            # In work mode, Email tab is for LLM-assisted email composition/rewriting
            # NOT for M365 email actions (which are personal actions)
            # Calendar actions still explicitly require "add to calendar" etc.
            calendar_explicit = [
                "add to my calendar", "add to calendar", "add this to my calendar",
                "put on calendar", "put this on calendar", "put on my calendar",
                "add appointment", "create appointment", "book me", "schedule me"
            ]
            has_explicit_calendar = any(phrase in text_l for phrase in calendar_explicit)

            if has_explicit_calendar:
                # User explicitly requested calendar action
                return None  # Fall through to keyword matching
            else:
                # Work mode Email tab = LLM assistance with professional emails
                # Return "general" so it goes to LLM, not M365 email actions
                return "general", 0.95

        return None

    def _keyword_match(
        self,
        text: str,
        text_l: str,
        user_id: Optional[int],
        mode: Optional[str],
        subtab: Optional[str]
    ) -> Tuple[str, float]:
        """
        Keyword-based matching with mode-aware confidence scoring.

        Returns: (intent, confidence_score)
        """
        # Check for confirmation intents first
        if self.memory and user_id:
            confirmation_result = self._check_confirmations(text_l, user_id)
            if confirmation_result:
                return confirmation_result  # High confidence

        # Calendar action keywords with confidence weighting
        # Use regex patterns for flexible matching
        import re

        BOOK_APPOINTMENT_STRONG_PATTERNS = [
            r'\badd\b.{0,30}\b(to\s+)?(my\s+)?calendar\b',  # "add X to my calendar"
            r'\bput\b.{0,30}\bon\s+(my\s+)?calendar\b',     # "put X on my calendar"
            r'\bbook\s+me\b',                                 # "book me"
            r'\bschedule\s+me\b',                             # "schedule me"
            r'\bcreate\s+(an?\s+)?appointment\b',            # "create appointment"
            r'\bset\s+up\s+(a\s+)?meeting\b',                # "set up meeting"
        ]

        BOOK_APPOINTMENT_WEAK = ["schedule", "book", "arrange"]

        # Check strong calendar signals with regex
        for pattern in BOOK_APPOINTMENT_STRONG_PATTERNS:
            if re.search(pattern, text_l):
                # Strong signal - these phrases are very explicit
                # Keep high confidence even in code mode
                return "book_appointment", 0.90

        # Check weak calendar signals (require additional context)
        calendar_context = [
            "calendar", "diary", "appointment", "meeting", "lunch", "dinner",
            "today", "tomorrow", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday", "am", "pm"
        ]

        has_calendar_context = any(ctx in text_l for ctx in calendar_context)

        for keyword in BOOK_APPOINTMENT_WEAK:
            if keyword in text_l and has_calendar_context:
                # Weak signal + context
                base_confidence = 0.60

                # Reduce confidence if in technical mode
                if mode == "work" and subtab == "code":
                    # "schedule" in ServiceNow context is likely NOT a calendar action
                    base_confidence = 0.30

                return "book_appointment", base_confidence

        # Email keywords
        email_keywords = [
            "send email", "draft email", "compose email", "write email",
            "email to", "send an email"
        ]

        for keyword in email_keywords:
            if keyword in text_l:
                return "compose_email", 0.90

        # Read calendar
        read_calendar_keywords = [
            "what's on my calendar", "what's in my calendar", "whats on my calendar",
            "whats in my calendar", "check my calendar", "my availability",
            "when am i free", "schedule for", "what do i have",
            "any meetings", "any appointments", "my calendar for", "calendar for",
            "show my calendar", "show me my calendar"
        ]

        for keyword in read_calendar_keywords:
            if keyword in text_l:
                return "read_calendar", 0.85

        # Also check for "what's on" followed by "calendar" or time reference
        if "what" in text_l and "calendar" in text_l:
            return "read_calendar", 0.85

        # Read email/inbox
        read_email_keywords = [
            "what's in my inbox", "whats in my inbox", "check my inbox",
            "check my email", "read my email", "any emails", "any new emails",
            "show me my emails", "what emails", "inbox messages",
            "read the email", "read me the email", "show me the email",
            "open the email", "read that email", "show that email",
            "email about", "email from"
        ]

        for keyword in read_email_keywords:
            if keyword in text_l:
                return "read_email", 0.85

        # Check for pattern: (show|read|open) ... email
        email_action_pattern = r'\b(show|read|open|display)\b.{0,50}\bemail\b'
        if re.search(email_action_pattern, text_l):
            return "read_email", 0.80

        # Weather keywords
        weather_keywords = [
            "what's the weather", "whats the weather", "weather in",
            "weather for", "how's the weather", "hows the weather",
            "temperature in", "temperature for", "forecast for",
            "is it raining", "will it rain", "sunny in"
        ]

        for keyword in weather_keywords:
            if keyword in text_l:
                return "weather", 0.90

        # Check for simple weather queries
        weather_simple = ["weather", "temperature", "forecast"]
        location_indicators = ["in", "at", "for"]

        for weather_word in weather_simple:
            if weather_word in text_l:
                # Check if there's a location indicator nearby
                if any(loc in text_l for loc in location_indicators):
                    return "weather", 0.85

        # Routing keywords
        routing_keywords = [
            "route from", "route to", "directions from", "directions to",
            "how do i get from", "how do i get to", "how to get from",
            "how to get to", "navigate from", "navigate to",
            "distance from", "distance to", "drive from", "drive to",
            "travel from", "travel to"
        ]

        for keyword in routing_keywords:
            if keyword in text_l:
                return "routing", 0.90

        # Check for simple routing queries
        routing_simple = ["route", "directions", "navigate", "navigation"]
        route_indicators = ["from", "to", "between"]

        for route_word in routing_simple:
            if route_word in text_l:
                # Check if there's a route indicator nearby
                if any(ind in text_l for ind in route_indicators):
                    return "routing", 0.85

        # Planning keywords
        planning_keywords = [
            "going to", "planning to", "want to go", "need to go",
            "meeting at", "appointment at", "shopping at",
            "visiting", "heading to", "tomorrow at", "later at",
            "this afternoon at", "tonight at", "going shopping",
            "have an appointment", "need to be at"
        ]

        for keyword in planning_keywords:
            if keyword in text_l:
                # Check if there's a time or location indicator
                time_indicators = ["tomorrow", "today", "tonight", "afternoon", "morning", "at", "pm", "am"]
                location_indicators = ["at", "in", "to"]

                has_time = any(ind in text_l for ind in time_indicators)
                has_location = any(ind in text_l for ind in location_indicators)

                if has_time or has_location:
                    return "planning", 0.90

        # Check user-defined intents (if memory available)
        if self.memory:
            intents = self.memory.list_intents("local")
            enabled_intents = [i for i in intents if i.get("enabled", True)]

            for intent_obj in enabled_intents:
                keywords = intent_obj.get("keywords", "").split(",")
                keywords = [kw.strip().lower() for kw in keywords if kw.strip()]

                for keyword in keywords:
                    if keyword in text_l:
                        return intent_obj["id"], 0.75

        # Default to general
        return "general", 0.50

    def _check_confirmations(
        self,
        text_l: str,
        user_id: int
    ) -> Optional[Tuple[str, float]]:
        """
        Check if message is responding to a pending confirmation.

        Returns (intent, confidence) or None
        """
        from core.confirmation_manager import ConfirmationManager

        conf_manager = ConfirmationManager(self.memory)
        pending = conf_manager.get_pending_confirmations(user_id)

        if not pending:
            return None

        # Approval keywords
        approval_keywords = ["approve", "yes", "confirm", "ok", "looks good", "go ahead", "do it"]
        rejection_keywords = ["reject", "no", "don't", "nevermind", "never mind"]

        # Check for approval
        for keyword in approval_keywords:
            if keyword in ["yes", "ok", "no"]:
                # Require word boundaries for very common words
                pattern = rf'\b{re.escape(keyword)}\b'
                if re.search(pattern, text_l):
                    return "approve_confirmation", 0.95
            else:
                if keyword in text_l:
                    return "approve_confirmation", 0.90

        # Check for rejection
        for keyword in rejection_keywords:
            if keyword in ["no"]:
                pattern = rf'\b{re.escape(keyword)}\b'
                if re.search(pattern, text_l):
                    return "reject_confirmation", 0.95
            else:
                if keyword in text_l:
                    return "reject_confirmation", 0.90

        return None

    def _llm_clarify(
        self,
        text: str,
        suspected_intent: str,
        mode: Optional[str],
        subtab: Optional[str]
    ) -> Tuple[str, float]:
        """
        Use LLM (Haiku - cheapest) to clarify ambiguous intent.

        Cost: ~$0.001 per call (Haiku is very cheap)

        Returns: (intent, confidence)
        """
        try:
            # Get Haiku provider (cheapest)
            haiku_providers = [
                p for p in self.provider_registry.list_providers()
                if "haiku" in p["id"].lower()
            ]

            if not haiku_providers:
                logging.warning("[INTENT] No Haiku provider available for LLM clarification")
                return suspected_intent, 0.50

            provider_id = haiku_providers[0]["id"]

            # Construct a simple yes/no prompt
            context_info = ""
            if mode and subtab:
                context_info = f"\n\nContext: User is in {mode.upper()} mode, specifically in the '{subtab}' tab."

            prompt = f"""You are helping classify user intent. Answer with ONLY the intent name, nothing else.

User message: "{text}"{context_info}

Question: Is this message asking to CREATE A CALENDAR EVENT/APPOINTMENT?

Answer ONLY with one of these exact words:
- "book_appointment" if YES, they want to add something to their calendar
- "coding" if this is a technical/programming question
- "compose_email" if this is about writing/sending an email
- "general" if none of the above

Answer:"""

            # Call Haiku (very cheap, very fast)
            provider = self.provider_registry.get_provider(provider_id)
            if not provider:
                return suspected_intent, 0.50

            response = provider.complete(prompt, max_tokens=20)
            llm_intent = response.strip().lower()

            # Validate LLM response
            valid_intents = [
                "book_appointment", "coding", "compose_email", "general",
                "read_calendar", "update_appointment", "cancel_appointment"
            ]

            if llm_intent in valid_intents:
                # LLM gave a clear answer
                return llm_intent, 0.85
            else:
                logging.warning(f"[INTENT] LLM gave unexpected response: {llm_intent}")
                return suspected_intent, 0.50

        except Exception as e:
            logging.error(f"[INTENT] LLM clarification failed: {e}")
            return suspected_intent, 0.50


def classify_intent_enhanced(
    text: str,
    memory=None,
    user_id: Optional[int] = None,
    mode: Optional[str] = None,
    subtab: Optional[str] = None,
    provider_registry=None
) -> str:
    """
    Enhanced intent classification with mode awareness and LLM assistance.

    This is a drop-in replacement for the old classify_intent() function.

    Args:
        text: User's message
        memory: MemoryStore instance
        user_id: User ID
        mode: Work mode (work/personal)
        subtab: Sub-tab (code/email/conversation)
        provider_registry: Provider registry for LLM calls

    Returns:
        Intent string (e.g., "coding", "book_appointment", "general")
    """
    classifier = IntentClassifier(memory, provider_registry)
    intent, confidence = classifier.classify(text, user_id, mode, subtab)

    logging.info(f"[INTENT] Final classification: {intent} (confidence: {confidence:.2f})")

    return intent
