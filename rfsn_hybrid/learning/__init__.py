"""
Learning layer for RFSN NPC system.

This module provides minimal, controlled learning that reweights existing
reducer decisions without creating new behaviors.

Key principles:
- Learning does NOT create new behaviors
- Learning only reweights existing choices
- Learning is slow, incremental, and capped
- Learning is completely disable-able

Design:
- Uses contextual bandit approach (epsilon-greedy)
- Tracks outcomes per (context, action) pair
- Adjusts weights slowly over time
- Bounded state (fixed memory budget)
"""

from .learning_state import LearningState, ActionWeight
from .outcome_evaluator import OutcomeEvaluator, Outcome, OutcomeType
from .policy_adjuster import PolicyAdjuster

__all__ = [
    "LearningState",
    "ActionWeight",
    "OutcomeEvaluator",
    "Outcome",
    "OutcomeType",
    "PolicyAdjuster",
]
