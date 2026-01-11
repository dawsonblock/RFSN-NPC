"""
Tests for transaction abort behavior.

Killing a stream mid-way should NOT change NPC state.
"""
import pytest

from rfsn_hybrid.types import RFSNState
from rfsn_hybrid.storage import FactsStore
from rfsn_hybrid.core.state.store import StateStore
from rfsn_hybrid.core.state.event_types import (
    affinity_delta_event,
    mood_set_event,
    transaction_begin_event,
    transaction_abort_event,
    transaction_commit_event,
)
from rfsn_hybrid.streaming.transaction import StreamTransaction


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


@pytest.fixture
def store(initial_state):
    """Create state store."""
    return StateStore(initial_state)


class TestTransactionAbort:
    """Test that aborted transactions don't modify state."""
    
    def test_abort_discards_buffered_events(self, store, initial_state):
        """Events in aborted transaction should be discarded."""
        original_affinity = initial_state.affinity
        
        # Begin transaction
        store.dispatch(transaction_begin_event("lydia", "test-convo"))
        
        # Dispatch events (buffered)
        store.dispatch(affinity_delta_event("lydia", 0.5, convo_id="test-convo"))
        store.dispatch(mood_set_event("lydia", "Happy", convo_id="test-convo"))
        
        # Abort
        store.dispatch(transaction_abort_event("lydia", "test-convo", "test abort"))
        
        # State should be unchanged
        snapshot = store.get_snapshot()
        assert snapshot.affinity == original_affinity
        assert snapshot.mood == "Neutral"
    
    def test_commit_applies_buffered_events(self, store, initial_state):
        """Committed transaction should apply all events."""
        # Begin transaction
        store.dispatch(transaction_begin_event("lydia", "test-convo"))
        
        # Dispatch events (buffered)
        store.dispatch(affinity_delta_event("lydia", 0.3, convo_id="test-convo"))
        store.dispatch(mood_set_event("lydia", "Happy", convo_id="test-convo"))
        
        # Commit
        store.dispatch(transaction_commit_event("lydia", "test-convo"))
        
        # State should be updated
        snapshot = store.get_snapshot()
        assert snapshot.affinity == pytest.approx(0.8)
        assert snapshot.mood == "Happy"
    
    def test_stream_transaction_abort(self, store):
        """StreamTransaction abort should not modify state."""
        original = store.get_snapshot()
        
        txn = StreamTransaction("lydia", store)
        txn.start("Hello!")
        txn.add_text("Greetings, ")
        txn.add_text("my Thane.")
        txn.queue_affinity_change(0.5, "greeting")
        
        # Abort (simulating error)
        txn.abort("Generator failed")
        
        # State unchanged
        snapshot = store.get_snapshot()
        assert snapshot.affinity == original.affinity
    
    def test_stream_transaction_commit(self, store):
        """StreamTransaction commit should apply changes."""
        txn = StreamTransaction("lydia", store)
        txn.start("Give gift")
        txn.add_text("Thank you!")
        txn.queue_affinity_change(0.2, "gift")
        txn.queue_mood_change("Pleased")
        
        txn.commit()
        
        snapshot = store.get_snapshot()
        assert snapshot.affinity == pytest.approx(0.7)
        assert snapshot.mood == "Pleased"
    
    def test_nested_transaction_not_allowed(self, store):
        """Starting a transaction when one exists should warn."""
        store.dispatch(transaction_begin_event("lydia", "convo-1"))
        
        # Second begin with same ID should be ignored
        store.dispatch(transaction_begin_event("lydia", "convo-1"))
        
        # Should still work
        store.dispatch(transaction_abort_event("lydia", "convo-1", "cleanup"))
    
    def test_abort_after_partial_text(self, store):
        """Partial text generation then abort should be safe."""
        original = store.get_snapshot()
        
        txn = StreamTransaction("lydia", store)
        txn.start("Tell me about dragons")
        
        # Simulate partial generation
        for i in range(5):
            txn.add_text(f"Token {i} ")
        
        # Something goes wrong
        txn.abort("TTS failed mid-stream")
        
        # No state change
        snapshot = store.get_snapshot()
        assert snapshot.affinity == original.affinity
    
    def test_multiple_transactions_isolated(self, store):
        """Different convo_ids should be isolated."""
        # Start two transactions
        store.dispatch(transaction_begin_event("lydia", "convo-1"))
        store.dispatch(transaction_begin_event("lydia", "convo-2"))
        
        # Events to first
        store.dispatch(affinity_delta_event("lydia", 0.3, convo_id="convo-1"))
        
        # Events to second
        store.dispatch(affinity_delta_event("lydia", -0.2, convo_id="convo-2"))
        
        # Abort first, commit second
        store.dispatch(transaction_abort_event("lydia", "convo-1", "aborted"))
        store.dispatch(transaction_commit_event("lydia", "convo-2"))
        
        # Only second should apply
        snapshot = store.get_snapshot()
        assert snapshot.affinity == pytest.approx(0.3)  # 0.5 - 0.2
