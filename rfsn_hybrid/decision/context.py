"""
Decision context builder.

Builds compact, stable context keys from NPC state for decision making.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DecisionContext:
    """
    Compact representation of context for decision making.
    
    Attributes:
        affinity_bucket: Affinity level bucketed (-2 to 2)
        mood: Current mood string
        recent_player_events: Last 1-2 player event types
        recent_env_events: Last 1-2 environment event types (if any)
    """
    affinity_bucket: int  # -2, -1, 0, 1, 2
    mood: str
    recent_player_events: List[str]
    recent_env_events: List[str]
    
    def to_key(self) -> str:
        """
        Convert context to a stable string key.
        
        Returns:
            String key for use in weight lookups
        """
        # Format: "aff:{bucket}|mood:{mood}|pevents:{...}|eevents:{...}"
        parts = [
            f"aff:{self.affinity_bucket}",
            f"mood:{self.mood.lower()}",
        ]
        
        if self.recent_player_events:
            pevents = ",".join(sorted(self.recent_player_events[:2]))
            parts.append(f"pevents:{pevents}")
        
        if self.recent_env_events:
            eevents = ",".join(sorted(self.recent_env_events[:2]))
            parts.append(f"eevents:{eevents}")
        
        return "|".join(parts)


def affinity_to_bucket(affinity: float) -> int:
    """
    Bucket affinity into discrete levels.
    
    Args:
        affinity: Affinity value (-1.0 to 1.0)
        
    Returns:
        Bucket number (-2 to 2)
    """
    if affinity >= 0.6:
        return 2  # Very positive
    elif affinity >= 0.2:
        return 1  # Positive
    elif affinity >= -0.2:
        return 0  # Neutral
    elif affinity >= -0.6:
        return -1  # Negative
    else:
        return -2  # Very negative


def build_context_key(
    affinity: float,
    mood: str,
    recent_player_events: Optional[List[str]] = None,
    recent_env_events: Optional[List[str]] = None,
) -> str:
    """
    Build a compact context key for decision making.
    
    This is the primary interface for creating context keys.
    
    Args:
        affinity: Current affinity (-1.0 to 1.0)
        mood: Current mood string
        recent_player_events: Last 1-2 player event types
        recent_env_events: Last 1-2 environment event types
        
    Returns:
        String key suitable for weight lookup
        
    Examples:
        >>> build_context_key(0.8, "Pleased", ["GIFT"], ["QUEST_COMPLETED"])
        'aff:2|mood:pleased|pevents:GIFT|eevents:QUEST_COMPLETED'
        
        >>> build_context_key(-0.7, "Hostile", ["PUNCH"])
        'aff:-2|mood:hostile|pevents:PUNCH'
    """
    context = DecisionContext(
        affinity_bucket=affinity_to_bucket(affinity),
        mood=mood,
        recent_player_events=recent_player_events or [],
        recent_env_events=recent_env_events or [],
    )
    return context.to_key()


def extract_recent_events(
    event_history: List[dict],
    event_type_key: str = "event_type",
    limit: int = 2,
) -> List[str]:
    """
    Extract recent event types from event history.
    
    Args:
        event_history: List of event dictionaries
        event_type_key: Key to extract from each event dict
        limit: Maximum number of recent events to extract
        
    Returns:
        List of recent event type strings
    """
    if not event_history:
        return []
    
    # Get most recent events
    recent = event_history[-limit:]
    
    # Extract event types
    types = []
    for event in recent:
        if isinstance(event, dict) and event_type_key in event:
            types.append(event[event_type_key])
    
    return types
