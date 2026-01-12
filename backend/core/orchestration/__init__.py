"""
Orchestration system for multi-service coordination.

This module provides intelligent coordination across multiple services
(calendar, weather, traffic, etc.) using LLM-first architecture.
"""

from .orchestrator import Orchestrator
from .service_registry import SERVICE_REGISTRY, get_service_capabilities_prompt

__all__ = [
    'Orchestrator',
    'SERVICE_REGISTRY',
    'get_service_capabilities_prompt'
]
