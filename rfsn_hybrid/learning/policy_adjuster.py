"""
Policy adjuster for NPC behavior learning.

Adjusts action selection weights based on learned outcomes.
Does NOT create new behaviors - only reweights existing reducer decisions.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from .learning_state import LearningState, ActionWeight
from .outcome_evaluator import Outcome, OutcomeEvaluator


class PolicyAdjuster:
    """
    Adjusts policy weights based on learning outcomes.
    
    Uses epsilon-greedy exploration strategy:
    - Most of the time: use learned weights
    - Sometimes: explore with uniform weights (to discover better options)
    
    Key principle: This ONLY reweights existing actions.
    It cannot create new behaviors or actions.
    """
    
    def __init__(
        self,
        learning_state: LearningState,
        outcome_evaluator: OutcomeEvaluator,
        exploration_rate: float = 0.1,
        learning_rate: float = 0.05,
    ):
        """
        Initialize policy adjuster.
        
        Args:
            learning_state: Learning state storage
            outcome_evaluator: Evaluates outcomes to generate rewards
            exploration_rate: Probability of exploring (0.0 to 1.0)
            learning_rate: How quickly to update weights (0.0 to 1.0)
        """
        self.learning_state = learning_state
        self.outcome_evaluator = outcome_evaluator
        self.exploration_rate = max(0.0, min(1.0, exploration_rate))
        self.learning_rate = max(0.0, min(1.0, learning_rate))
    
    def get_action_weight(self, context_key: str, action: str) -> float:
        """
        Get weight for an action in a context.
        
        Args:
            context_key: Context identifier
            action: Action identifier
            
        Returns:
            Weight multiplier (0.5 to 2.0)
        """
        if not self.learning_state.enabled:
            return 1.0
        
        # Epsilon-greedy: sometimes return neutral weight for exploration
        if random.random() < self.exploration_rate:
            return 1.0
        
        return self.learning_state.get_weight(context_key, action)
    
    def get_action_weights(
        self,
        context_key: str,
        actions: List[str],
    ) -> Dict[str, float]:
        """
        Get weights for multiple actions.
        
        Args:
            context_key: Context identifier
            actions: List of action identifiers
            
        Returns:
            Dictionary of action -> weight
        """
        return {
            action: self.get_action_weight(context_key, action)
            for action in actions
        }
    
    def record_outcome(
        self,
        context_key: str,
        action: str,
        outcome: Outcome,
    ) -> float:
        """
        Record an outcome and update weights.
        
        Args:
            context_key: Context in which action was taken
            action: Action that was taken
            outcome: Outcome to learn from
            
        Returns:
            New weight for this (context, action) pair
        """
        if not self.learning_state.enabled:
            return 1.0
        
        return self.learning_state.update_weight(
            context_key=context_key,
            action=action,
            reward=outcome.reward,
            learning_rate=self.learning_rate,
        )
    
    def apply_affinity_feedback(
        self,
        context_key: str,
        action: str,
        affinity_delta: float,
    ) -> float:
        """
        Update weights based on affinity change.
        
        Convenience method that evaluates affinity change as outcome
        and records it for learning.
        
        Args:
            context_key: Context key
            action: Action identifier
            affinity_delta: Change in affinity
            
        Returns:
            New weight
        """
        outcome = self.outcome_evaluator.evaluate_from_affinity_change(
            affinity_delta=affinity_delta,
            context=context_key,
            action=action,
        )
        return self.record_outcome(context_key, action, outcome)
    
    def apply_player_event_feedback(
        self,
        context_key: str,
        action: str,
        player_event_type: str,
    ) -> float:
        """
        Update weights based on player event.
        
        Args:
            context_key: Context key
            action: Action identifier
            player_event_type: Player event type (GIFT, PUNCH, etc.)
            
        Returns:
            New weight
        """
        outcome = self.outcome_evaluator.evaluate_from_player_event(
            player_event_type=player_event_type,
            context=context_key,
            action=action,
        )
        return self.record_outcome(context_key, action, outcome)
    
    def build_context_key(
        self,
        affinity: float,
        mood: str,
        recent_events: Optional[List[str]] = None,
    ) -> str:
        """
        Build a context key from state variables.
        
        Context keys are used to group similar situations for learning.
        
        Args:
            affinity: Current affinity (-1.0 to 1.0)
            mood: Current mood
            recent_events: Optional recent event types
            
        Returns:
            Context key string
        """
        # Discretize affinity into buckets
        if affinity >= 0.6:
            aff_bucket = "high"
        elif affinity >= 0.2:
            aff_bucket = "mid"
        elif affinity >= -0.2:
            aff_bucket = "neutral"
        elif affinity >= -0.6:
            aff_bucket = "low"
        else:
            aff_bucket = "hostile"
        
        # Build key
        parts = [f"aff:{aff_bucket}", f"mood:{mood.lower()}"]
        
        # Optionally include recent event context
        if recent_events:
            event_str = "_".join(recent_events[-2:])  # Last 2 events
            parts.append(f"events:{event_str}")
        
        return "|".join(parts)
    
    def get_statistics(self) -> Dict:
        """
        Get learning statistics.
        
        Returns:
            Dictionary with learning stats
        """
        weights = self.learning_state.get_all_weights()
        
        if not weights:
            return {
                "enabled": self.learning_state.enabled,
                "total_entries": 0,
                "avg_weight": 1.0,
                "avg_success_rate": 0.5,
            }
        
        total_weight = sum(w.weight for w in weights)
        total_success_rate = sum(w.success_rate for w in weights)
        
        return {
            "enabled": self.learning_state.enabled,
            "total_entries": len(weights),
            "avg_weight": total_weight / len(weights),
            "avg_success_rate": total_success_rate / len(weights),
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
        }
