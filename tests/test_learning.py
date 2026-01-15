"""
Tests for the learning layer.

Validates that learning:
- Only reweights existing actions
- Remains bounded
- Can be disabled
- Is deterministic given same inputs
"""
import os
import tempfile
import pytest

from rfsn_hybrid.learning import (
    LearningState,
    ActionWeight,
    OutcomeEvaluator,
    OutcomeType,
    Outcome,
    PolicyAdjuster,
)


class TestLearningState:
    """Tests for LearningState."""
    
    def test_disabled_by_default(self):
        """Learning should be disabled by default."""
        state = LearningState()
        assert not state.enabled
        assert state.get_weight("ctx", "action") == 1.0
    
    def test_enabled_returns_weights(self):
        """When enabled, should track and return weights."""
        state = LearningState(enabled=True)
        
        # Initially neutral
        assert state.get_weight("ctx1", "act1") == 1.0
        
        # Update weight
        new_weight = state.update_weight("ctx1", "act1", reward=0.5)
        assert new_weight > 1.0  # Positive reward increases weight
        
        # Retrieve updated weight
        assert state.get_weight("ctx1", "act1") == new_weight
    
    def test_weight_bounds_enforced(self):
        """Weights should be clamped to [min_weight, max_weight]."""
        state = LearningState(
            enabled=True,
            min_weight=0.5,
            max_weight=2.0,
        )
        
        # Try to increase beyond max
        for _ in range(20):
            state.update_weight("ctx", "act", reward=1.0, learning_rate=0.5)
        
        weight = state.get_weight("ctx", "act")
        assert weight <= 2.0
        
        # Try to decrease below min
        for _ in range(20):
            state.update_weight("ctx", "act2", reward=-1.0, learning_rate=0.5)
        
        weight = state.get_weight("ctx", "act2")
        assert weight >= 0.5
    
    def test_bounded_memory(self):
        """Should evict old entries when max_entries reached."""
        state = LearningState(enabled=True, max_entries=5)
        
        # Add 10 entries
        for i in range(10):
            state.update_weight(f"ctx{i}", f"act{i}", reward=0.5)
        
        # Should only have 5 entries (LRU eviction)
        assert len(state.weights) == 5
    
    def test_statistics_tracking(self):
        """Should track success/failure counts."""
        state = LearningState(enabled=True)
        
        # Record successes
        state.update_weight("ctx", "act", reward=0.8)
        state.update_weight("ctx", "act", reward=0.5)
        
        # Record failure
        state.update_weight("ctx", "act", reward=-0.3)
        
        stats = state.get_stats("ctx", "act")
        assert stats.success_count == 2
        assert stats.failure_count == 1
        assert stats.total_count == 3
        assert 0.0 < stats.success_rate < 1.0
    
    def test_persistence(self):
        """Should save and load state from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create and populate
            state1 = LearningState(path=path, enabled=True)
            state1.update_weight("ctx1", "act1", reward=0.5)
            state1.update_weight("ctx2", "act2", reward=-0.3)
            
            # Load from same path
            state2 = LearningState(path=path)
            assert state2.enabled == True
            assert len(state2.weights) == 2
            assert state2.get_weight("ctx1", "act1") > 1.0


class TestOutcomeEvaluator:
    """Tests for OutcomeEvaluator."""
    
    def test_default_rewards(self):
        """Should have sensible default rewards."""
        evaluator = OutcomeEvaluator()
        
        outcome = evaluator.evaluate(
            OutcomeType.DIALOGUE_SUCCESS,
            context="test",
            action="test_act",
        )
        
        assert outcome.reward > 0
        assert -1.0 <= outcome.reward <= 1.0
    
    def test_custom_rewards(self):
        """Should allow custom reward values."""
        custom = {OutcomeType.DIALOGUE_SUCCESS: 0.9}
        evaluator = OutcomeEvaluator(custom_rewards=custom)
        
        outcome = evaluator.evaluate(
            OutcomeType.DIALOGUE_SUCCESS,
            context="test",
            action="test",
        )
        
        assert outcome.reward == 0.9
    
    def test_intensity_multiplier(self):
        """Should scale reward by intensity."""
        evaluator = OutcomeEvaluator()
        
        outcome1 = evaluator.evaluate(
            OutcomeType.DIALOGUE_SUCCESS,
            context="test",
            action="test",
            intensity=0.5,
        )
        
        outcome2 = evaluator.evaluate(
            OutcomeType.DIALOGUE_SUCCESS,
            context="test",
            action="test",
            intensity=2.0,
        )
        
        assert outcome2.reward > outcome1.reward
    
    def test_affinity_change_evaluation(self):
        """Should evaluate affinity changes as outcomes."""
        evaluator = OutcomeEvaluator()
        
        # Positive change -> positive reward
        outcome = evaluator.evaluate_from_affinity_change(
            affinity_delta=0.3,
            context="test",
            action="test",
        )
        assert outcome.reward > 0
        
        # Negative change -> negative reward
        outcome = evaluator.evaluate_from_affinity_change(
            affinity_delta=-0.3,
            context="test",
            action="test",
        )
        assert outcome.reward < 0
    
    def test_player_event_evaluation(self):
        """Should evaluate player events correctly."""
        evaluator = OutcomeEvaluator()
        
        # Positive event
        outcome = evaluator.evaluate_from_player_event(
            player_event_type="GIFT",
            context="test",
            action="test",
        )
        assert outcome.reward > 0
        
        # Negative event
        outcome = evaluator.evaluate_from_player_event(
            player_event_type="PUNCH",
            context="test",
            action="test",
        )
        assert outcome.reward < 0


class TestPolicyAdjuster:
    """Tests for PolicyAdjuster."""
    
    def test_disabled_returns_neutral(self):
        """When learning disabled, should return neutral weights."""
        state = LearningState(enabled=False)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator)
        
        weight = adjuster.get_action_weight("ctx", "act")
        assert weight == 1.0
    
    def test_records_outcomes(self):
        """Should record outcomes and update weights."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator, exploration_rate=0.0)
        
        outcome = Outcome(
            outcome_type=OutcomeType.DIALOGUE_SUCCESS,
            reward=0.5,
            context="ctx1",
            action="act1",
        )
        
        new_weight = adjuster.record_outcome("ctx1", "act1", outcome)
        assert new_weight > 1.0
        
        # Weight should be retrievable
        weight = adjuster.get_action_weight("ctx1", "act1")
        assert weight == new_weight
    
    def test_affinity_feedback(self):
        """Should handle affinity feedback."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator)
        
        # Positive affinity change
        weight = adjuster.apply_affinity_feedback(
            context_key="ctx",
            action="act",
            affinity_delta=0.3,
        )
        assert weight > 1.0
    
    def test_context_key_building(self):
        """Should build consistent context keys."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator)
        
        key1 = adjuster.build_context_key(0.7, "Pleased")
        key2 = adjuster.build_context_key(0.7, "Pleased")
        assert key1 == key2
        
        # Different affinity -> different key
        key3 = adjuster.build_context_key(-0.5, "Angry")
        assert key3 != key1
    
    def test_exploration_rate(self):
        """Should sometimes return neutral weight for exploration."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(
            state,
            evaluator,
            exploration_rate=1.0,  # Always explore
        )
        
        # Train a weight
        state.update_weight("ctx", "act", reward=0.8)
        
        # Should still return 1.0 due to exploration
        weight = adjuster.get_action_weight("ctx", "act")
        assert weight == 1.0
    
    def test_statistics(self):
        """Should provide learning statistics."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator)
        
        stats = adjuster.get_statistics()
        assert "enabled" in stats
        assert "total_entries" in stats
        assert stats["enabled"] == True


class TestLearningIntegration:
    """Integration tests for learning components."""
    
    def test_end_to_end_learning_cycle(self):
        """Test complete learning cycle."""
        state = LearningState(enabled=True, max_entries=10)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(
            state,
            evaluator,
            exploration_rate=0.0,
            learning_rate=0.1,
        )
        
        context = adjuster.build_context_key(0.5, "Neutral")
        action = "response_type_a"
        
        # Initial weight is neutral
        initial_weight = adjuster.get_action_weight(context, action)
        assert initial_weight == 1.0
        
        # Simulate positive outcomes
        for _ in range(5):
            adjuster.apply_affinity_feedback(context, action, 0.2)
        
        # Weight should increase
        final_weight = adjuster.get_action_weight(context, action)
        assert final_weight > initial_weight
        
        # Simulate negative outcomes for different action
        action2 = "response_type_b"
        for _ in range(5):
            adjuster.apply_affinity_feedback(context, action2, -0.2)
        
        # Weight should decrease
        weight2 = adjuster.get_action_weight(context, action2)
        assert weight2 < 1.0
        
        # Verify bounded
        assert 0.5 <= weight2 <= 2.0
        assert 0.5 <= final_weight <= 2.0
    
    def test_learning_does_not_create_actions(self):
        """Verify learning only reweights, doesn't create actions."""
        state = LearningState(enabled=True)
        evaluator = OutcomeEvaluator()
        adjuster = PolicyAdjuster(state, evaluator)
        
        # Predefined actions
        actions = ["act1", "act2", "act3"]
        context = "ctx"
        
        # Get weights (should not create new actions)
        weights = adjuster.get_action_weights(context, actions)
        
        assert len(weights) == len(actions)
        assert set(weights.keys()) == set(actions)
        
        # All should be neutral initially
        for weight in weights.values():
            assert weight == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
