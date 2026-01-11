"""
Tests for replay determinism.

Event stream replay should produce identical final state.
"""
import copy

import pytest

from rfsn_hybrid.types import RFSNState
from rfsn_hybrid.core.state.event_types import (
    StateEvent,
    EventType,
    affinity_delta_event,
    mood_set_event,
    player_event,
)
from rfsn_hybrid.core.state.reducer import reduce_state, reduce_events


@pytest.fixture
def initial_state():
    """Create initial NPC state."""
    return RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=0.5,
        mood="Neutral",
        player_name="Player",
        player_playstyle="Adventurer",
    )


class TestReplayDeterminism:
    """Verify event replay produces identical state."""
    
    def test_single_event_determinism(self, initial_state):
        """Same event should produce same state."""
        event = affinity_delta_event("lydia", 0.1, "gift")
        
        state1, _, _ = reduce_state(initial_state, event)
        state2, _, _ = reduce_state(initial_state, event)
        
        assert state1.affinity == state2.affinity
        assert state1.mood == state2.mood
    
    def test_event_sequence_determinism(self, initial_state):
        """Same event sequence should produce same final state."""
        events = [
            affinity_delta_event("lydia", 0.1, "gift"),
            mood_set_event("lydia", "Happy"),
            affinity_delta_event("lydia", -0.05, "time"),
            player_event("lydia", "PRAISE", 0.5, ["positive"]),
        ]
        
        # Apply sequence twice
        final1, _ = reduce_events(initial_state, events)
        final2, _ = reduce_events(initial_state, events)
        
        assert final1.affinity == final2.affinity
        assert final1.mood == final2.mood
    
    def test_reordering_changes_result(self, initial_state):
        """Different event order should (potentially) produce different state."""
        events_a = [
            affinity_delta_event("lydia", 0.5, "gift"),  # 0.5 -> 1.0
            affinity_delta_event("lydia", -0.3, "insult"),  # 1.0 -> 0.7
        ]
        
        events_b = [
            affinity_delta_event("lydia", -0.3, "insult"),  # 0.5 -> 0.2
            affinity_delta_event("lydia", 0.5, "gift"),  # 0.2 -> 0.7
        ]
        
        final_a, _ = reduce_events(initial_state, events_a)
        final_b, _ = reduce_events(initial_state, events_b)
        
        # Both should end at 0.7 (additive)
        assert abs(final_a.affinity - 0.7) < 0.01
        assert abs(final_b.affinity - 0.7) < 0.01
    
    def test_reducer_does_not_mutate_input(self, initial_state):
        """Reducer should not mutate input state."""
        original_affinity = initial_state.affinity
        
        event = affinity_delta_event("lydia", 0.5, "gift")
        new_state, _, _ = reduce_state(initial_state, event)
        
        # Original unchanged
        assert initial_state.affinity == original_affinity
        # New state changed
        assert new_state.affinity != original_affinity
    
    def test_empty_event_sequence(self, initial_state):
        """Empty event sequence should return initial state."""
        final, _ = reduce_events(initial_state, [])
        
        assert final.affinity == initial_state.affinity
        assert final.mood == initial_state.mood
    
    def test_clamping_at_boundaries(self, initial_state):
        """Affinity should clamp at -1 and 1."""
        # Try to exceed upper bound
        events = [affinity_delta_event("lydia", 10.0, "huge gift")]
        final, _ = reduce_events(initial_state, events)
        assert final.affinity == 1.0
        
        # Try to exceed lower bound
        initial_state.affinity = -0.5
        events = [affinity_delta_event("lydia", -10.0, "huge insult")]
        final, _ = reduce_events(initial_state, events)
        assert final.affinity == -1.0
