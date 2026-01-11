"""
Tests for conversation harness.
"""
import pytest
from rfsn_hybrid.harness import ConversationHarness, ReplayResult
from rfsn_hybrid.types import RFSNState

# Mock engine for harness testing
class MockEngine:
    pass

class TestConversationHarness:
    """Test the harness logic."""
    
    def test_init(self):
        engine = MockEngine()
        harness = ConversationHarness(engine)
        assert harness.engine is engine
    
    def test_result_object(self):
        res = ReplayResult(True, 10, 0, [], "sess_1")
        assert res.success
        assert res.failed_turns == 0
