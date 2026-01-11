"""
LLM-first orchestration engine.

Uses Intent Reasoning Engine output to decide when to orchestrate,
then uses Lightweight LLM System for planning and synthesis.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

# Will be imported when needed
# from core.router import route_request
# from core.confirmation_manager import ConfirmationManager


@dataclass
class OrchestrationResult:
    """Result from orchestration attempt."""
    should_orchestrate: bool
    skip_reason: Optional[str] = None
    text: Optional[str] = None
    confirmations: Optional[List] = None
    metadata: Optional[Dict[str, Any]] = None
    needs_clarification: bool = False


class Orchestrator:
    """
    Orchestrates multi-service coordination using LLM-first architecture.

    Philosophy:
    - LLM makes all intelligence decisions
    - Code handles execution and validation
    - Uses Intent Reasoning Engine output (service signals, entities)
    - Routes to Lightweight LLM System (user-configured)
    """

    # Orchestration trigger thresholds
    HIGH_RELEVANCE_THRESHOLD = 0.7
    MIN_HIGH_RELEVANCE_SERVICES = 2
    MIN_COMPLEX_ENTITIES = 3

    def __init__(self, memory):
        """
        Initialize orchestrator.

        Args:
            memory: MemoryStore instance for user facts and data
        """
        self.memory = memory
        self.logger = logging.getLogger(__name__)

    def should_orchestrate(self, reasoning_result) -> OrchestrationResult:
        """
        Decide if orchestration is needed based on Intent Reasoning output.

        LLM-First Approach:
        1. Trust the LLM's orchestration_recommended field (if present)
        2. Fallback to heuristics only if LLM didn't provide recommendation

        Args:
            reasoning_result: IntentReasoningResult from Intent Reasoning Engine

        Returns:
            OrchestrationResult with should_orchestrate flag and reasoning
        """
        # Check if Intent Reasoning detected ambiguity
        if hasattr(reasoning_result, 'is_ambiguous') and reasoning_result.is_ambiguous:
            self.logger.info("[ORCHESTRATOR] Intent Reasoning detected ambiguity")
            # Let the clarification question go through normal routing
            return OrchestrationResult(
                should_orchestrate=False,
                skip_reason="ambiguous_query"
            )

        # LLM-First Decision: Trust the LLM's recommendation (if provided)
        # Check if orchestration_recommended exists AND is not None
        has_llm_recommendation = (
            hasattr(reasoning_result, 'orchestration_recommended') and
            reasoning_result.orchestration_recommended is not None
        )

        if has_llm_recommendation:
            if reasoning_result.orchestration_recommended:
                reason = getattr(reasoning_result, 'orchestration_reason', 'LLM recommended orchestration')
                self.logger.info(f"[ORCHESTRATOR] ✓ LLM recommended orchestration: {reason}")
                return OrchestrationResult(
                    should_orchestrate=True,
                    metadata={"decision_method": "llm", "reason": reason}
                )
            else:
                reason = getattr(reasoning_result, 'orchestration_reason', 'LLM determined orchestration not needed')
                self.logger.info(f"[ORCHESTRATOR] ✗ LLM skipped orchestration: {reason}")
                return OrchestrationResult(
                    should_orchestrate=False,
                    skip_reason="llm_decision",
                    metadata={"decision_method": "llm", "reason": reason}
                )

        # Fallback to heuristics if LLM didn't provide recommendation
        self.logger.info("[ORCHESTRATOR] No LLM recommendation found, using heuristics")

        # Count high-relevance services (LLM told us which services are relevant)
        high_relevance_services = []
        if hasattr(reasoning_result, 'service_signals') and reasoning_result.service_signals:
            high_relevance_services = [
                s for s in reasoning_result.service_signals
                if s.relevance >= self.HIGH_RELEVANCE_THRESHOLD
            ]

        # Count complex entities
        entity_count = 0
        if hasattr(reasoning_result, 'entities') and reasoning_result.entities:
            entities = reasoning_result.entities
            entity_count = (
                len(getattr(entities, 'locations', [])) +
                len(getattr(entities, 'datetimes', [])) +
                len(getattr(entities, 'people', []))
            )

        # Log decision factors
        self.logger.info(
            f"[ORCHESTRATOR] Heuristic factors: "
            f"{len(high_relevance_services)} high-relevance services "
            f"(threshold: {self.HIGH_RELEVANCE_THRESHOLD}), "
            f"{entity_count} complex entities"
        )

        # Decision: 2+ high-relevance services OR 3+ complex entities
        needs_orchestration = (
            len(high_relevance_services) >= self.MIN_HIGH_RELEVANCE_SERVICES or
            entity_count >= self.MIN_COMPLEX_ENTITIES
        )

        if needs_orchestration:
            service_names = [s.service for s in high_relevance_services]
            self.logger.info(
                f"[ORCHESTRATOR] ✓ Triggering orchestration via heuristics "
                f"(services: {', '.join(service_names)})"
            )
            return OrchestrationResult(
                should_orchestrate=True,
                metadata={"decision_method": "heuristics"}
            )
        else:
            self.logger.info(
                f"[ORCHESTRATOR] ✗ Skipping orchestration via heuristics "
                f"(not enough high-relevance services or complex entities)"
            )
            return OrchestrationResult(
                should_orchestrate=False,
                skip_reason="insufficient_complexity",
                metadata={"decision_method": "heuristics"}
            )

    def orchestrate(
        self,
        user_query: str,
        user_id: int,
        session_id: int,
        reasoning_result,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> OrchestrationResult:
        """
        Main orchestration workflow.

        Steps:
        1. Check if orchestration is needed (use Intent Reasoning data)
        2. Plan services to query (LLM call #1)
        3. Gather context from services (code execution)
        4. Synthesize response (LLM call #2) - Phase 3
        5. Create confirmations for actions - Phase 3
        6. Return result

        Args:
            user_query: User's original query
            user_id: User ID
            session_id: Session ID
            reasoning_result: IntentReasoningResult from Intent Reasoning Engine
            conversation_history: Recent conversation turns (optional)

        Returns:
            OrchestrationResult with response text, confirmations, metadata
        """
        self.logger.info(f"[ORCHESTRATOR] Starting orchestration for query: {user_query[:100]}")

        # Step 1: Check if we should orchestrate
        decision = self.should_orchestrate(reasoning_result)

        if not decision.should_orchestrate:
            self.logger.info(f"[ORCHESTRATOR] Skipping: {decision.skip_reason}")
            return decision

        # Step 2: Plan which services to query (LLM decides)
        try:
            service_plan = self._plan_services(
                user_query, user_id, reasoning_result, conversation_history
            )
        except Exception as e:
            self.logger.error(f"[ORCHESTRATOR] Service planning failed: {e}")
            return OrchestrationResult(
                should_orchestrate=False,
                skip_reason="planning_failed",
                metadata={"error": str(e)}
            )

        if not service_plan or not service_plan.get("services_to_query"):
            self.logger.info("[ORCHESTRATOR] No services to query, skipping")
            return OrchestrationResult(
                should_orchestrate=False,
                skip_reason="no_services_planned"
            )

        # Step 3: Gather context from services (code executes)
        gathered_data = self._gather_context(
            service_plan["services_to_query"], user_id
        )

        self.logger.info(f"[ORCHESTRATOR] Gathered data from {len(gathered_data)} service(s)")

        # TODO: Step 4-6: Synthesize response, create confirmations (Phase 3)
        # For now, return placeholder with gathered data
        return OrchestrationResult(
            should_orchestrate=True,
            text=f"Orchestration complete. Gathered data from {len(gathered_data)} services.",
            metadata={
                "phase": "2_complete",
                "services_queried": list(gathered_data.keys()),
                "service_plan": service_plan,
                "gathered_data": gathered_data
            }
        )

    def _plan_services(
        self,
        user_query: str,
        user_id: int,
        reasoning_result,
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> dict:
        """
        Use LLM to plan which service methods to call.

        Args:
            user_query: User's original query
            user_id: User ID
            reasoning_result: IntentReasoningResult with service signals and entities
            conversation_history: Recent conversation turns

        Returns:
            dict: Service plan with services_to_query list
        """
        from core.orchestration.service_registry import get_service_capabilities_prompt
        from core.router import route_request

        self.logger.info("[ORCHESTRATOR] Planning services to query...")

        # Get user facts from memory
        user_facts = self.memory.get_all(user_id)
        facts_str = self._format_user_facts(user_facts)

        # Format Intent Reasoning insights
        service_signals_str = self._format_service_signals(reasoning_result.service_signals)
        entities_str = self._format_entities(reasoning_result.entities)

        # Get service capabilities
        capabilities = get_service_capabilities_prompt()

        # Build LLM prompt for service planning
        prompt = f"""You are planning which services to query for a multi-service request.

User query: "{user_query}"

User facts:
{facts_str}

Intent Reasoning Analysis:
- Detected services: {service_signals_str}
- Extracted entities: {entities_str}

Available services and methods:
{capabilities}

Based on the Intent Reasoning analysis above, plan which SPECIFIC METHODS to call and with what parameters.

IMPORTANT RULES:
1. Only query services with relevance >= 0.7 from Intent Reasoning
2. Use extracted entities for parameters (locations, datetimes, people, etc.)
3. Resolve location aliases: "home" → user's Home Location, "work" → user's Work Location
4. For dates like "this weekend", "tomorrow", calculate actual dates (today is {self._get_current_date()})
5. Keep queries minimal - only what's needed to answer the user's question
6. Maximum 3 service queries total

Respond with JSON only (no markdown):
{{
  "services_to_query": [
    {{"service": "service_name", "method": "method_name", "params": {{"param": "value"}}}}
  ],
  "reasoning": "Brief explanation of why these services"
}}
"""

        # Route to Lightweight LLM System
        # IMPORTANT: Set _skip_orchestration flag to prevent infinite recursion
        context = {
            "user_id": user_id,
            "session_id": "orchestration",  # Special session for internal operations
            "text": prompt,
            "force_intent": "system",  # Use user's configured lightweight LLM
            "mode": "personal",
            "memory": self.memory,
            "_skip_orchestration": True  # Prevent re-entry into orchestration
        }

        # CRITICAL DEBUG: Log before calling route_request
        self.logger.info(f"[ORCHESTRATOR] About to call route_request with context keys: {context.keys()}")
        response = route_request(context, stream=False)

        # CRITICAL DEBUG: Log what route_request returned
        self.logger.info(f"[ORCHESTRATOR] route_request returned type={type(response)}")
        if hasattr(response, 'keys'):
            self.logger.info(f"[ORCHESTRATOR] Response keys: {response.keys()}")

        # Parse LLM response
        try:
            # Debug: Log response type and content
            self.logger.info(f"[ORCHESTRATOR] Response type: {type(response)}")
            if response is None:
                raise ValueError("route_request returned None")
            if isinstance(response, str):
                raise ValueError(f"route_request returned string instead of dict: {response[:100]}")

            # Extract JSON from response (handle potential markdown formatting)
            response_text = response.get("text", "")
            if "```json" in response_text:
                # Extract JSON from markdown code block
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1
                response_text = response_text[json_start:json_end]

            service_plan = json.loads(response_text)
            self.logger.info(f"[ORCHESTRATOR] LLM planned {len(service_plan.get('services_to_query', []))} service queries")
            self.logger.info(f"[ORCHESTRATOR] Reasoning: {service_plan.get('reasoning', 'N/A')}")

            return service_plan

        except json.JSONDecodeError as e:
            self.logger.error(f"[ORCHESTRATOR] Failed to parse LLM service plan: {e}")
            self.logger.error(f"[ORCHESTRATOR] Raw response: {response_text[:200]}")
            raise

    def _gather_context(
        self,
        services_to_query: List[Dict],
        user_id: int
    ) -> Dict[str, Any]:
        """
        Execute service queries and gather context data.

        Args:
            services_to_query: List of service requests from planning
            user_id: User ID

        Returns:
            Dict mapping service names to their results
        """
        from core.orchestration.service_registry import validate_service_request

        gathered_data = {}

        for service_request in services_to_query:
            service = service_request.get("service")
            method = service_request.get("method")
            params = service_request.get("params", {})

            # Validate service request
            is_valid, error_msg = validate_service_request(service, method, params)
            if not is_valid:
                self.logger.warning(f"[ORCHESTRATOR] Invalid service request: {error_msg}")
                gathered_data[service] = {"error": error_msg}
                continue

            # Execute service call
            try:
                self.logger.info(f"[ORCHESTRATOR] Calling {service}.{method}({params})")
                result = self._execute_service(service, method, params, user_id)
                gathered_data[service] = result
                self.logger.info(f"[ORCHESTRATOR] ✓ {service} returned data")

            except Exception as e:
                # Individual service failures don't block orchestration
                self.logger.error(f"[ORCHESTRATOR] ✗ {service}.{method} failed: {e}")
                gathered_data[service] = {"error": str(e)}

        return gathered_data

    def _execute_service(
        self,
        service: str,
        method: str,
        params: Dict,
        user_id: int
    ) -> Any:
        """
        Execute a single service method call.

        Args:
            service: Service name (e.g., "calendar")
            method: Method name (e.g., "get_upcoming_events")
            params: Method parameters
            user_id: User ID

        Returns:
            Service result data

        Raises:
            ValueError: If service or method is not supported
            Exception: If service execution fails
        """
        # Resolve location aliases in params
        params = self._resolve_location_aliases(params, user_id)

        # Route to appropriate service handler
        if service == "calendar":
            return self._execute_calendar_service(method, params, user_id)
        elif service == "weather":
            return self._execute_weather_service(method, params, user_id)
        elif service == "traffic":
            return self._execute_traffic_service(method, params, user_id)
        elif service == "email":
            return self._execute_email_service(method, params, user_id)
        elif service == "tasks":
            return self._execute_tasks_service(method, params, user_id)
        elif service == "web_fetch":
            return self._execute_web_fetch_service(method, params, user_id)
        elif service == "memory":
            return self._execute_memory_service(method, params, user_id)
        elif service == "whoop":
            return self._execute_whoop_service(method, params, user_id)
        elif service == "plex":
            return self._execute_plex_service(method, params, user_id)
        else:
            raise ValueError(f"Unknown service: {service}")

    def _resolve_location_aliases(self, params: Dict, user_id: int) -> Dict:
        """
        Resolve location aliases like 'home' and 'work' to actual addresses.

        Args:
            params: Parameters dict
            user_id: User ID

        Returns:
            Updated params with resolved locations
        """
        resolved = params.copy()

        # Check for location parameters
        for key in ["location", "origin", "destination"]:
            if key in resolved:
                location = resolved[key].lower().strip()

                if location == "home":
                    home_location = self._get_user_fact(user_id, "home location")
                    if home_location:
                        resolved[key] = home_location
                        self.logger.info(f"[ORCHESTRATOR] Resolved 'home' → '{home_location}'")

                elif location == "work":
                    work_location = self._get_user_fact(user_id, "work location")
                    if work_location:
                        resolved[key] = work_location
                        self.logger.info(f"[ORCHESTRATOR] Resolved 'work' → '{work_location}'")

        return resolved

    def _get_user_fact(self, user_id: int, fact_key: str) -> Optional[str]:
        """
        Get a specific user fact from memory.

        Args:
            user_id: User ID
            fact_key: Fact key (case-insensitive)

        Returns:
            Fact value or None
        """
        facts = self.memory.get_all(user_id)
        fact_key_lower = fact_key.lower()

        # memory.get_all() returns a dict, so iterate over key-value pairs
        if isinstance(facts, dict):
            for key, value in facts.items():
                if key.lower() == fact_key_lower:
                    return value
        # Handle list format (if memory.get_memories() was used instead)
        elif isinstance(facts, list):
            for fact in facts:
                if fact.get("key", "").lower() == fact_key_lower:
                    return fact.get("value")

        return None

    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

    def _format_user_facts(self, facts) -> str:
        """
        Format user facts for LLM prompt.

        Args:
            facts: Either dict (from memory.get_all) or list of dicts (from memory.get_memories)

        Returns:
            Formatted string of facts
        """
        if not facts:
            return "None stored"

        lines = []

        # Handle dict format (from memory.get_all)
        if isinstance(facts, dict):
            for key, value in facts.items():
                lines.append(f"- {key}: {value}")
        # Handle list format (from memory.get_memories)
        elif isinstance(facts, list):
            for fact in facts:
                key = fact.get("key", "Unknown")
                value = fact.get("value", "")
                lines.append(f"- {key}: {value}")
        else:
            return "Invalid facts format"

        return "\n".join(lines)

    def _format_service_signals(self, service_signals: List) -> str:
        """Format service signals for LLM prompt."""
        if not service_signals:
            return "None"

        lines = []
        for signal in service_signals:
            if signal.relevance >= self.HIGH_RELEVANCE_THRESHOLD:
                lines.append(
                    f"  - {signal.service}: {signal.relevance:.2f} "
                    f"(reason: {signal.reason})"
                )

        return "\n".join(lines) if lines else "None above threshold"

    def _format_entities(self, entities) -> str:
        """Format extracted entities for LLM prompt."""
        if not entities:
            return "None"

        parts = []

        if getattr(entities, 'locations', []):
            parts.append(f"Locations: {', '.join(entities.locations)}")

        if getattr(entities, 'datetimes', []):
            parts.append(f"Datetimes: {', '.join(entities.datetimes)}")

        if getattr(entities, 'people', []):
            parts.append(f"People: {', '.join(entities.people)}")

        if getattr(entities, 'activities', []):
            parts.append(f"Activities: {', '.join(entities.activities)}")

        if getattr(entities, 'items', []):
            parts.append(f"Items: {', '.join(entities.items)}")

        return "; ".join(parts) if parts else "None"

    # =============================
    # Service Execution Methods
    # =============================

    def _execute_weather_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute weather service method."""
        from core.weather_service import WeatherService

        # Get Weather API key from feature providers
        api_key = self._get_feature_provider_key(user_id, "weather")
        if not api_key:
            raise ValueError("Weather API key not configured")

        weather_service = WeatherService(api_key)

        if method == "get_forecast":
            location = params.get("location")
            if not location:
                raise ValueError("Missing required parameter: location")

            result = weather_service.get_weather(location)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown weather method: {method}")

    def _execute_traffic_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute traffic service method."""
        from core.traffic_service import TrafficService

        # Get HERE API key from feature providers
        api_key = self._get_feature_provider_key(user_id, "here_maps")
        if not api_key:
            raise ValueError("HERE Maps API key not configured")

        traffic_service = TrafficService(api_key)

        if method == "get_route":
            origin = params.get("origin")
            destination = params.get("destination")
            if not origin or not destination:
                raise ValueError("Missing required parameters: origin, destination")

            result = traffic_service.get_traffic_estimate(origin, destination)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown traffic method: {method}")

    def _execute_calendar_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute calendar service method (M365)."""
        from actions.action_registry import ActionProviderRegistry

        # Load M365 provider
        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(user_id)

        providers = registry.get_providers_by_capability("read_calendar", user_id)
        if not providers:
            raise ValueError("No calendar provider configured")

        provider_id, provider = providers[0]  # Use first available provider

        if method == "get_upcoming_events":
            days_ahead = params.get("days_ahead", 7)
            result = provider.read_calendar(days_ahead=days_ahead)
            return {"method": method, "data": result}
        elif method == "check_availability":
            date = params.get("date")
            if not date:
                raise ValueError("Missing required parameter: date")
            # Use read_calendar and filter by date
            result = provider.read_calendar(days_ahead=30)
            # Filter events for the specific date
            filtered = [e for e in result.get("events", []) if e.get("start", "").startswith(date)]
            return {"method": method, "data": {"date": date, "events": filtered}}
        else:
            raise ValueError(f"Unknown calendar method: {method}")

    def _execute_email_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute email service method (M365)."""
        from actions.action_registry import ActionProviderRegistry

        # Load M365 provider
        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(user_id)

        providers = registry.get_providers_by_capability("read_email", user_id)
        if not providers:
            raise ValueError("No email provider configured")

        provider_id, provider = providers[0]

        if method == "get_recent":
            count = params.get("count", 10)
            result = provider.read_email(count=count)
            return {"method": method, "data": result}
        elif method == "search":
            query = params.get("query")
            if not query:
                raise ValueError("Missing required parameter: query")
            result = provider.search_email(query=query)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown email method: {method}")

    def _execute_tasks_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute tasks service method (M365)."""
        from actions.action_registry import ActionProviderRegistry

        # Load M365 provider
        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(user_id)

        providers = registry.get_providers_by_capability("read_tasks", user_id)
        if not providers:
            raise ValueError("No tasks provider configured")

        provider_id, provider = providers[0]

        if method == "get_pending":
            result = provider.read_tasks()
            # provider.read_tasks() returns a list of tasks directly
            tasks = result if isinstance(result, list) else result.get("tasks", [])
            # Filter for incomplete tasks
            pending = [t for t in tasks if not t.get("completed", False)]
            return {"method": method, "data": {"tasks": pending}}
        elif method == "get_by_date":
            date = params.get("date")
            if not date:
                raise ValueError("Missing required parameter: date")
            result = provider.read_tasks()
            # provider.read_tasks() returns a list of tasks directly
            tasks = result if isinstance(result, list) else result.get("tasks", [])
            # Filter tasks by due date (handle None dates)
            filtered = [t for t in tasks if t.get("due_date") and t.get("due_date").startswith(date)]
            return {"method": method, "data": {"date": date, "tasks": filtered}}
        else:
            raise ValueError(f"Unknown tasks method: {method}")

    def _execute_web_fetch_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute web fetch service method."""
        from core.web_fetch import fetch_webpage

        if method == "fetch_url":
            url = params.get("url")
            if not url:
                raise ValueError("Missing required parameter: url")

            content = fetch_webpage(url)
            return {"method": method, "data": {"url": url, "content": content}}
        else:
            raise ValueError(f"Unknown web_fetch method: {method}")

    def _execute_memory_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute memory service method."""
        if method == "search":
            query = params.get("query")
            if not query:
                raise ValueError("Missing required parameter: query")

            # Search user facts/memories
            facts = self.memory.get_all(user_id)
            # Simple keyword matching - facts is a dict
            matching = []
            if isinstance(facts, dict):
                for key, value in facts.items():
                    if query.lower() in key.lower() or query.lower() in str(value).lower():
                        matching.append({"key": key, "value": value})
            # Handle list format (if memory.get_memories() was used)
            elif isinstance(facts, list):
                matching = [
                    f for f in facts
                    if query.lower() in f.get("key", "").lower() or
                       query.lower() in str(f.get("value", "")).lower()
                ]

            return {"method": method, "data": {"query": query, "results": matching}}
        else:
            raise ValueError(f"Unknown memory method: {method}")

    def _execute_whoop_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute WHOOP service method."""
        from actions.action_registry import ActionProviderRegistry

        # Note: WHOOP is currently not in ActionProviderRegistry
        # This is a placeholder for future implementation
        raise NotImplementedError("WHOOP service integration pending")

    def _execute_plex_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute Plex service method."""
        from actions.action_registry import ActionProviderRegistry

        # Load Plex provider
        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(user_id)

        # Get providers that support Plex operations
        plex_providers = [
            (pid, prov) for pid, prov in registry._providers.items()
            if hasattr(prov, 'name') and prov.name == 'plex'
        ]

        if not plex_providers:
            raise ValueError("No Plex provider configured")

        provider_id, provider = plex_providers[0]

        if method == "search_library":
            query = params.get("query")
            if not query:
                raise ValueError("Missing required parameter: query")
            result = provider.search_library(query=query)
            return {"method": method, "data": result}
        elif method == "get_history":
            count = params.get("count", 10)
            result = provider.get_watch_history(count=count)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown plex method: {method}")

    def _get_feature_provider_key(self, user_id: int, provider_name: str) -> Optional[str]:
        """
        Get API key for a feature provider.

        Args:
            user_id: User ID
            provider_name: Provider name (e.g., "weather", "here_maps")

        Returns:
            API key string or None if not found
        """
        try:
            # Get the API key directly from memory.get_all()
            # Weather and HERE Maps keys are stored with specific key names
            prefs = self.memory.get_all(user_id)

            # Map provider names to preference keys
            key_mapping = {
                "weather": "feature_provider_openweather_api_key",
                "here_maps": "feature_provider_here_api_key"
            }

            pref_key = key_mapping.get(provider_name)
            if pref_key and pref_key in prefs:
                return prefs[pref_key]

            return None
        except Exception as e:
            self.logger.error(f"[ORCHESTRATOR] Failed to get API key for {provider_name}: {e}")
            return None
