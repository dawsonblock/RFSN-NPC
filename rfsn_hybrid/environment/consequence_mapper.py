"""
Consequence mapper for environment feedback.

Maps game events to NPC-relevant consequence signals.
These signals represent how the NPC "feels" about events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .event_adapter import GameEvent, GameEventType


class ConsequenceType(str, Enum):
    """Types of consequences from events."""
    STRESS = "stress"              # Anxiety, tension
    RELIEF = "relief"              # Calm, relaxation
    THREAT = "threat"              # Danger perceived
    SAFETY = "safety"              # Security felt
    BONDING = "bonding"            # Connection with player
    ALIENATION = "alienation"      # Disconnection from player
    ACHIEVEMENT = "achievement"    # Success, accomplishment
    FAILURE = "failure"            # Defeat, loss
    INJUSTICE = "injustice"        # Wrong witnessed
    JUSTICE = "justice"            # Right witnessed


@dataclass
class ConsequenceSignal:
    """
    A normalized signal representing how an event affects the NPC.
    
    Attributes:
        consequence_type: Type of consequence
        intensity: Signal strength (0.0 to 1.0)
        source_event: Original event type
        affects: What this consequence affects (mood, relationship, etc.)
        decay_rate: How quickly signal fades (per hour)
        data: Additional signal data
    """
    consequence_type: ConsequenceType
    intensity: float
    source_event: GameEventType
    affects: List[str] = field(default_factory=list)
    decay_rate: float = 0.1
    data: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure intensity is bounded."""
        self.intensity = max(0.0, min(1.0, self.intensity))
        self.decay_rate = max(0.0, min(1.0, self.decay_rate))
    
    def to_dict(self) -> Dict:
        return {
            "consequence_type": self.consequence_type.value,
            "intensity": self.intensity,
            "source_event": self.source_event.value,
            "affects": self.affects,
            "decay_rate": self.decay_rate,
            "data": self.data,
        }


class ConsequenceMapper:
    """
    Maps game events to NPC consequence signals.
    
    This is where we define how different events affect the NPC's
    internal state. The mapping is deterministic and configurable.
    """
    
    # Default mappings: event_type -> (consequence_type, base_intensity, affects)
    DEFAULT_MAPPINGS: Dict[GameEventType, List[tuple]] = {
        # Combat events
        GameEventType.COMBAT_START: [
            (ConsequenceType.STRESS, 0.6, ["mood"], 0.2),
            (ConsequenceType.THREAT, 0.7, ["mood"], 0.3),
        ],
        GameEventType.COMBAT_END: [
            (ConsequenceType.RELIEF, 0.5, ["mood"], 0.15),
        ],
        GameEventType.COMBAT_HIT_TAKEN: [
            (ConsequenceType.STRESS, 0.7, ["mood"], 0.1),
            (ConsequenceType.THREAT, 0.8, ["mood"], 0.15),
        ],
        GameEventType.COMBAT_HIT_DEALT: [
            (ConsequenceType.ACHIEVEMENT, 0.4, ["mood"], 0.2),
        ],
        GameEventType.COMBAT_ALLY_DIED: [
            (ConsequenceType.STRESS, 0.9, ["mood"], 0.05),
            (ConsequenceType.FAILURE, 0.6, ["mood"], 0.1),
        ],
        GameEventType.COMBAT_ENEMY_DIED: [
            (ConsequenceType.RELIEF, 0.6, ["mood"], 0.2),
            (ConsequenceType.SAFETY, 0.5, ["mood"], 0.25),
        ],
        
        # Dialogue events
        GameEventType.DIALOGUE_START: [
            (ConsequenceType.BONDING, 0.3, ["relationship"], 0.3),
        ],
        GameEventType.DIALOGUE_PERSUASION_SUCCESS: [
            (ConsequenceType.BONDING, 0.5, ["relationship"], 0.2),
        ],
        GameEventType.DIALOGUE_PERSUASION_FAILURE: [
            (ConsequenceType.ALIENATION, 0.4, ["relationship"], 0.25),
        ],
        
        # Social events
        GameEventType.WITNESSED_CRIME: [
            (ConsequenceType.INJUSTICE, 0.7, ["relationship", "mood"], 0.15),
            (ConsequenceType.ALIENATION, 0.6, ["relationship"], 0.2),
        ],
        GameEventType.WITNESSED_GOOD_DEED: [
            (ConsequenceType.JUSTICE, 0.6, ["relationship"], 0.2),
            (ConsequenceType.BONDING, 0.5, ["relationship"], 0.25),
        ],
        
        # Quest events
        GameEventType.QUEST_COMPLETED: [
            (ConsequenceType.ACHIEVEMENT, 0.8, ["mood", "relationship"], 0.1),
            (ConsequenceType.BONDING, 0.7, ["relationship"], 0.15),
        ],
        GameEventType.QUEST_FAILED: [
            (ConsequenceType.FAILURE, 0.7, ["mood"], 0.15),
            (ConsequenceType.ALIENATION, 0.5, ["relationship"], 0.2),
        ],
        
        # Item events
        GameEventType.ITEM_STOLEN: [
            (ConsequenceType.INJUSTICE, 0.9, ["relationship", "mood"], 0.05),
            (ConsequenceType.ALIENATION, 0.8, ["relationship"], 0.1),
        ],
        GameEventType.ITEM_RECEIVED: [
            (ConsequenceType.BONDING, 0.6, ["relationship"], 0.2),
        ],
        
        # Time passage
        GameEventType.TIME_PASSED: [
            (ConsequenceType.RELIEF, 0.1, ["mood"], 0.5),  # Natural calming
        ],
    }
    
    def __init__(
        self,
        custom_mappings: Optional[Dict[GameEventType, List[tuple]]] = None,
        enabled: bool = True,
    ):
        """
        Initialize consequence mapper.
        
        Args:
            custom_mappings: Override default event mappings
            enabled: Whether to process events
        """
        self.mappings = self.DEFAULT_MAPPINGS.copy()
        if custom_mappings:
            self.mappings.update(custom_mappings)
        self.enabled = enabled
    
    def map_event(self, event: GameEvent) -> List[ConsequenceSignal]:
        """
        Map a game event to consequence signals.
        
        Args:
            event: Game event to map
            
        Returns:
            List of consequence signals
        """
        if not self.enabled:
            return []
        
        mapping = self.mappings.get(event.event_type, [])
        signals = []
        
        for consequence_type, base_intensity, affects, decay_rate in mapping:
            # Scale intensity by event magnitude
            intensity = base_intensity * event.magnitude
            
            signal = ConsequenceSignal(
                consequence_type=consequence_type,
                intensity=intensity,
                source_event=event.event_type,
                affects=affects,
                decay_rate=decay_rate,
                data=event.data,
            )
            signals.append(signal)
        
        return signals
    
    def map_batch(self, events: List[GameEvent]) -> List[ConsequenceSignal]:
        """
        Map multiple events efficiently.
        
        Args:
            events: List of game events
            
        Returns:
            List of all consequence signals
        """
        signals = []
        for event in events:
            signals.extend(self.map_event(event))
        return signals
    
    def add_mapping(
        self,
        event_type: GameEventType,
        consequence_type: ConsequenceType,
        base_intensity: float,
        affects: List[str],
        decay_rate: float = 0.2,
    ) -> None:
        """
        Add or override an event mapping.
        
        Args:
            event_type: Game event type
            consequence_type: Consequence to map to
            base_intensity: Base signal strength
            affects: What this affects
            decay_rate: How quickly signal fades
        """
        if event_type not in self.mappings:
            self.mappings[event_type] = []
        
        self.mappings[event_type].append((
            consequence_type,
            max(0.0, min(1.0, base_intensity)),
            affects,
            max(0.0, min(1.0, decay_rate)),
        ))
    
    def get_mappings_for_event(
        self,
        event_type: GameEventType,
    ) -> List[tuple]:
        """Get all mappings for an event type."""
        return self.mappings.get(event_type, [])
