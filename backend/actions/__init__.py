"""
Actions package for THEO Personal AI Agent.

This package contains action providers that execute external actions
(calendar events, emails, bookings) as opposed to LLM providers that
generate text responses.
"""

from actions.base import ActionProvider

__all__ = ['ActionProvider']
