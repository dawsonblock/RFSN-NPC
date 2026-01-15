"""
Event adapter for environment feedback.

Ingests raw game events and converts them to a standardized format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class GameEventType(str, Enum):
    """Types of game events the NPC can perceive."""
    
    # Combat events
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    COMBAT_HIT_TAKEN = "combat_hit_taken"
    COMBAT_HIT_DEALT = "combat_hit_dealt"
    COMBAT_ALLY_DIED = "combat_ally_died"
    COMBAT_ENEMY_DIED = "combat_enemy_died"
    
    # Dialogue events
    DIALOGUE_START = "dialogue_start"
    DIALOGUE_END = "dialogue_end"
    DIALOGUE_BRANCH_TAKEN = "dialogue_branch_taken"
    DIALOGUE_PERSUASION_SUCCESS = "dialogue_persuasion_success"
    DIALOGUE_PERSUASION_FAILURE = "dialogue_persuasion_failure"
    
    # Social events
    PLAYER_NEARBY = "player_nearby"
    PLAYER_LEFT = "player_left"
    WITNESSED_CRIME = "witnessed_crime"
    WITNESSED_GOOD_DEED = "witnessed_good_deed"
    REPUTATION_CHANGE = "reputation_change"
    
    # Quest events
    QUEST_STARTED = "quest_started"
    QUEST_OBJECTIVE_COMPLETE = "quest_objective_complete"
    QUEST_COMPLETED = "quest_completed"
    QUEST_FAILED = "quest_failed"
    
    # Environment events
    TIME_PASSED = "time_passed"
    LOCATION_CHANGED = "location_changed"
    WEATHER_CHANGED = "weather_changed"
    
    # Item events
    ITEM_RECEIVED = "item_received"
    ITEM_TAKEN = "item_taken"
    ITEM_STOLEN = "item_stolen"
    
    # Status events
    HEALTH_CHANGED = "health_changed"
    SPELL_CAST_ON_NPC = "spell_cast_on_npc"
    BUFF_APPLIED = "buff_applied"
    DEBUFF_APPLIED = "debuff_applied"


@dataclass
class GameEvent:
    """
    Standardized game event.
    
    Attributes:
        event_type: Type of event
        timestamp: When event occurred
        npc_id: ID of affected NPC
        player_id: ID of player (if relevant)
        magnitude: Intensity of event (0.0 to 1.0)
        data: Additional event-specific data
        tags: Event classification tags
    """
    event_type: GameEventType
    npc_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    player_id: Optional[str] = None
    magnitude: float = 0.5
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Ensure magnitude is bounded."""
        self.magnitude = max(0.0, min(1.0, self.magnitude))
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_type": self.event_type.value,
            "npc_id": self.npc_id,
            "timestamp": self.timestamp,
            "player_id": self.player_id,
            "magnitude": self.magnitude,
            "data": self.data,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GameEvent:
        """Deserialize from dictionary."""
        return cls(
            event_type=GameEventType(data["event_type"]),
            npc_id=data["npc_id"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            player_id=data.get("player_id"),
            magnitude=data.get("magnitude", 0.5),
            data=data.get("data", {}),
            tags=data.get("tags", []),
        )


class EventAdapter:
    """
    Adapts raw game events to standardized GameEvent format.
    
    This is the entry point for environmental feedback.
    Game engines feed raw events here, which are normalized
    and validated before being passed to the consequence mapper.
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize event adapter.
        
        Args:
            enabled: Whether to process events
        """
        self.enabled = enabled
        self.event_count = 0
        self.events_by_type: Dict[GameEventType, int] = {}
    
    def adapt(
        self,
        event_type: GameEventType,
        npc_id: str,
        player_id: Optional[str] = None,
        magnitude: float = 0.5,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[GameEvent]:
        """
        Adapt a raw event to GameEvent format.
        
        Args:
            event_type: Type of event
            npc_id: NPC affected
            player_id: Player involved (if any)
            magnitude: Event intensity
            data: Additional data
            tags: Event tags
            
        Returns:
            GameEvent if enabled, None otherwise
        """
        if not self.enabled:
            return None
        
        event = GameEvent(
            event_type=event_type,
            npc_id=npc_id,
            player_id=player_id,
            magnitude=magnitude,
            data=data or {},
            tags=tags or [],
        )
        
        # Track statistics
        self.event_count += 1
        self.events_by_type[event_type] = self.events_by_type.get(event_type, 0) + 1
        
        return event
    
    def adapt_combat_event(
        self,
        npc_id: str,
        event_subtype: str,
        damage: float = 0.0,
        attacker: Optional[str] = None,
        target: Optional[str] = None,
    ) -> Optional[GameEvent]:
        """
        Convenience method for combat events.
        
        Args:
            npc_id: NPC experiencing the event
            event_subtype: "start", "end", "hit_taken", "hit_dealt", etc.
            damage: Damage amount (normalized 0-1)
            attacker: Who attacked
            target: Who was attacked
            
        Returns:
            GameEvent or None
        """
        event_type_map = {
            "start": GameEventType.COMBAT_START,
            "end": GameEventType.COMBAT_END,
            "hit_taken": GameEventType.COMBAT_HIT_TAKEN,
            "hit_dealt": GameEventType.COMBAT_HIT_DEALT,
            "ally_died": GameEventType.COMBAT_ALLY_DIED,
            "enemy_died": GameEventType.COMBAT_ENEMY_DIED,
        }
        
        event_type = event_type_map.get(event_subtype)
        if not event_type:
            return None
        
        return self.adapt(
            event_type=event_type,
            npc_id=npc_id,
            magnitude=damage,
            data={"attacker": attacker, "target": target},
            tags=["combat"],
        )
    
    def adapt_dialogue_event(
        self,
        npc_id: str,
        player_id: str,
        event_subtype: str,
        branch_id: Optional[str] = None,
    ) -> Optional[GameEvent]:
        """
        Convenience method for dialogue events.
        
        Args:
            npc_id: NPC in dialogue
            player_id: Player in dialogue
            event_subtype: "start", "end", "branch_taken", etc.
            branch_id: ID of dialogue branch (if relevant)
            
        Returns:
            GameEvent or None
        """
        event_type_map = {
            "start": GameEventType.DIALOGUE_START,
            "end": GameEventType.DIALOGUE_END,
            "branch_taken": GameEventType.DIALOGUE_BRANCH_TAKEN,
            "persuasion_success": GameEventType.DIALOGUE_PERSUASION_SUCCESS,
            "persuasion_failure": GameEventType.DIALOGUE_PERSUASION_FAILURE,
        }
        
        event_type = event_type_map.get(event_subtype)
        if not event_type:
            return None
        
        return self.adapt(
            event_type=event_type,
            npc_id=npc_id,
            player_id=player_id,
            data={"branch_id": branch_id} if branch_id else {},
            tags=["dialogue"],
        )
    
    def adapt_time_event(
        self,
        npc_id: str,
        hours_passed: float,
    ) -> Optional[GameEvent]:
        """
        Convenience method for time passage.
        
        Args:
            npc_id: NPC experiencing time
            hours_passed: Game hours passed
            
        Returns:
            GameEvent or None
        """
        # Normalize hours to 0-1 (cap at 24 hours)
        magnitude = min(1.0, hours_passed / 24.0)
        
        return self.adapt(
            event_type=GameEventType.TIME_PASSED,
            npc_id=npc_id,
            magnitude=magnitude,
            data={"hours": hours_passed},
            tags=["time"],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get event processing statistics."""
        return {
            "enabled": self.enabled,
            "total_events": self.event_count,
            "events_by_type": {
                k.value: v for k, v in self.events_by_type.items()
            },
        }
    
    def reset_statistics(self) -> None:
        """Reset event counters."""
        self.event_count = 0
        self.events_by_type = {}
