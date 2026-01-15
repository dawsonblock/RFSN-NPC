"""
Common event schema for game environment feedback.

Defines a unified JSON event format that both Skyrim and Unity
can use to communicate with the RFSN system.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import json


class EnvironmentEventType(str, Enum):
    """Standard event types supported by RFSN."""
    
    # Dialogue events
    DIALOGUE_STARTED = "dialogue_started"
    DIALOGUE_ENDED = "dialogue_ended"
    DIALOGUE_CHOICE = "dialogue_choice"
    
    # Player sentiment/emotion
    PLAYER_SENTIMENT = "player_sentiment"
    PLAYER_HOSTILITY = "player_hostility"
    
    # Combat events
    COMBAT_STARTED = "combat_started"
    COMBAT_ENDED = "combat_ended"
    COMBAT_RESULT = "combat_result"
    COMBAT_DAMAGE_TAKEN = "combat_damage_taken"
    COMBAT_DAMAGE_DEALT = "combat_damage_dealt"
    
    # Quest events
    QUEST_STARTED = "quest_started"
    QUEST_UPDATED = "quest_updated"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    
    # Proximity/social
    PROXIMITY_ENTERED = "proximity_entered"
    PROXIMITY_EXITED = "proximity_exited"
    PROXIMITY_UPDATE = "proximity_update"
    
    # Social actions
    GIFT_GIVEN = "gift"
    THEFT_DETECTED = "theft"
    ASSIST_PROVIDED = "assist"
    CRIME_WITNESSED = "crime_witnessed"
    
    # Time/environment
    TIME_PASSED = "time_passed"
    LOCATION_CHANGED = "location_changed"
    
    # Generic fallback
    CUSTOM = "custom"


@dataclass
class EnvironmentEvent:
    """
    Unified event format for game environment feedback.
    
    This schema is designed to be serializable to JSON and
    easily constructed from both Skyrim (Papyrus) and Unity (C#).
    
    Attributes:
        event_type: Type of event (from EnvironmentEventType enum)
        ts: Timestamp (ISO 8601 format or Unix timestamp)
        npc_id: Identifier for the NPC experiencing the event
        player_id: Identifier for the player (if relevant)
        session_id: Session identifier for grouping related events
        payload: Event-specific data
        version: Schema version for compatibility
    """
    event_type: str
    npc_id: str
    ts: float = field(default_factory=lambda: datetime.now().timestamp())
    player_id: Optional[str] = None
    session_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EnvironmentEvent":
        """Create from dictionary (e.g., from JSON)."""
        return cls(
            event_type=data["event_type"],
            npc_id=data["npc_id"],
            ts=data.get("ts", datetime.now().timestamp()),
            player_id=data.get("player_id"),
            session_id=data.get("session_id"),
            payload=data.get("payload", {}),
            version=data.get("version", 1),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "EnvironmentEvent":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate event structure and content.
        
        Returns:
            (is_valid, error_message)
        """
        # Check required fields
        if not self.event_type:
            return False, "event_type is required"
        
        if not self.npc_id:
            return False, "npc_id is required"
        
        # Validate event type
        try:
            EnvironmentEventType(self.event_type)
        except ValueError:
            if self.event_type != "custom":
                return False, f"Invalid event_type: {self.event_type}"
        
        # Validate timestamp
        if self.ts is None:
            return False, "timestamp is required"
        
        if self.ts < 0:
            return False, "Invalid timestamp"
        
        # Validate payload
        if not isinstance(self.payload, dict):
            return False, "payload must be a dictionary"
        
        return True, None


# Event builder helpers for common event types

def dialogue_started_event(
    npc_id: str,
    player_id: str,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a DIALOGUE_STARTED event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.DIALOGUE_STARTED.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
    )


def dialogue_choice_event(
    npc_id: str,
    player_id: str,
    choice_id: str,
    choice_text: Optional[str] = None,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a DIALOGUE_CHOICE event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.DIALOGUE_CHOICE.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "choice_id": choice_id,
            "choice_text": choice_text,
        },
    )


def player_sentiment_event(
    npc_id: str,
    player_id: str,
    sentiment: float,  # -1.0 to 1.0
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a PLAYER_SENTIMENT event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.PLAYER_SENTIMENT.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "sentiment": max(-1.0, min(1.0, sentiment)),
        },
    )


def player_hostility_event(
    npc_id: str,
    player_id: str,
    hostility: float,  # 0.0 to 1.0
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a PLAYER_HOSTILITY event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.PLAYER_HOSTILITY.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "hostility": max(0.0, min(1.0, hostility)),
        },
    )


def combat_result_event(
    npc_id: str,
    player_id: str,
    result: str,  # "win", "loss", "flee"
    damage_dealt: float = 0.0,
    damage_taken: float = 0.0,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a COMBAT_RESULT event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.COMBAT_RESULT.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "result": result,
            "damage_dealt": damage_dealt,
            "damage_taken": damage_taken,
        },
    )


def quest_update_event(
    npc_id: str,
    quest_id: str,
    status: str,  # "started", "updated", "completed", "failed"
    progress: float = 0.0,  # 0.0 to 1.0
    player_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a QUEST_UPDATE event."""
    event_type_map = {
        "started": EnvironmentEventType.QUEST_STARTED,
        "updated": EnvironmentEventType.QUEST_UPDATED,
        "completed": EnvironmentEventType.QUEST_COMPLETED,
        "failed": EnvironmentEventType.QUEST_FAILED,
    }
    
    return EnvironmentEvent(
        event_type=event_type_map.get(status, EnvironmentEventType.QUEST_UPDATED).value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "quest_id": quest_id,
            "status": status,
            "progress": max(0.0, min(1.0, progress)),
        },
    )


def proximity_update_event(
    npc_id: str,
    player_id: str,
    distance: float,  # Distance in game units
    time_near: float = 0.0,  # Time player has been near (seconds)
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a PROXIMITY_UPDATE event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.PROXIMITY_UPDATE.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "distance": distance,
            "time_near": time_near,
        },
    )


def gift_event(
    npc_id: str,
    player_id: str,
    item_id: str,
    item_value: float = 0.0,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a GIFT event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.GIFT_GIVEN.value,
        npc_id=npc_id,
        player_id=player_id,
        session_id=session_id,
        payload={
            "item_id": item_id,
            "item_value": item_value,
        },
    )


def time_passed_event(
    npc_id: str,
    hours_passed: float,
    session_id: Optional[str] = None,
) -> EnvironmentEvent:
    """Create a TIME_PASSED event."""
    return EnvironmentEvent(
        event_type=EnvironmentEventType.TIME_PASSED.value,
        npc_id=npc_id,
        session_id=session_id,
        payload={
            "hours_passed": hours_passed,
        },
    )
