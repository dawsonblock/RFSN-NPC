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
- Uses contextual bandit approach (epsilon-greedy + LinUCB)
- Tracks outcomes per (context, action) pair
- Adjusts weights slowly over time
- Bounded state (fixed memory budget)
"""

from dataclasses import dataclass, field
from typing import Dict, Any

from .learning_state import LearningState, ActionWeight
from .outcome_evaluator import OutcomeEvaluator, Outcome, OutcomeType
from .policy_adjuster import PolicyAdjuster
from .learning_config import LearningConfig, LearningPresets, DEFAULT_LEARNING_CONFIG
from .feature_encoder import FeatureEncoder, FeatureVector, FEATURE_SCHEMA_VERSION
from .bandit import LinUCBBandit, BanditArm
from .persistence_hooks import LearningPersistence, restore_learning_components


@dataclass(frozen=True)
class PolicyBias:
    """
    Policy bias output from learning system.
    
    This is consumed by the reducer to adjust action selection.
    The reducer adds these biases to its own heuristic scores but
    never bypasses its safety checks or rule clamps.
    
    Attributes:
        action_bias: Dictionary mapping action_id -> additive bias value
        metadata: Explainability info (chosen arm, confidence, etc.)
    """
    action_bias: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def neutral(cls) -> "PolicyBias":
        """Create a neutral bias (no influence)."""
        return cls(action_bias={}, metadata={"type": "neutral"})
    
    def __bool__(self) -> bool:
        """Check if bias has any effect."""
        return bool(self.action_bias)


__all__ = [
    # Core learning components
    "LearningState",
    "ActionWeight",
    "OutcomeEvaluator",
    "Outcome",
    "OutcomeType",
    "PolicyAdjuster",
    
    # Configuration
    "LearningConfig",
    "LearningPresets",
    "DEFAULT_LEARNING_CONFIG",
    
    # Feature encoding
    "FeatureEncoder",
    "FeatureVector",
    "FEATURE_SCHEMA_VERSION",
    
    # Bandit learner
    "LinUCBBandit",
    "BanditArm",
    
    # Persistence
    "LearningPersistence",
    "restore_learning_components",
    
    # Policy output
    "PolicyBias",
]
