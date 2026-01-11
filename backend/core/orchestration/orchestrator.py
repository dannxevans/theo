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

    async def orchestrate(
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
        4. Synthesize response (LLM call #2)
        5. Create confirmations for actions
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

        # TODO: Implement Steps 2-6 in next phase
        # For now, return placeholder
        return OrchestrationResult(
            should_orchestrate=True,
            text="Orchestration triggered but not yet implemented",
            metadata={"phase": "1_placeholder"}
        )

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
