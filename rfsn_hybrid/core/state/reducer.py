"""
Optimized pure reducer function for state transitions.

Uses dispatch dictionary for O(1) event type lookup and
minimizes deep copies for better performance.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import replace
from datetime import datetime
from typing import Callable, Dict, List, Tuple, Optional, Any

from .event_types import StateEvent, EventType
from ...types import RFSNState
from ...storage import Fact
from ...util import clamp

logger = logging.getLogger(__name__)

# Module-level constants for player events (avoid recreating on each call)
_AFFINITY_MAP: Dict[str, float] = {
    "GIFT": 0.15,
    "PRAISE": 0.08,
    "HELP": 0.06,
    "PUNCH": -0.35,
    "INSULT": -0.20,
    "THREATEN": -0.25,
    "THEFT": -0.15,
    "TALK": 0.0,
}

_MOOD_MAP: Dict[str, str] = {
    "GIFT": "Pleased",
    "PRAISE": "Warm",
    "HELP": "Grateful",
    "PUNCH": "Angry",
    "INSULT": "Offended",
    "THREATEN": "Hostile",
    "THEFT": "Suspicious",
}


def _handle_affinity_delta(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle AFFINITY_DELTA event."""
    delta = payload.get("delta", 0.0)
    # Shallow copy + modify single field
    new_state = copy.copy(state)
    new_state.affinity = clamp(state.affinity + delta, -1.0, 1.0)
    return new_state, facts, None


def _handle_mood_set(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle MOOD_SET event."""
    new_state = copy.copy(state)
    new_state.mood = payload.get("mood", "Neutral")
    return new_state, facts, None


def _handle_fact_add(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle FACT_ADD event."""
    if facts is None:
        return state, facts, None
    
    text = payload.get("text", "")
    tags = payload.get("tags", [])
    salience = payload.get("salience", 0.5)

    # Admission Policy
    if len(text) > 2000:
        logger.warning("Fact rejected: Too long")
        return state, facts, None
    if any(b in text.lower() for b in ["<|", "|>", "system instruction"]):
        logger.warning("Fact rejected: Contains forbidden tokens")
        return state, facts, None
    
    # Only copy the list, not all facts
    new_facts = list(facts)
    new_facts.append(Fact(
        text=text,
        tags=tags,
        time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        salience=salience,
    ))
    return state, new_facts, text


def _handle_fact_decay(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle FACT_DECAY event - modifies salience values."""
    if facts is None:
        return state, facts, None
    
    decay_rate = payload.get("decay_rate", 0.05)
    min_salience = payload.get("min_salience", 0.1)
    
    # Deep copy only when modifying fact attributes
    new_facts = [copy.copy(f) for f in facts]
    for fact in new_facts:
        if fact.salience > min_salience:
            fact.salience = max(min_salience, fact.salience - decay_rate)
    
    return state, new_facts, None


def _handle_fact_reinforce(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle FACT_REINFORCE event."""
    if facts is None:
        return state, facts, None
    
    fragment = payload.get("fragment", "").lower()
    boost = payload.get("boost", 0.1)
    
    if not fragment:
        return state, facts, None
    
    # Only copy facts that need modification
    modified = False
    new_facts = list(facts)
    for i, fact in enumerate(facts):
        if fragment in fact.text.lower():
            if not modified:
                new_facts = [copy.copy(f) for f in facts]
                modified = True
            new_facts[i].salience = min(1.0, fact.salience + boost)
    
    return state, new_facts if modified else facts, None


def _handle_player_event(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle PLAYER_EVENT using cached lookup tables."""
    player_event_type = payload.get("player_event_type", "TALK")
    strength = payload.get("strength", 0.5)
    
    delta = _AFFINITY_MAP.get(player_event_type, 0.0) * strength
    new_state = copy.copy(state)
    new_state.affinity = clamp(state.affinity + delta, -1.0, 1.0)
    
    if player_event_type in _MOOD_MAP:
        new_state.mood = _MOOD_MAP[player_event_type]
    
    return new_state, facts, None


def _handle_state_reset(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle STATE_RESET event."""
    new_state = copy.copy(state)
    new_state.affinity = payload.get("affinity", 0.0)
    new_state.mood = payload.get("mood", "Neutral")
    new_state.recent_memory = ""
    return new_state, facts, None


def _handle_state_load(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """Handle STATE_LOAD event."""
    if "state_dict" not in payload:
        return state, facts, None
    
    loaded = payload["state_dict"]
    new_state = copy.copy(state)
    new_state.affinity = loaded.get("affinity", state.affinity)
    new_state.mood = loaded.get("mood", state.mood)
    new_state.recent_memory = loaded.get("recent_memory", "")
    return new_state, facts, None


def _handle_noop(
    state: RFSNState,
    facts: Optional[List[Fact]],
    payload: Dict[str, Any],
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """No-op handler for transaction events."""
    return state, facts, None


# O(1) dispatch table
_EVENT_HANDLERS: Dict[EventType, Callable] = {
    EventType.AFFINITY_DELTA: _handle_affinity_delta,
    EventType.MOOD_SET: _handle_mood_set,
    EventType.FACT_ADD: _handle_fact_add,
    EventType.FACT_DECAY: _handle_fact_decay,
    EventType.FACT_REINFORCE: _handle_fact_reinforce,
    EventType.PLAYER_EVENT: _handle_player_event,
    EventType.STATE_RESET: _handle_state_reset,
    EventType.STATE_LOAD: _handle_state_load,
    EventType.TRANSACTION_BEGIN: _handle_noop,
    EventType.TRANSACTION_COMMIT: _handle_noop,
    EventType.TRANSACTION_ABORT: _handle_noop,
}


def reduce_state(
    state: RFSNState,
    event: StateEvent,
    facts: Optional[List[Fact]] = None,
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """
    Apply an event to produce a new state.
    
    Uses O(1) dispatch table lookup for performance.
    Minimizes copies - only creates new objects when necessary.
    """
    handler = _EVENT_HANDLERS.get(event.event_type)
    
    if handler is None:
        logger.warning(f"Unknown event type: {event.event_type}")
        return state, facts, None
    
    return handler(state, facts, event.payload)


def reduce_events(
    initial_state: RFSNState,
    events: List[StateEvent],
    initial_facts: Optional[List[Fact]] = None,
) -> Tuple[RFSNState, Optional[List[Fact]]]:
    """Apply a sequence of events to get final state."""
    state = initial_state
    facts = initial_facts
    
    for event in events:
        state, facts, _ = reduce_state(state, event, facts)
    
    return state, facts
