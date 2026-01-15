"""
Decision layer for NPC action selection.

This module provides bounded action selection capabilities that work
alongside the existing learning module. It does NOT create new behaviors,
but selects from a finite, pre-defined action set based on context.
"""

from .policy import DecisionPolicy, NPCAction
from .context import DecisionContext, build_context_key
from .outcome import OutcomeProcessor, evaluate_outcome

__all__ = [
    "DecisionPolicy",
    "NPCAction",
    "DecisionContext",
    "build_context_key",
    "OutcomeProcessor",
    "evaluate_outcome",
]
