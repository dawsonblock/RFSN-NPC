"""
Pure reducer function for state transitions.

The reducer is a pure function: (state, event) -> new_state
- No side effects
- Deterministic
- Returns a new state copy (never mutates input)

This enables:
- Replay for debugging
- Testing without mocks
- Time-travel debugging
"""
from __future__ import annotations

import copy
import logging
from dataclasses import replace
from datetime import datetime
from typing import List, Tuple, Optional

from .event_types import StateEvent, EventType
from ...types import RFSNState
from ...storage import Fact
from ...util import clamp


def reduce_state(
    state: RFSNState,
    event: StateEvent,
    facts: Optional[List[Fact]] = None,
) -> Tuple[RFSNState, Optional[List[Fact]], Optional[str]]:
    """
    Apply an event to produce a new state.
    
    This is the ONLY function that should modify NPC state.
    It is pure: given the same inputs, always returns the same outputs.
    
    Args:
        state: Current NPC state (not mutated)
        event: Event to apply
        facts: Optional list of facts (not mutated)
        
    Returns:
        Tuple of (new_state, new_facts, new_fact_text_if_any)
        
    Note:
        Transaction events return the state unchanged - they are
        handled by the store layer.
    """
    # Make copies to avoid mutation
    new_state = copy.deepcopy(state)
    new_facts = copy.deepcopy(facts) if facts is not None else None
    new_fact_text = None
    
    event_type = event.event_type
    
    if event_type == EventType.AFFINITY_DELTA:
        delta = event.payload.get("delta", 0.0)
        new_state.affinity = clamp(new_state.affinity + delta, -1.0, 1.0)
        
    elif event_type == EventType.MOOD_SET:
        new_state.mood = event.payload.get("mood", "Neutral")
        
    elif event_type == EventType.FACT_ADD:
        if new_facts is not None:
            text = event.payload.get("text", "")
            tags = event.payload.get("tags", [])
            salience = event.payload.get("salience", 0.5)
            new_facts.append(Fact(
                text=text,
                tags=tags,
                time=datetime.now().strftime("%Y-%m-%d %H:%M"),
                salience=salience,
            ))
            new_fact_text = text
            
    elif event_type == EventType.FACT_DECAY:
        if new_facts is not None:
            decay_rate = event.payload.get("decay_rate", 0.05)
            min_salience = event.payload.get("min_salience", 0.1)
            for fact in new_facts:
                if fact.salience > min_salience:
                    fact.salience = max(min_salience, fact.salience - decay_rate)
                    
    elif event_type == EventType.FACT_REINFORCE:
        if new_facts is not None:
            fragment = event.payload.get("fragment", "").lower()
            boost = event.payload.get("boost", 0.1)
            for fact in new_facts:
                if fragment in fact.text.lower():
                    fact.salience = min(1.0, fact.salience + boost)
                    
    elif event_type == EventType.PLAYER_EVENT:
        # Delegate to the legacy transition logic
        player_event_type = event.payload.get("player_event_type", "TALK")
        strength = event.payload.get("strength", 0.5)
        
        # Apply affinity/mood based on event type
        affinity_map = {
            "GIFT": 0.15,
            "PRAISE": 0.08,
            "HELP": 0.06,
            "PUNCH": -0.35,
            "INSULT": -0.20,
            "THREATEN": -0.25,
            "THEFT": -0.15,
            "TALK": 0.0,
        }
        mood_map = {
            "GIFT": "Pleased",
            "PRAISE": "Warm",
            "HELP": "Grateful",
            "PUNCH": "Angry",
            "INSULT": "Offended",
            "THREATEN": "Hostile",
            "THEFT": "Suspicious",
        }
        
        delta = affinity_map.get(player_event_type, 0.0) * strength
        new_state.affinity = clamp(new_state.affinity + delta, -1.0, 1.0)
        
        if player_event_type in mood_map:
            new_state.mood = mood_map[player_event_type]
            
    elif event_type == EventType.STATE_RESET:
        # Reset to initial values
        new_state.affinity = event.payload.get("affinity", 0.0)
        new_state.mood = event.payload.get("mood", "Neutral")
        new_state.recent_memory = ""
        
    elif event_type == EventType.STATE_LOAD:
        # Load from saved state
        if "state_dict" in event.payload:
            loaded = event.payload["state_dict"]
            new_state.affinity = loaded.get("affinity", new_state.affinity)
            new_state.mood = loaded.get("mood", new_state.mood)
            new_state.recent_memory = loaded.get("recent_memory", "")
            
    elif event_type in (EventType.TRANSACTION_BEGIN, EventType.TRANSACTION_COMMIT, EventType.TRANSACTION_ABORT):
        # Transaction events are handled by the store, not the reducer
        pass
        
    else:
        # Unknown event type - log warning but don't crash
        logging.warning(f"Unknown event type: {event.event_type}")
    
    return new_state, new_facts, new_fact_text


def reduce_events(
    initial_state: RFSNState,
    events: List[StateEvent],
    initial_facts: Optional[List[Fact]] = None,
) -> Tuple[RFSNState, Optional[List[Fact]]]:
    """
    Apply a sequence of events to get final state.
    
    Useful for:
    - Replay from event log
    - Testing determinism
    - Reconstructing state from events
    """
    state = initial_state
    facts = initial_facts
    
    for event in events:
        state, facts, _ = reduce_state(state, event, facts)
    
    return state, facts
