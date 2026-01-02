"""
Routines module for THEO.

Routines allow bundling of multiple related requests into a single interaction
that returns a consolidated response.
"""

from .detector import detect_routine
from .executor import execute_routine
from .consolidator import consolidate_results

__all__ = ["detect_routine", "execute_routine", "consolidate_results"]
