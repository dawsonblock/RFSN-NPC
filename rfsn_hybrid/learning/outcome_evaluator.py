"""
Outcome evaluator for NPC learning system.

Evaluates the outcomes of NPC actions to generate reward signals.
Rewards guide the learning system to reweight action preferences.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class OutcomeType(str, Enum):
    """Types of outcomes that can be evaluated."""
    DIALOGUE_SUCCESS = "dialogue_success"
    DIALOGUE_FAILURE = "dialogue_failure"
    QUEST_COMPLETE = "quest_complete"
    QUEST_FAILED = "quest_failed"
    RELATIONSHIP_IMPROVED = "relationship_improved"
    RELATIONSHIP_DAMAGED = "relationship_damaged"
    PLAYER_POSITIVE_REACTION = "player_positive_reaction"
    PLAYER_NEGATIVE_REACTION = "player_negative_reaction"
    COMBAT_VICTORY = "combat_victory"
    COMBAT_DEFEAT = "combat_defeat"


@dataclass
class Outcome:
    """
    Represents an outcome of an NPC action.
    
    Attributes:
        outcome_type: Type of outcome
        reward: Reward signal (-1.0 to 1.0)
        context: Context in which action was taken
        action: Action that was taken
        details: Additional outcome details
    """
    outcome_type: OutcomeType
    reward: float
    context: str
    action: str
    details: Optional[Dict] = None
    
    def __post_init__(self):
        """Clamp reward to valid range."""
        self.reward = max(-1.0, min(1.0, self.reward))


class OutcomeEvaluator:
    """
    Evaluates outcomes and generates reward signals.
    
    This is the bridge between game events and the learning system.
    Translates high-level outcomes into numeric rewards.
    """
    
    # Default reward values for different outcome types
    DEFAULT_REWARDS: Dict[OutcomeType, float] = {
        OutcomeType.DIALOGUE_SUCCESS: 0.5,
        OutcomeType.DIALOGUE_FAILURE: -0.3,
        OutcomeType.QUEST_COMPLETE: 0.8,
        OutcomeType.QUEST_FAILED: -0.6,
        OutcomeType.RELATIONSHIP_IMPROVED: 0.6,
        OutcomeType.RELATIONSHIP_DAMAGED: -0.5,
        OutcomeType.PLAYER_POSITIVE_REACTION: 0.4,
        OutcomeType.PLAYER_NEGATIVE_REACTION: -0.4,
        OutcomeType.COMBAT_VICTORY: 0.7,
        OutcomeType.COMBAT_DEFEAT: -0.7,
    }
    
    def __init__(self, custom_rewards: Optional[Dict[OutcomeType, float]] = None):
        """
        Initialize evaluator.
        
        Args:
            custom_rewards: Optional custom reward values to override defaults
        """
        self.rewards = self.DEFAULT_REWARDS.copy()
        if custom_rewards:
            self.rewards.update(custom_rewards)
    
    def evaluate(
        self,
        outcome_type: OutcomeType,
        context: str,
        action: str,
        intensity: float = 1.0,
        details: Optional[Dict] = None,
    ) -> Outcome:
        """
        Evaluate an outcome and generate reward signal.
        
        Args:
            outcome_type: Type of outcome
            context: Context key for the action
            action: Action identifier
            intensity: Multiplier for reward (0.0 to 2.0)
            details: Additional outcome information
            
        Returns:
            Outcome object with reward signal
        """
        base_reward = self.rewards.get(outcome_type, 0.0)
        
        # Apply intensity multiplier (clamped)
        intensity = max(0.0, min(2.0, intensity))
        reward = base_reward * intensity
        
        return Outcome(
            outcome_type=outcome_type,
            reward=reward,
            context=context,
            action=action,
            details=details,
        )
    
    def evaluate_from_affinity_change(
        self,
        affinity_delta: float,
        context: str,
        action: str,
    ) -> Outcome:
        """
        Evaluate outcome based on affinity change.
        
        Positive affinity change -> positive reward
        Negative affinity change -> negative reward
        
        Args:
            affinity_delta: Change in affinity (-1.0 to 1.0)
            context: Context key
            action: Action identifier
            
        Returns:
            Outcome with reward proportional to affinity change
        """
        # Map affinity change to outcome type
        if affinity_delta > 0.1:
            outcome_type = OutcomeType.RELATIONSHIP_IMPROVED
        elif affinity_delta < -0.1:
            outcome_type = OutcomeType.RELATIONSHIP_DAMAGED
        else:
            # Neutral - minimal signal
            return Outcome(
                outcome_type=OutcomeType.DIALOGUE_SUCCESS,
                reward=0.0,
                context=context,
                action=action,
            )
        
        # Reward proportional to magnitude of change
        intensity = abs(affinity_delta) * 5.0  # Scale to 0-1 range
        return self.evaluate(outcome_type, context, action, intensity)
    
    def evaluate_from_player_event(
        self,
        player_event_type: str,
        context: str,
        action: str,
    ) -> Outcome:
        """
        Evaluate outcome based on player event type.
        
        Args:
            player_event_type: Player event (GIFT, PUNCH, etc.)
            context: Context key
            action: Action identifier
            
        Returns:
            Outcome with appropriate reward
        """
        # Map player events to outcome types
        positive_events = ["GIFT", "PRAISE", "HELP", "QUEST_COMPLETE"]
        negative_events = ["PUNCH", "INSULT", "THREATEN", "THEFT"]
        
        if player_event_type in positive_events:
            outcome_type = OutcomeType.PLAYER_POSITIVE_REACTION
        elif player_event_type in negative_events:
            outcome_type = OutcomeType.PLAYER_NEGATIVE_REACTION
        else:
            # Neutral event (TALK)
            return Outcome(
                outcome_type=OutcomeType.DIALOGUE_SUCCESS,
                reward=0.0,
                context=context,
                action=action,
            )
        
        return self.evaluate(outcome_type, context, action)
    
    def set_reward(self, outcome_type: OutcomeType, reward: float) -> None:
        """
        Override default reward for an outcome type.
        
        Args:
            outcome_type: Type to override
            reward: New reward value (-1.0 to 1.0)
        """
        self.rewards[outcome_type] = max(-1.0, min(1.0, reward))
