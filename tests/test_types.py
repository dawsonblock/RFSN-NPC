"""Tests for RFSNState persistence and serialization."""
import os
import tempfile
from rfsn_hybrid.types import RFSNState


def base_state(affinity: float = 0.5, mood: str = "Neutral") -> RFSNState:
    return RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=affinity,
        mood=mood,
        player_name="Dragonborn",
        player_playstyle="Combatant",
        recent_memory="Test memory",
    )


def test_to_dict_roundtrip():
    """State should serialize and deserialize correctly."""
    original = base_state(0.75, "Pleased")
    data = original.to_dict()
    restored = RFSNState.from_dict(data)
    
    assert restored.npc_name == original.npc_name
    assert restored.role == original.role
    assert restored.affinity == original.affinity
    assert restored.mood == original.mood
    assert restored.player_name == original.player_name
    assert restored.player_playstyle == original.player_playstyle
    assert restored.recent_memory == original.recent_memory


def test_save_and_load():
    """State should persist to disk and reload correctly."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "npc_state.json")
        
        original = base_state(-0.3, "Suspicious")
        original.save(path)
        
        loaded = RFSNState.load(path)
        assert loaded is not None
        assert loaded.npc_name == "Lydia"
        assert loaded.affinity == -0.3
        assert loaded.mood == "Suspicious"


def test_load_missing_file_returns_none():
    """Loading from a non-existent file should return None."""
    result = RFSNState.load("/nonexistent/path/state.json")
    assert result is None


def test_load_corrupted_file_returns_none():
    """Loading from a corrupted JSON file should return None."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bad.json")
        with open(path, "w") as f:
            f.write("{ invalid json garbage }")
        
        result = RFSNState.load(path)
        assert result is None


def test_attitude_thresholds():
    """Attitude strings should change at correct affinity thresholds."""
    assert "Hostile" in base_state(-0.9).attitude()
    assert "Cold" in base_state(-0.5).attitude()
    assert "Neutral" in base_state(0.0).attitude()
    assert "Friendly" in base_state(0.5).attitude()
    assert "Devoted" in base_state(0.9).attitude()
