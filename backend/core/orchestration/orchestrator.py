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

    # Class-level cache for clarification contexts (session_id -> context_data)
    _clarification_contexts = {}

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
        # BUT: Don't skip if multiple services detected - orchestrator can handle missing info via defaults
        # ALSO: Don't skip for appointment booking - orchestrator can find available slots
        if hasattr(reasoning_result, 'is_ambiguous') and reasoning_result.is_ambiguous:
            has_multiple_services = len(reasoning_result.service_signals) > 1
            is_appointment_booking = reasoning_result.intent in ['book_appointment', 'calendar_create']

            if not has_multiple_services and not is_appointment_booking:
                self.logger.info("[ORCHESTRATOR] Intent Reasoning detected ambiguity (single service, not appointment)")
                # Let the clarification question go through normal routing
                return OrchestrationResult(
                    should_orchestrate=False,
                    skip_reason="ambiguous_query"
                )
            elif is_appointment_booking:
                self.logger.info(f"[ORCHESTRATOR] Ambiguity detected but appointment booking intent - forcing orchestration to find available slots")
                # Force orchestration for appointment booking with vague timing
                return OrchestrationResult(
                    should_orchestrate=True,
                    metadata={"decision_method": "appointment_booking_override", "reason": "Appointment booking with vague timing requires calendar availability check"}
                )
            else:
                self.logger.info(f"[ORCHESTRATOR] Ambiguity detected but multiple services present ({[s.service for s in reasoning_result.service_signals]}) - proceeding with orchestration")

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

        # Step 0: Check if this is a clarification response
        clarification_context = self._get_clarification_context(user_id, session_id)
        if clarification_context:
            self.logger.info(
                f"[ORCHESTRATOR] Detected clarification response for: "
                f"{clarification_context.get('original_query')}"
            )

            # Check if this looks like an address response
            if self._is_address_response(user_query, reasoning_result):
                # Store the address in memory
                person_name = clarification_context.get("missing_person")
                self._store_person_address(user_id, person_name, user_query)

                # Clear clarification context
                self._clear_clarification_context(user_id, session_id)

                # Resume original orchestration with the original query
                original_query = clarification_context.get("original_query")
                self.logger.info(f"[ORCHESTRATOR] Resuming orchestration with: {original_query}")

                # Re-run orchestration with the original query
                # We need to re-classify the original query to get fresh reasoning
                from core.intent_reasoning import IntentReasoningEngine
                from core.providers.registry import ProviderRegistry

                # Get fresh reasoning for the original query
                provider_registry = ProviderRegistry(self.memory)
                reasoning_engine = IntentReasoningEngine(
                    provider_registry,
                    self.memory,
                    user_id=user_id
                )
                resumed_reasoning = reasoning_engine.reason(
                    original_query,
                    mode="personal",  # TODO: Get actual mode from context
                    subtab=None,
                    conversation_history=conversation_history
                )

                # Continue orchestration with the original query
                user_query = original_query
                reasoning_result = resumed_reasoning

        # Step 1: Check if we should orchestrate
        decision = self.should_orchestrate(reasoning_result)

        if not decision.should_orchestrate:
            self.logger.info(f"[ORCHESTRATOR] Skipping: {decision.skip_reason}")
            return decision

        # Step 1.5: Validate that person-based locations are known
        validation_result = self._validate_person_locations(reasoning_result, user_id, user_query)
        if validation_result:
            # Need clarification - store context and return clarification question
            self.logger.info(f"[ORCHESTRATOR] Person location unknown, requesting clarification")

            # Store the original query context in session memory for resumption
            self._store_clarification_context(
                user_id=user_id,
                session_id=session_id,
                original_query=user_query,
                missing_person=validation_result["missing_person"],
                location_ref=validation_result["location_ref"]
            )

            return OrchestrationResult(
                should_orchestrate=False,
                skip_reason="missing_person_location",
                text=validation_result["clarification_question"],
                needs_clarification=True,
                metadata={
                    "awaiting_clarification": True,
                    "clarification_type": "person_location",
                    "missing_person": validation_result["missing_person"],
                    "original_query": user_query
                }
            )

        # Step 2: Plan which services to query (LLM decides)
        try:
            service_plan, processed_entities = self._plan_services(
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

        # Step 4: Synthesize response (LLM call #2)
        try:
            synthesis_result = self._synthesize_response(
                user_query=user_query,
                user_id=user_id,
                gathered_data=gathered_data,
                service_plan=service_plan,
                conversation_history=conversation_history,
                processed_entities=processed_entities
            )
        except Exception as e:
            self.logger.error(f"[ORCHESTRATOR] Response synthesis failed: {e}")
            # Fall back to raw data display
            synthesis_result = {
                "response": f"I gathered data from {len(gathered_data)} services, but couldn't synthesize a response. Raw data: {gathered_data}",
                "needs_confirmation": False,
                "proposed_actions": []
            }

        # Step 5: Create confirmations for actions (if needed)
        confirmations = []
        proposed_actions = synthesis_result.get("proposed_actions", [])

        if proposed_actions:
            from core.confirmation_manager import ConfirmationManager

            # Initialize ConfirmationManager
            # Note: action_router will be None here - it's only needed for execution (approval phase)
            # The ActionRouter will be set when the confirmation is approved via the frontend
            confirmation_manager = ConfirmationManager(self.memory, action_router=None)

            self.logger.info(f"[ORCHESTRATOR] Creating {len(proposed_actions)} confirmation(s)")

            for action in proposed_actions:
                try:
                    # Validate action structure
                    action_type = action.get("type")
                    action_params = action.get("params", {})
                    confirmation_message = action.get("confirmation_message")

                    if not action_type:
                        self.logger.error(f"[ORCHESTRATOR] Action missing 'type' field: {action}")
                        continue

                    if not confirmation_message:
                        self.logger.warning(f"[ORCHESTRATOR] Action missing 'confirmation_message', using default")
                        confirmation_message = f"Confirm {action_type}?"

                    # Create confirmation in database
                    confirmation = confirmation_manager.create_confirmation(
                        user_id=user_id,
                        session_id=session_id,  # Use real session_id (not "orchestration")
                        action_type=action_type,
                        action_params=action_params,
                        confirmation_message=confirmation_message,
                        provider_id=None,  # Will be resolved during execution
                        expires_in_hours=24  # Standard 24-hour expiration
                    )

                    confirmations.append(confirmation)
                    self.logger.info(
                        f"[ORCHESTRATOR] Created confirmation {confirmation['confirmation_id']} "
                        f"for {action_type} (expires: {confirmation['expires_at']})"
                    )

                except Exception as e:
                    self.logger.error(f"[ORCHESTRATOR] Failed to create confirmation: {e}", exc_info=True)
                    # Continue processing other actions even if one fails
                    continue

            if confirmations:
                self.logger.info(f"[ORCHESTRATOR] Successfully created {len(confirmations)} confirmation(s)")
            else:
                self.logger.warning("[ORCHESTRATOR] No confirmations created (all failed validation)")

        # Step 6: Return result
        return OrchestrationResult(
            should_orchestrate=True,
            text=synthesis_result["response"],
            confirmations=confirmations,
            metadata={
                "phase": "4_complete",  # Updated to Phase 4 (Action Confirmation & Execution)
                "services_queried": list(gathered_data.keys()),
                "service_plan": service_plan,
                "gathered_data": gathered_data,
                "proposed_actions": synthesis_result.get("proposed_actions", []),
                "confirmations": confirmations,  # Include confirmations in metadata for frontend
                "synthesis_provider": synthesis_result.get("synthesis_provider"),
                "synthesis_model": synthesis_result.get("synthesis_model")
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

        # Pre-process entities to parse relative dates in Python
        processed_entities = self._preprocess_entities(reasoning_result.entities)

        # Format Intent Reasoning insights
        service_signals_str = self._format_service_signals(reasoning_result.service_signals)
        entities_str = self._format_entities(processed_entities)

        # Debug: Log what entities the LLM will see
        self.logger.info(f"[ORCHESTRATOR] Entities being passed to LLM: {entities_str}")

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

CRITICAL RULES FOR DATE PARAMETERS:
- NEVER calculate dates yourself from the user query
- ONLY use dates from the "Extracted entities" section above
- The dates in entities are ALREADY CALCULATED and in YYYY-MM-DD format
- Example: If entities shows "Datetimes: 2026-01-14", use "2026-01-14" - do NOT recalculate it
- TODAY is {self._get_current_date()} (for reference only)

OTHER RULES:
1. Only query services with relevance >= 0.5 from Intent Reasoning
2. Use extracted entities for ALL parameters (locations, datetimes, people, etc.)
3. **INFER USER'S LOCATION FROM CALENDAR CONTEXT**:
   - If querying traffic/routing, check if the target time falls during a calendar event
   - If user has a calendar event at that time with a location, route FROM that location
   - Example: Event "Work (Office)" at Colgate Lane from 07:00-17:00, pickup at 14:00 → route from Colgate Lane
   - Only use "home" as origin if no calendar event at that time
   - Location aliases: "home" → user's Home Location, "work" → user's Work Location
4. Keep queries minimal - only what's needed to answer the user's question
5. Maximum 3 service queries total

Respond with JSON only (no markdown):
{{
  "services_to_query": [
    {{"service": "service_name", "method": "method_name", "params": {{"param": "value"}}}}
  ],
  "reasoning": "Brief explanation of why these services"
}}
"""

        # Route to Orchestration Planning intent
        # IMPORTANT: Set _skip_orchestration flag to prevent infinite recursion
        context = {
            "user_id": user_id,
            "session_id": "orchestration",  # Special session for internal operations
            "text": prompt,
            "force_intent": "system_orchestration_planning",  # Use orchestration planning intent
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

            # Post-process the plan to fix dates (LLM sometimes ignores our instructions)
            service_plan = self._fix_service_plan_dates(service_plan, processed_entities)

            return service_plan, processed_entities

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
        calendar_events = None  # Track calendar events for location inference

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

            # SMART LOCATION INFERENCE: If this is a traffic query and we have calendar data, infer origin
            if service == "traffic" and method == "get_route" and calendar_events is not None:
                params = self._infer_traffic_origin_from_calendar(params, calendar_events, user_id)

            # Execute service call
            try:
                self.logger.info(f"[ORCHESTRATOR] Calling {service}.{method}({params})")
                result = self._execute_service(service, method, params, user_id)
                gathered_data[service] = result
                self.logger.info(f"[ORCHESTRATOR] ✓ {service} returned data")

                # Store calendar events for location inference
                if service == "calendar" and "data" in result and "events" in result["data"]:
                    calendar_events = result["data"]["events"]

            except Exception as e:
                # Individual service failures don't block orchestration
                self.logger.error(f"[ORCHESTRATOR] ✗ {service}.{method} failed: {e}")
                gathered_data[service] = {"error": str(e)}

        return gathered_data

    def _infer_traffic_origin_from_calendar(
        self,
        traffic_params: Dict,
        calendar_events: List[Dict],
        user_id: int
    ) -> Dict:
        """
        Intelligently infer traffic origin based on calendar events.

        If the user has a calendar event at the time they need to travel,
        use that event's location as the origin instead of defaulting to 'home'.

        Args:
            traffic_params: Original traffic params (may have origin='home')
            calendar_events: List of calendar events
            user_id: User ID

        Returns:
            Updated traffic params with corrected origin
        """
        from datetime import datetime, time

        origin = traffic_params.get("origin", "home")

        # Only adjust if origin is 'home' (the default)
        if origin != "home":
            return traffic_params

        # Try to infer the target time from context
        # For now, use a simple heuristic: check if any event is happening during typical work hours
        # TODO: Make this smarter by parsing the actual destination arrival time

        for event in calendar_events:
            start_time_str = event.get("start_time", "")
            end_time_str = event.get("end_time", "")
            location = event.get("location", "")

            # Skip events without location
            if not location:
                continue

            try:
                # Parse times (handle M365's 7-digit fractional seconds)
                # M365 format: "2026-01-14T07:00:00.0000000"
                # Python's fromisoformat only handles up to 6 digits
                start_time_clean = start_time_str.split('.')[0]  # Remove fractional seconds
                end_time_clean = end_time_str.split('.')[0]
                start_time = datetime.fromisoformat(start_time_clean)
                end_time = datetime.fromisoformat(end_time_clean)

                # If this is a work event during the day, use it as origin
                # Heuristic: Events longer than 4 hours during daytime are likely work
                duration_hours = (end_time - start_time).total_seconds() / 3600
                is_daytime = 6 <= start_time.hour <= 18

                if duration_hours >= 4 and is_daytime:
                    self.logger.info(
                        f"[ORCHESTRATOR] Inferring origin from calendar: "
                        f"Event '{event.get('subject')}' at {location} "
                        f"({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
                    )
                    traffic_params["origin"] = location
                    return traffic_params

            except Exception as e:
                self.logger.warning(f"[ORCHESTRATOR] Failed to parse event times: {e}")
                continue

        # No suitable event found, keep original params
        return traffic_params

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
        Resolve location aliases like 'home', 'work', and person-based locations to actual addresses.

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
                location = resolved[key].strip()
                location_lower = location.lower()

                if location_lower == "home":
                    home_location = self._get_user_fact(user_id, "home location")
                    if home_location:
                        resolved[key] = home_location
                        self.logger.info(f"[ORCHESTRATOR] Resolved 'home' → '{home_location}'")

                elif location_lower == "work":
                    work_location = self._get_user_fact(user_id, "work location")
                    if work_location:
                        resolved[key] = work_location
                        self.logger.info(f"[ORCHESTRATOR] Resolved 'work' → '{work_location}'")

                # Check for person-based locations (e.g., "Mums", "mum's", "Dad's")
                elif location_lower in ["mum", "mums", "mum's", "dad", "dads", "dad's"]:
                    person_name = location_lower.rstrip("s'").rstrip("'s")
                    person_cap = person_name.capitalize()
                    person_address = self._get_user_fact(user_id, f"{person_cap}'s Address")
                    if person_address:
                        resolved[key] = person_address
                        self.logger.info(f"[ORCHESTRATOR] Resolved '{location}' → '{person_address}'")

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
        # get_memories() returns list of memory facts from 'memories' table
        # get_all() returns dict of preferences from 'preferences' table
        memories = self.memory.get_memories(user_id)
        fact_key_lower = fact_key.lower()

        self.logger.info(f"[ORCHESTRATOR] Looking for fact '{fact_key}' (user_id={user_id}), got {len(memories) if memories else 0} memories")

        if isinstance(memories, list):
            for memory in memories:
                # Memory structure: {'key': 'Home Location', 'value': '8 Harefields Way...'}
                mem_key = memory.get("key", "")
                self.logger.info(f"[ORCHESTRATOR] Checking memory key: '{mem_key}' against '{fact_key}'")
                if mem_key.lower() == fact_key_lower:
                    value = memory.get("value")
                    self.logger.info(f"[ORCHESTRATOR] Found match! Returning: '{value}'")
                    return value

        self.logger.warning(f"[ORCHESTRATOR] No memory found for fact '{fact_key}'")
        return None

    def _validate_person_locations(
        self,
        reasoning_result,
        user_id: int,
        user_query: str
    ) -> Optional[Dict[str, str]]:
        """
        Validate that person-based location references have stored addresses.

        Checks extracted locations for person references (e.g., "mum", "dad", "John's")
        and ensures we have a stored address for them before proceeding.

        Args:
            reasoning_result: IntentReasoningResult with entities
            user_id: User ID
            user_query: Original user query for context

        Returns:
            None if validation passes, or dict with "clarification_question" if validation fails
        """
        if not hasattr(reasoning_result, 'entities') or not reasoning_result.entities:
            return None

        entities = reasoning_result.entities
        locations = getattr(entities, 'locations', [])
        people = getattr(entities, 'people', [])

        # Check if any locations are person-based references
        person_based_locations = []
        for location in locations:
            location_lower = location.lower()

            # Check for possessive forms: "mum's", "dad's", "John's", etc.
            if location_lower.endswith("'s") or location_lower.endswith("s'"):
                person_name = location_lower.rstrip("'s").rstrip("s'").strip()
                person_based_locations.append((location, person_name))

            # Check for direct person references: "mum", "dad", "mums", "dads"
            elif location_lower in ["mum", "mums", "mum's", "dad", "dads", "dad's", "parents", "parent's"]:
                person_based_locations.append((location, location_lower.rstrip("s")))

            # Check if location matches any person entity
            elif any(person.lower() in location_lower for person in people):
                person_based_locations.append((location, location))

        if not person_based_locations:
            return None

        # Check if we have stored locations for these people
        for location_ref, person_name in person_based_locations:
            # Try to find stored address
            # Look for patterns like "Mum's Address", "Mum Location", etc.
            # Try with capitalized first (stored by _store_person_address)
            person_cap = person_name.capitalize()
            stored_location = (
                self._get_user_fact(user_id, f"{person_cap}'s Address") or
                self._get_user_fact(user_id, f"{person_cap}'s Location") or
                self._get_user_fact(user_id, f"{person_name}'s address") or
                self._get_user_fact(user_id, f"{person_name}'s location") or
                self._get_user_fact(user_id, f"{person_name} address") or
                self._get_user_fact(user_id, f"{person_name} location")
            )

            if not stored_location:
                # Missing location - request clarification
                self.logger.info(
                    f"[ORCHESTRATOR] Person-based location '{location_ref}' has no stored address"
                )

                # Generate clarification question
                clarification = (
                    f"I'd be happy to help you plan this! However, I don't have your {person_name}'s address stored. "
                    f"Could you tell me where your {person_name} lives so I can provide routing information?"
                )

                return {
                    "clarification_question": clarification,
                    "missing_person": person_name,
                    "location_ref": location_ref
                }

        # All person-based locations are known
        return None

    def _store_clarification_context(
        self,
        user_id: int,
        session_id: int,
        original_query: str,
        missing_person: str,
        location_ref: str
    ):
        """
        Store clarification context in session-based memory.

        Stores the original query and missing information so we can resume
        orchestration when the user provides the clarification.

        Args:
            user_id: User ID
            session_id: Session ID
            original_query: The original user query that needed clarification
            missing_person: The person whose location is missing (e.g., "mum")
            location_ref: The location reference from the query (e.g., "Mums")
        """
        import json

        clarification_data = {
            "original_query": original_query,
            "missing_person": missing_person,
            "location_ref": location_ref,
            "type": "person_location"
        }

        # Store in class-level cache (simple in-memory storage)
        Orchestrator._clarification_contexts[session_id] = clarification_data

        self.logger.info(
            f"[ORCHESTRATOR] Stored clarification context for session {session_id}: "
            f"waiting for {missing_person}'s address"
        )

    def _get_clarification_context(self, user_id: int, session_id: int) -> Optional[Dict]:
        """
        Retrieve stored clarification context for a session.

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Clarification context dict or None if not found
        """
        return Orchestrator._clarification_contexts.get(session_id)

    def _clear_clarification_context(self, user_id: int, session_id: int):
        """Clear clarification context after it's been used."""
        if session_id in Orchestrator._clarification_contexts:
            del Orchestrator._clarification_contexts[session_id]
            self.logger.info(f"[ORCHESTRATOR] Cleared clarification context for session {session_id}")

    def _is_address_response(self, user_query: str, reasoning_result) -> bool:
        """
        Detect if user query looks like an address response.

        Checks for location entities or address-like patterns.

        Args:
            user_query: User's query
            reasoning_result: Intent reasoning result

        Returns:
            True if this looks like an address response
        """
        # Check if reasoning extracted locations
        if hasattr(reasoning_result, 'entities') and reasoning_result.entities:
            locations = getattr(reasoning_result.entities, 'locations', [])
            if locations:
                self.logger.info(f"[ORCHESTRATOR] Detected location entities: {locations}")
                return True

        # Check for address-like patterns (postcode, street name, etc.)
        import re
        # UK postcode pattern
        postcode_pattern = r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b'
        if re.search(postcode_pattern, user_query, re.IGNORECASE):
            self.logger.info(f"[ORCHESTRATOR] Detected postcode pattern in: {user_query}")
            return True

        # Check for street/drive/road/avenue patterns
        street_pattern = r'\b\d+\s+[A-Za-z\s]+(Street|Road|Drive|Avenue|Lane|Way|Close|Court)\b'
        if re.search(street_pattern, user_query, re.IGNORECASE):
            self.logger.info(f"[ORCHESTRATOR] Detected street address pattern in: {user_query}")
            return True

        return False

    def _store_person_address(self, user_id: int, person_name: str, address: str):
        """
        Store a person's address in user memory.

        Args:
            user_id: User ID
            person_name: Person's name (e.g., "mum", "dad")
            address: The address to store
        """
        # Capitalize person name for memory key
        memory_key = f"{person_name.capitalize()}'s Address"

        # Store in memories table (permanent user facts)
        self.memory.store_memory(
            user_id=user_id,
            memory_type="fact",
            key=memory_key,
            value=address.strip(),
            pinned=True  # Pin person addresses so they don't decay
        )

        self.logger.info(f"[ORCHESTRATOR] Stored {memory_key}: {address}")

    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format with day of week."""
        from datetime import datetime
        return datetime.now().strftime("%A, %Y-%m-%d")

    def _fix_dates_in_text(self, text: str, processed_entities) -> str:
        """
        Fix dates in text (like reasoning) to replace incorrect dates with correct ones.

        Args:
            text: Text containing potentially incorrect dates
            processed_entities: Pre-processed entities with correct dates

        Returns:
            Text with dates corrected
        """
        import re

        if not text or not processed_entities:
            return text

        # Extract dates from entities
        entity_dates = []
        if hasattr(processed_entities, 'datetimes'):
            entity_dates = processed_entities.datetimes

        if not entity_dates:
            return text

        # Find all YYYY-MM-DD dates in text
        date_pattern = r'\b(\d{4}-\d{2}-\d{2})\b'
        found_dates = re.findall(date_pattern, text)

        # Replace any dates that don't match entity dates
        corrected_text = text
        for found_date in found_dates:
            if found_date not in entity_dates and len(entity_dates) > 0:
                correct_date = entity_dates[0]
                self.logger.info(
                    f"[ORCHESTRATOR] Correcting date in text: '{found_date}' → '{correct_date}'"
                )
                corrected_text = corrected_text.replace(found_date, correct_date)

        return corrected_text

    def _fix_proposed_action_dates(self, synthesis_result: Dict, processed_entities) -> Dict:
        """
        Post-process proposed actions to fix dates that the LLM got wrong.

        Args:
            synthesis_result: Synthesis result with proposed_actions
            processed_entities: Pre-processed entities with correct dates

        Returns:
            Fixed synthesis result
        """
        import re

        # Extract dates from entities
        entity_dates = []
        if processed_entities and hasattr(processed_entities, 'datetimes'):
            entity_dates = processed_entities.datetimes

        if not entity_dates:
            return synthesis_result

        self.logger.info(f"[ORCHESTRATOR] Fixing dates in proposed actions. Entity dates: {entity_dates}")

        # Fix dates in proposed actions
        proposed_actions = synthesis_result.get('proposed_actions', [])
        for action in proposed_actions:
            params = action.get('params', {})

            # Check for date parameters
            for param_key, param_value in params.items():
                if param_key in ['date', 'start_date', 'end_date', 'due_date']:
                    # Check if this date is in YYYY-MM-DD format
                    if isinstance(param_value, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', param_value):
                        # Check if it differs from our entity dates
                        if param_value not in entity_dates and len(entity_dates) > 0:
                            # LLM used a different date - replace with our calculated one
                            correct_date = entity_dates[0]
                            self.logger.warning(
                                f"[ORCHESTRATOR] Proposed action used wrong date '{param_value}', "
                                f"replacing with correct date '{correct_date}'"
                            )
                            params[param_key] = correct_date

        return synthesis_result

    def _fix_service_plan_dates(self, service_plan: Dict, processed_entities) -> Dict:
        """
        Post-process service plan to fix dates that the LLM got wrong.

        LLMs (especially Haiku) sometimes ignore our instructions and calculate
        their own dates. This method enforces that dates in params match the
        dates we calculated in Python.

        Args:
            service_plan: Service plan from LLM
            processed_entities: Pre-processed entities with correct dates

        Returns:
            Fixed service plan
        """
        from datetime import datetime
        import re

        # Extract dates from entities (already in YYYY-MM-DD format)
        entity_dates = []
        if processed_entities and hasattr(processed_entities, 'datetimes'):
            entity_dates = processed_entities.datetimes

        if not entity_dates:
            # No dates to fix
            return service_plan

        self.logger.info(f"[ORCHESTRATOR] Fixing dates in service plan. Entity dates: {entity_dates}")

        # Iterate through service queries and fix any date parameters
        services_to_query = service_plan.get('services_to_query', [])
        for service_query in services_to_query:
            params = service_query.get('params', {})

            # Check for date parameters
            for param_key, param_value in params.items():
                if param_key in ['date', 'start_date', 'end_date', 'due_date']:
                    if not isinstance(param_value, str):
                        continue

                    # Check if this date is in YYYY-MM-DD format
                    is_valid_format = re.match(r'^\d{4}-\d{2}-\d{2}$', param_value)

                    if is_valid_format:
                        # Check if it differs from our entity dates
                        if param_value not in entity_dates and len(entity_dates) > 0:
                            # LLM used a different date - replace with our calculated one
                            correct_date = entity_dates[0]  # Use first entity date
                            self.logger.warning(
                                f"[ORCHESTRATOR] LLM used wrong date '{param_value}', "
                                f"replacing with correct date '{correct_date}'"
                            )
                            params[param_key] = correct_date
                    else:
                        # Date is not in YYYY-MM-DD format (e.g., "2pm", "Wednesday", etc.)
                        if len(entity_dates) > 0:
                            correct_date = entity_dates[0]  # Use first entity date
                            self.logger.warning(
                                f"[ORCHESTRATOR] LLM used invalid date format '{param_value}', "
                                f"replacing with correct date '{correct_date}'"
                            )
                            params[param_key] = correct_date

        return service_plan

    def _parse_relative_date(self, date_str: str) -> str:
        """
        Parse relative date expressions into YYYY-MM-DD format.

        Handles:
        - "today" → current date
        - "tomorrow" → current date + 1 day
        - Day names: "monday", "tuesday", etc. → next occurrence
        - "this weekend" → next Saturday
        - Already formatted dates (YYYY-MM-DD) → pass through

        Args:
            date_str: Date expression (relative or absolute)

        Returns:
            Date in YYYY-MM-DD format
        """
        from datetime import datetime, timedelta
        import re

        if not date_str:
            return date_str

        date_str_lower = date_str.lower().strip()
        today = datetime.now()

        # Already in YYYY-MM-DD format? Pass through
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str_lower):
            self.logger.info(f"[ORCHESTRATOR] Date already formatted: {date_str}")
            return date_str

        # Handle "today"
        if date_str_lower == "today":
            result = today.strftime("%Y-%m-%d")
            self.logger.info(f"[ORCHESTRATOR] Parsed 'today' → {result}")
            return result

        # Handle "tomorrow"
        if date_str_lower == "tomorrow":
            result = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            self.logger.info(f"[ORCHESTRATOR] Parsed 'tomorrow' → {result}")
            return result

        # Handle day names (monday, tuesday, etc.)
        day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }

        for day_name, day_num in day_names.items():
            if day_name in date_str_lower:
                # Calculate days until next occurrence
                current_day = today.weekday()
                days_ahead = (day_num - current_day) % 7

                # If days_ahead is 0, it means "today" is that day
                # User likely means "next occurrence" which is 7 days away
                if days_ahead == 0:
                    days_ahead = 7

                target_date = today + timedelta(days=days_ahead)
                result = target_date.strftime("%Y-%m-%d")
                self.logger.info(f"[ORCHESTRATOR] Parsed '{day_name}' → {result} (today is {today.strftime('%A')}, {days_ahead} days ahead)")
                return result

        # Handle "this weekend" → Saturday
        if "weekend" in date_str_lower:
            current_day = today.weekday()
            days_until_saturday = (5 - current_day) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            target_date = today + timedelta(days=days_until_saturday)
            result = target_date.strftime("%Y-%m-%d")
            self.logger.info(f"[ORCHESTRATOR] Parsed 'weekend' → {result} (Saturday)")
            return result

        # Couldn't parse - return as-is and let LLM handle it
        self.logger.warning(f"[ORCHESTRATOR] Could not parse date '{date_str}', passing through")
        return date_str

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

    def _preprocess_entities(self, entities):
        """
        Pre-process entities to convert relative dates to absolute dates.

        This ensures date calculations are done in Python, not by the LLM.

        Args:
            entities: Intent reasoning entities object

        Returns:
            Modified entities object with parsed dates
        """
        if not entities:
            return entities

        # Parse datetime entities
        if hasattr(entities, 'datetimes') and entities.datetimes:
            import re
            parsed_datetimes = []
            for dt_str in entities.datetimes:
                parsed = self._parse_relative_date(dt_str)

                # Only keep actual dates (YYYY-MM-DD format)
                # Filter out time expressions like "2pm", "morning", etc.
                if re.match(r'^\d{4}-\d{2}-\d{2}$', parsed):
                    parsed_datetimes.append(parsed)
                else:
                    self.logger.info(f"[ORCHESTRATOR] Filtering out non-date entity: '{parsed}'")

            entities.datetimes = parsed_datetimes

        return entities

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

            # Sanitize location address for better geocoding
            location = self._sanitize_address_for_here(location)

            result = weather_service.get_weather(location)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown weather method: {method}")

    def _execute_traffic_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute traffic service method."""
        from core.traffic_service import TrafficService
        import re

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

            # Enhance generic location names (e.g., "airport" → "Manchester Airport")
            origin = self._enhance_generic_location(origin, user_id)
            destination = self._enhance_generic_location(destination, user_id)

            # Sanitize addresses for HERE API (extract city + postcode)
            origin = self._sanitize_address_for_here(origin)
            destination = self._sanitize_address_for_here(destination)

            result = traffic_service.get_traffic_estimate(origin, destination)
            return {"method": method, "data": result}
        else:
            raise ValueError(f"Unknown traffic method: {method}")

    def _execute_calendar_service(self, method: str, params: Dict, user_id: int) -> Dict:
        """Execute calendar service method (M365)."""
        from actions.action_registry import ActionProviderRegistry
        from datetime import datetime, timedelta

        # Load M365 provider
        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(user_id)

        providers = registry.get_providers_by_capability("read_calendar", user_id)
        if not providers:
            raise ValueError("No calendar provider configured")

        provider_id, provider = providers[0]  # Use first available provider

        if method == "get_upcoming_events":
            days_ahead = params.get("days_ahead", 7)
            start_date = datetime.now()
            end_date = start_date + timedelta(days=days_ahead)
            result = provider.read_calendar(start_date=start_date, end_date=end_date)
            return {"method": method, "data": {"events": result}}
        elif method == "check_availability":
            date = params.get("date")
            if not date:
                raise ValueError("Missing required parameter: date")
            # Parse date string (format: YYYY-MM-DD)
            target_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = target_date.replace(hour=0, minute=0, second=0)
            end_date = target_date.replace(hour=23, minute=59, second=59)

            result = provider.read_calendar(start_date=start_date, end_date=end_date)
            return {"method": method, "data": {"date": date, "events": result}}
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

    def _enhance_generic_location(self, location: str, user_id: int) -> str:
        """
        Enhance generic location names with specific details based on user context.

        Examples:
            "airport" → "Manchester Airport" (if user is in Manchester/Salford area)
            "station" → "Manchester Piccadilly" (if user is in Manchester)

        Args:
            location: Generic location name
            user_id: User ID for context

        Returns:
            Enhanced location name or original if no enhancement needed
        """
        if not location:
            return location

        location_lower = location.lower().strip()

        # Check if location is generic "airport"
        if location_lower == "airport":
            # Try to infer which airport based on user's home/work location
            home_loc = self._get_user_fact(user_id, "home location")
            work_loc = self._get_user_fact(user_id, "work location")

            # Check if user is in Manchester/Salford area
            for user_location in [home_loc, work_loc]:
                if user_location:
                    user_loc_lower = user_location.lower()
                    if any(city in user_loc_lower for city in ["manchester", "salford", "wirral", "stockport"]):
                        enhanced = "Manchester Airport"
                        self.logger.info(f"[ORCHESTRATOR] Enhanced '{location}' → '{enhanced}' based on user location")
                        return enhanced

        # No enhancement needed
        return location

    def _sanitize_address_for_here(self, address: str) -> str:
        """
        Sanitize address for HERE API by extracting city + postcode.

        Per wiki: HERE API performs better with simplified addresses containing
        the last two components (typically city + postcode).

        Examples:
            "Soapworks, Colgate Ln, Salford M5 3LZ" → "Salford M5 3LZ"
            "8 Harefields Way, Wirral. CH494SB" → "Wirral CH494SB"

        Args:
            address: Full address string

        Returns:
            Sanitized address (city + postcode) or original if already simple
        """
        import re

        if not address:
            return address

        # If it's already coordinates (lat,lon), don't modify
        if re.match(r'^-?\d+\.?\d*,-?\d+\.?\d*$', address.strip()):
            return address

        # UK postcode pattern
        uk_postcode_pattern = r'[A-Z]{1,2}\d{1,2}\s?\d?[A-Z]{2}'

        # Check if address contains UK postcode
        postcode_match = re.search(uk_postcode_pattern, address, re.IGNORECASE)

        if postcode_match:
            # Split address by common delimiters
            parts = re.split(r'[,.]', address)
            # Clean up parts (strip whitespace)
            parts = [p.strip() for p in parts if p.strip()]

            # Take last 2 components (city + postcode)
            if len(parts) >= 2:
                sanitized = ", ".join(parts[-2:])
                self.logger.info(f"[ORCHESTRATOR] Sanitized address: '{address}' → '{sanitized}'")
                return sanitized

        # No postcode found or already simple - return as-is
        return address

    def _synthesize_response(
        self,
        user_query: str,
        user_id: int,
        gathered_data: Dict[str, Any],
        service_plan: Dict,
        conversation_history: Optional[List[Dict[str, str]]],
        processed_entities=None
    ) -> Dict[str, Any]:
        """
        Synthesize a natural conversational response from gathered service data.

        Uses LLM to transform raw service data into a helpful, contextual response.

        Args:
            user_query: Original user query
            user_id: User ID
            gathered_data: Data gathered from services (dict mapping service name to results)
            service_plan: Original service plan with reasoning
            conversation_history: Recent conversation turns
            processed_entities: Pre-processed entities with correct dates

        Returns:
            dict with:
                - response: Natural language response text
                - needs_confirmation: Whether user confirmation is needed for actions
                - proposed_actions: List of proposed actions (if any)
        """
        from core.router import route_request

        self.logger.info("[ORCHESTRATOR] Synthesizing response from gathered data...")

        # Format gathered data for LLM prompt
        data_summary = self._format_gathered_data(gathered_data)

        # Fix dates in service plan reasoning to avoid confusing the synthesis LLM
        corrected_reasoning = self._fix_dates_in_text(
            service_plan.get('reasoning', 'N/A'),
            processed_entities
        )

        # Build synthesis prompt
        prompt = f"""You are synthesizing a response based on data gathered from multiple services.

User's original query: "{user_query}"

Service planning reasoning:
{corrected_reasoning}

Gathered data:
{data_summary}

Your task:
1. Analyze the gathered data in context of the user's query
2. Provide a helpful, conversational response that directly addresses their request
3. **CRITICAL**: If traffic/routing data is provided with a destination, look for address details in the gathered data and mention the specific location found (city/town at minimum)
   - Example: "Asda in Salford" or "Asda Trafford Park" (not just "Asda")
   - This helps user verify the correct location was geocoded
4. If the data suggests creating a task or event, propose specific actionable steps
5. If you recommend an action, set needs_confirmation=true and include proposed_actions

CRITICAL RULES FOR ACTION PROPOSALS:
- ONLY propose actions that the user explicitly or implicitly requested
- DO NOT propose actions for informational queries (e.g., "What's the weather?" should NOT create a calendar event)
- **Shopping/errands with location and time** → MUST propose "create_calendar_event" (NOT "create_task")
  Example: "buy groceries from Asda tomorrow" → create_calendar_event with time slot
- **Tasks/reminders WITHOUT specific time** → propose "create_task"
  Example: "remind me to call John" → create_task
- Appointments with explicit times → propose "create_calendar_event"
- Each action MUST include a human-readable "confirmation_message" for user approval
- Use the exact date format from entities (YYYY-MM-DD) - DO NOT recalculate dates

Response format (JSON):
{{
    "response": "Your natural language response here",
    "needs_confirmation": false,
    "proposed_actions": []
}}

ACTION TYPES AND SCHEMAS:

1. Calendar Event:
{{
    "type": "create_calendar_event",
    "service": "calendar",
    "params": {{
        "subject": "Event title",
        "start_time": "YYYY-MM-DDTHH:MM:SS",  // ISO 8601 format
        "end_time": "YYYY-MM-DDTHH:MM:SS",    // ISO 8601 format
        "location": "Location (optional)",
        "description": "Description (optional)"
    }},
    "confirmation_message": "Create calendar event 'Event title' on [date] at [time]?",
    "reasoning": "Why this action makes sense"
}}

2. Task:
{{
    "type": "create_task",
    "service": "tasks",
    "params": {{
        "title": "Task title",
        "due_date": "YYYY-MM-DD",
        "notes": "Task details (optional)",
        "importance": "normal"  // normal, high, low
    }},
    "confirmation_message": "Create task '[title]' due on [date]?",
    "reasoning": "Why this action makes sense"
}}

EXAMPLES:

Example 1 - Shopping List:
User: "I need to buy milk, eggs, and bread from Asda tomorrow"
Gathered data: Calendar shows 2-3pm free tomorrow
Response:
{{
    "response": "I've checked your calendar and you're free tomorrow between 2-3pm. I can create a calendar event for your Asda shopping trip.",
    "needs_confirmation": true,
    "proposed_actions": [
        {{
            "type": "create_calendar_event",
            "service": "calendar",
            "params": {{
                "subject": "Shopping at Asda",
                "start_time": "2026-01-14T14:00:00",
                "end_time": "2026-01-14T15:00:00",
                "description": "Buy: milk, eggs, bread"
            }},
            "confirmation_message": "Create calendar event 'Shopping at Asda' tomorrow at 2:00 PM for 1 hour?",
            "reasoning": "User requested shopping trip, calendar shows availability"
        }}
    ]
}}

Example 2 - Appointment Booking:
User: "Book a haircut at Cuts Barber on Friday at 2pm"
Response:
{{
    "response": "I can add this haircut appointment to your calendar for Friday at 2pm.",
    "needs_confirmation": true,
    "proposed_actions": [
        {{
            "type": "create_calendar_event",
            "service": "calendar",
            "params": {{
                "subject": "Haircut",
                "start_time": "2026-01-17T14:00:00",
                "end_time": "2026-01-17T14:30:00",
                "location": "Cuts Barber"
            }},
            "confirmation_message": "Create calendar event 'Haircut' at Cuts Barber on Friday at 2:00 PM?",
            "reasoning": "User explicitly requested appointment booking"
        }}
    ]
}}

Example 3 - Informational Query (NO ACTION):
User: "What's the weather tomorrow?"
Gathered data: Weather shows 15°C, partly cloudy
Response:
{{
    "response": "Tomorrow's weather will be partly cloudy with a high of 15°C.",
    "needs_confirmation": false,
    "proposed_actions": []
}}
Note: NO action proposed - user only wants information.

Provide ONLY the JSON response, no other text."""

        # Call LLM via router (force orchestration synthesis intent)
        context = {
            "text": prompt,
            "user_id": user_id,
            "force_intent": "system_orchestration_synthesis",
            "mode": "personal",
            "memory": self.memory,
            "_skip_orchestration": True  # Prevent recursive orchestration
        }

        self.logger.info("[ORCHESTRATOR] About to call route_request for synthesis")
        response = route_request(context=context, stream=False)
        self.logger.info(f"[ORCHESTRATOR] route_request returned type={type(response)}")

        # Extract response text and provider info
        response_text = response.get("text", "").strip()
        synthesis_provider = response.get("provider")
        synthesis_model = response.get("model")
        self.logger.info(f"[ORCHESTRATOR] Synthesis response length: {len(response_text)}")
        self.logger.info(f"[ORCHESTRATOR] Synthesis provider: {synthesis_provider}, model: {synthesis_model}")

        # Parse JSON response
        try:
            # Try to extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            synthesis_result = json.loads(response_text)
            self.logger.info(f"[ORCHESTRATOR] Successfully synthesized response")

            # Post-process proposed actions to fix dates
            synthesis_result = self._fix_proposed_action_dates(synthesis_result, processed_entities)

            # Add synthesis provider info for attribution
            synthesis_result["synthesis_provider"] = synthesis_provider
            synthesis_result["synthesis_model"] = synthesis_model

            return synthesis_result
        except json.JSONDecodeError as e:
            self.logger.error(f"[ORCHESTRATOR] Failed to parse synthesis JSON: {e}")
            self.logger.error(f"[ORCHESTRATOR] Raw response: {response_text[:500]}")

            # Fall back to using the response as-is
            return {
                "response": response_text if response_text else "I gathered the requested data but couldn't format a response.",
                "needs_confirmation": False,
                "proposed_actions": []
            }

    def _format_gathered_data(self, gathered_data: Dict[str, Any]) -> str:
        """Format gathered service data for LLM prompt."""
        if not gathered_data:
            return "No data gathered"

        lines = []
        for service_name, service_result in gathered_data.items():
            if "error" in service_result:
                lines.append(f"\n{service_name.upper()} (ERROR):")
                lines.append(f"  Error: {service_result['error']}")
            else:
                lines.append(f"\n{service_name.upper()}:")
                method = service_result.get("method", "unknown")
                data = service_result.get("data", {})
                lines.append(f"  Method: {method}")
                lines.append(f"  Data: {json.dumps(data, indent=2)}")

        return "\n".join(lines)
