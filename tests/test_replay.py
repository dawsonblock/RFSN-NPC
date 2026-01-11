"""
Tests for replay and state diffing.
"""
import pytest
from rfsn_hybrid.replay import StateDiff, TraceRecorder, DialogueTurn, get_trace_recorder
from rfsn_hybrid.types import RFSNState

@pytest.fixture
def sample_state():
    return RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=0.5,
        mood="Neutral",
        player_name="Player",
        player_playstyle="Hero",
    )

class TestStateDiff:
    """Test state diffing logic."""
    
    def test_no_changes(self, sample_state):
        diff = StateDiff.compute(sample_state, sample_state)
        assert not diff.changes
        assert "No state changes" in diff.summary()
        
    def test_changes_detected(self, sample_state):
        new_state = RFSNState.from_dict(sample_state.to_dict())
        new_state.affinity = 0.8
        new_state.mood = "Happy"
        
        diff = StateDiff.compute(sample_state, new_state)
        assert "affinity" in diff.changes
        assert "mood" in diff.changes
        
        old_val, new_val = diff.changes["affinity"]
        assert old_val == 0.5
        assert new_val == 0.8
        
        summary = diff.summary()
        assert "affinity: 0.5 -> 0.8" in summary

class TestTraceRecorder:
    """Test trace recording."""
    
    def test_lifecycle(self, tmp_path, sample_state):
        recorder = TraceRecorder(str(tmp_path))
        
        # Start
        session_id = recorder.start_session("lydia")
        assert session_id.startswith("lydia_")
        
        # Record turn
        new_state = RFSNState.from_dict(sample_state.to_dict())
        new_state.affinity = 0.6
        
        recorder.record_turn(
            user_input="Hello",
            npc_response="Greetings",
            old_state=sample_state,
            new_state=new_state,
            processing_time_ms=100.0,
        )
        
        # End
        recorder.end_session()
        
        # Verify file
        trace = recorder.load_trace(session_id)
        assert len(trace) == 3  # Start, Turn, End
        
        assert trace[0]["type"] == "session_start"
        assert trace[1]["type"] == "turn"
        assert trace[1]["data"]["user_input"] == "Hello"
        assert trace[1]["data"]["state_diff"]["affinity"][1] == 0.6
        assert trace[2]["type"] == "session_end"

class TestGlobalRecorder:
    """Test global singleton."""
    
    def test_singleton(self):
        r1 = get_trace_recorder()
        r2 = get_trace_recorder()
        assert r1 is r2
