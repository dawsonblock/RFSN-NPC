"""
Outcome processor for decision learning.

Converts observable outcomes (affinity changes, player events, environment signals)
into reward signals for learning.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Outcome:
    """
    Outcome of an action.
    
    Attributes:
        affinity_delta: Change in affinity
        mood_changed: Whether mood changed
        player_event_type: Type of player response event (if any)
        env_signal: Environment signal name (if any)
        signal_magnitude: Magnitude of environment signal
    """
    affinity_delta: float = 0.0
    mood_changed: bool = False
    player_event_type: Optional[str] = None
    env_signal: Optional[str] = None
    signal_magnitude: float = 0.0


class OutcomeProcessor:
    """
    Processes outcomes to generate reward signals.
    
    Converts raw state changes into normalized reward values
    that can be used to update decision weights.
    """
    
    def __init__(self):
        """Initialize outcome processor."""
        # Map player event types to reward values
        self.player_event_rewards: Dict[str, float] = {
            "GIFT": 1.0,
            "PRAISE": 0.8,
            "HELP": 0.6,
            "TALK": 0.1,
            "QUEST_COMPLETE": 0.9,
            "INSULT": -0.8,
            "PUNCH": -1.0,
            "THREATEN": -0.9,
            "THEFT": -0.7,
        }
        
        # Map environment signals to reward values
        self.env_signal_rewards: Dict[str, float] = {
            "bonding": 0.7,
            "alienation": -0.7,
            "trust_gain": 0.6,
            "trust_loss": -0.6,
            "relief": 0.5,
            "stress": -0.5,
            "safety": 0.4,
            "threat": -0.6,
        }
    
    def evaluate(self, outcome: Outcome) -> float:
        """
        Evaluate outcome to produce a reward signal.
        
        Args:
            outcome: The outcome to evaluate
            
        Returns:
            Reward value (typically -1.0 to 1.0)
        """
        reward = 0.0
        
        # Primary signal: affinity change
        # Scale: -0.5 to 0.5 affinity delta -> -1.0 to 1.0 reward
        if outcome.affinity_delta != 0.0:
            reward += outcome.affinity_delta * 2.0
        
        # Secondary signal: player event type
        if outcome.player_event_type:
            event_reward = self.player_event_rewards.get(
                outcome.player_event_type,
                0.0
            )
            reward += event_reward * 0.5  # Weight player events at 50%
        
        # Tertiary signal: environment signal
        if outcome.env_signal:
            signal_reward = self.env_signal_rewards.get(
                outcome.env_signal,
                0.0
            )
            # Scale by magnitude
            reward += signal_reward * outcome.signal_magnitude * 0.3
        
        # Small bonus for mood change to positive states
        if outcome.mood_changed:
            reward += 0.1
        
        # Clamp to reasonable range
        reward = max(-2.0, min(2.0, reward))
        
        return reward


def evaluate_outcome(
    pre_affinity: float,
    post_affinity: float,
    player_event_type: Optional[str] = None,
    env_signal: Optional[str] = None,
    signal_magnitude: float = 0.0,
) -> float:
    """
    Convenience function to evaluate an outcome.
    
    Args:
        pre_affinity: Affinity before action
        post_affinity: Affinity after action
        player_event_type: Type of player event (if any)
        env_signal: Environment signal name (if any)
        signal_magnitude: Magnitude of environment signal
        
    Returns:
        Reward value (-2.0 to 2.0)
        
    Examples:
        >>> evaluate_outcome(0.5, 0.6, "GIFT")
        0.7  # Positive affinity change + gift reward
        
        >>> evaluate_outcome(0.2, -0.1, "INSULT")
        -1.0  # Negative affinity change + insult penalty
    """
    outcome = Outcome(
        affinity_delta=post_affinity - pre_affinity,
        player_event_type=player_event_type,
        env_signal=env_signal,
        signal_magnitude=signal_magnitude,
    )
    
    processor = OutcomeProcessor()
    return processor.evaluate(outcome)
