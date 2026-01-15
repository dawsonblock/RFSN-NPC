"""
Tests for learning namespaces (style + decision).
"""
import json
import os
import tempfile
import pytest
from rfsn_hybrid.learning.learning_state import LearningState


class TestLearningNamespaces:
    """Test dual namespace support for style and decision learning."""
    
    def test_style_namespace_isolated(self):
        """Style weights should be isolated in their namespace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create style learning state
            style_state = LearningState(
                path=path,
                enabled=True,
                namespace="style",
            )
            
            # Add style weight
            style_state.update_weight("ctx1", "warm", 0.5)
            
            # Create decision learning state (same file)
            decision_state = LearningState(
                path=path,
                enabled=True,
                namespace="decision",
            )
            
            # Add decision weight
            decision_state.update_weight("ctx1", "greet", 0.3)
            
            # Load file and verify both namespaces exist
            with open(path, "r") as f:
                data = json.load(f)
            
            assert "weights_style" in data
            assert "weights_decision" in data
            assert len(data["weights_style"]) == 1
            assert len(data["weights_decision"]) == 1
    
    def test_backward_compatibility(self):
        """Old format files should still load correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create old format file
            old_data = {
                "enabled": True,
                "max_entries": 100,
                "weights": [
                    {
                        "action": "warm",
                        "context_key": "ctx1",
                        "weight": 1.5,
                        "success_count": 5,
                        "failure_count": 1,
                        "total_count": 6,
                        "last_reward": 0.3,
                    }
                ],
            }
            
            with open(path, "w") as f:
                json.dump(old_data, f)
            
            # Load with new code
            state = LearningState(path=path, enabled=True, namespace="default")
            
            # Should load old weight
            assert state.get_weight("ctx1", "warm") == 1.5
    
    def test_namespace_does_not_overwrite_other(self):
        """Saving one namespace should not overwrite another."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create and save style weights
            style_state = LearningState(
                path=path,
                enabled=True,
                namespace="style",
            )
            style_state.update_weight("ctx1", "warm", 0.5)
            
            # Create and save decision weights
            decision_state = LearningState(
                path=path,
                enabled=True,
                namespace="decision",
            )
            decision_state.update_weight("ctx2", "greet", 0.7)
            
            # Reload style state and verify it still has its weights
            style_state2 = LearningState(
                path=path,
                enabled=True,
                namespace="style",
            )
            
            # Weight should be updated from reward using default learning_rate=0.1
            # Formula: new_weight = old_weight + learning_rate * reward
            # = 1.0 + 0.1 * 0.5 = 1.05
            assert style_state2.get_weight("ctx1", "warm") == pytest.approx(1.05, abs=0.01)
            
            # Decision weight should not be in style namespace
            assert style_state2.get_weight("ctx2", "greet") == 1.0  # Default
    
    def test_separate_namespaces_different_weights(self):
        """Same context/action in different namespaces should be independent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create style state
            style_state = LearningState(
                path=path,
                enabled=True,
                namespace="style",
            )
            style_state.update_weight("ctx1", "action1", 1.0)  # Positive reward
            
            # Create decision state
            decision_state = LearningState(
                path=path,
                enabled=True,
                namespace="decision",
            )
            decision_state.update_weight("ctx1", "action1", -0.5)  # Negative reward
            
            # Reload both and verify independence
            style_state2 = LearningState(
                path=path,
                enabled=True,
                namespace="style",
            )
            decision_state2 = LearningState(
                path=path,
                enabled=True,
                namespace="decision",
            )
            
            style_weight = style_state2.get_weight("ctx1", "action1")
            decision_weight = decision_state2.get_weight("ctx1", "action1")
            
            # Should have different weights
            assert style_weight > 1.0  # Increased
            assert decision_weight < 1.0  # Decreased


class TestDeterministicLearning:
    """Test deterministic RNG for replay stability."""
    
    def test_seeded_rng_deterministic(self):
        """Same seed should produce same exploration decisions."""
        from rfsn_hybrid.learning.policy_adjuster import PolicyAdjuster
        from rfsn_hybrid.learning.outcome_evaluator import OutcomeEvaluator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "learning.json")
            
            # Create two adjusters with same seed
            state1 = LearningState(path=path, enabled=True)
            evaluator1 = OutcomeEvaluator()
            adjuster1 = PolicyAdjuster(
                state1,
                evaluator1,
                exploration_rate=0.5,
                seed=42,
            )
            
            state2 = LearningState(path=path, enabled=True)
            evaluator2 = OutcomeEvaluator()
            adjuster2 = PolicyAdjuster(
                state2,
                evaluator2,
                exploration_rate=0.5,
                seed=42,
            )
            
            # Get weights multiple times - should be same sequence
            weights1 = [
                adjuster1.get_action_weight("ctx1", "act1")
                for _ in range(10)
            ]
            weights2 = [
                adjuster2.get_action_weight("ctx1", "act1")
                for _ in range(10)
            ]
            
            assert weights1 == weights2
    
    def test_different_seeds_different_exploration(self):
        """Different seeds should produce different exploration."""
        from rfsn_hybrid.learning.policy_adjuster import PolicyAdjuster
        from rfsn_hybrid.learning.outcome_evaluator import OutcomeEvaluator
        
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "learning1.json")
            path2 = os.path.join(tmpdir, "learning2.json")
            
            # Create two adjusters with different seeds
            state1 = LearningState(path=path1, enabled=True)
            # Add some learned weights so exploration matters
            state1.update_weight("ctx1", "act1", 0.5)
            
            evaluator1 = OutcomeEvaluator()
            adjuster1 = PolicyAdjuster(
                state1,
                evaluator1,
                exploration_rate=0.5,
                seed=42,
            )
            
            state2 = LearningState(path=path2, enabled=True)
            # Add same weights
            state2.update_weight("ctx1", "act1", 0.5)
            
            evaluator2 = OutcomeEvaluator()
            adjuster2 = PolicyAdjuster(
                state2,
                evaluator2,
                exploration_rate=0.5,
                seed=99,
            )
            
            # Get weights multiple times
            weights1 = [
                adjuster1.get_action_weight("ctx1", "act1")
                for _ in range(20)
            ]
            weights2 = [
                adjuster2.get_action_weight("ctx1", "act1")
                for _ in range(20)
            ]
            
            # Should be different (with very high probability)
            assert weights1 != weights2
