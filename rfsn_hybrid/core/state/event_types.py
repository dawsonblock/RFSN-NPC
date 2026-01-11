"""
Event types for the state reducer.

All state mutations are represented as events. This enables:
- Deterministic replay
- Single-writer pattern (no races)
- Transaction boundaries
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Literal, Optional


class EventType(str, Enum):
    """All possible state mutation events."""
    
    # Affinity/mood changes
    AFFINITY_DELTA = "affinity_delta"
    MOOD_SET = "mood_set"
    
    # Fact operations
    FACT_ADD = "fact_add"
    FACT_REMOVE = "fact_remove"
    FACT_DECAY = "fact_decay"
    FACT_REINFORCE = "fact_reinforce"
    
    # Conversation operations
    TURN_ADD = "turn_add"
    TURN_CLEAR = "turn_clear"
    
    # Player interactions
    PLAYER_EVENT = "player_event"
    
    # Relationship changes
    RELATIONSHIP_UPDATE = "relationship_update"
    
    # State management
    STATE_RESET = "state_reset"
    STATE_LOAD = "state_load"
    STATE_SNAPSHOT = "state_snapshot"
    
    # Transaction control
    TRANSACTION_BEGIN = "transaction_begin"
    TRANSACTION_COMMIT = "transaction_commit"
    TRANSACTION_ABORT = "transaction_abort"


@dataclass(frozen=True)
class StateEvent:
    """
    Immutable event representing a state mutation.
    
    Events are the ONLY way to modify state. They are:
    - Immutable (frozen dataclass)
    - Timestamped
    - Sequenced
    - Traceable (convo_id, npc_id)
    
    Attributes:
        event_type: Type of mutation
        npc_id: Target NPC identifier
        payload: Event-specific data
        timestamp: When event was created (ISO format)
        seq: Sequence number for ordering
        convo_id: Conversation ID for grouping
        source: What created this event (for debugging)
    """
    event_type: EventType
    npc_id: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    seq: int = 0
    convo_id: Optional[str] = None
    source: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/persistence."""
        return {
            "event_type": self.event_type.value,
            "npc_id": self.npc_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "seq": self.seq,
            "convo_id": self.convo_id,
            "source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateEvent":
        """Deserialize from dictionary."""
        return cls(
            event_type=EventType(data["event_type"]),
            npc_id=data["npc_id"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            seq=data.get("seq", 0),
            convo_id=data.get("convo_id"),
            source=data.get("source", "unknown"),
        )


# Event factory functions for common operations

def affinity_delta_event(
    npc_id: str,
    delta: float,
    reason: str = "",
    convo_id: Optional[str] = None,
) -> StateEvent:
    """Create an affinity change event."""
    return StateEvent(
        event_type=EventType.AFFINITY_DELTA,
        npc_id=npc_id,
        payload={"delta": delta, "reason": reason},
        convo_id=convo_id,
        source="affinity_delta_event",
    )


def mood_set_event(
    npc_id: str,
    mood: str,
    convo_id: Optional[str] = None,
) -> StateEvent:
    """Create a mood change event."""
    return StateEvent(
        event_type=EventType.MOOD_SET,
        npc_id=npc_id,
        payload={"mood": mood},
        convo_id=convo_id,
        source="mood_set_event",
    )


def fact_add_event(
    npc_id: str,
    text: str,
    tags: List[str],
    salience: float,
    convo_id: Optional[str] = None,
) -> StateEvent:
    """Create a fact addition event."""
    return StateEvent(
        event_type=EventType.FACT_ADD,
        npc_id=npc_id,
        payload={"text": text, "tags": tags, "salience": salience},
        convo_id=convo_id,
        source="fact_add_event",
    )


def turn_add_event(
    npc_id: str,
    role: Literal["user", "assistant"],
    content: str,
    convo_id: Optional[str] = None,
) -> StateEvent:
    """Create a conversation turn event."""
    return StateEvent(
        event_type=EventType.TURN_ADD,
        npc_id=npc_id,
        payload={"role": role, "content": content},
        convo_id=convo_id,
        source="turn_add_event",
    )


def player_event(
    npc_id: str,
    event_type_str: str,
    strength: float,
    tags: List[str],
    convo_id: Optional[str] = None,
) -> StateEvent:
    """Create a player interaction event."""
    return StateEvent(
        event_type=EventType.PLAYER_EVENT,
        npc_id=npc_id,
        payload={
            "player_event_type": event_type_str,
            "strength": strength,
            "tags": tags,
        },
        convo_id=convo_id,
        source="player_event",
    )


def transaction_begin_event(
    npc_id: str,
    convo_id: str,
) -> StateEvent:
    """Begin a transaction - events buffered until commit."""
    return StateEvent(
        event_type=EventType.TRANSACTION_BEGIN,
        npc_id=npc_id,
        payload={},
        convo_id=convo_id,
        source="transaction",
    )


def transaction_commit_event(
    npc_id: str,
    convo_id: str,
) -> StateEvent:
    """Commit transaction - apply all buffered events."""
    return StateEvent(
        event_type=EventType.TRANSACTION_COMMIT,
        npc_id=npc_id,
        payload={},
        convo_id=convo_id,
        source="transaction",
    )


def transaction_abort_event(
    npc_id: str,
    convo_id: str,
    reason: str,
) -> StateEvent:
    """Abort transaction - discard all buffered events."""
    return StateEvent(
        event_type=EventType.TRANSACTION_ABORT,
        npc_id=npc_id,
        payload={"reason": reason},
        convo_id=convo_id,
        source="transaction",
    )
