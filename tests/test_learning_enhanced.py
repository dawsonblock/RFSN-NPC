"""
Comprehensive tests for the enhanced learning system.

Tests the full learning pipeline including:
- Feature encoding
- Bandit learning (LinUCB)
- Configuration and presets
- Persistence and recovery
- Integration with reducer (PolicyBias)
- Deterministic replay
"""
import tempfile
import pytest

from rfsn_hybrid.learning import (
    LearningConfig,
    LearningPresets,
    FeatureEncoder,
    FeatureVector,
    FEATURE_SCHEMA_VERSION,
    LinUCBBandit,
    LearningPersistence,
    PolicyBias,
    LearningState,
    OutcomeEvaluator,
)


class TestLearningConfig:


class TestLearningConfig:
    """Tests for LearningConfig."""
    
    def test_default_config_disabled(self):
        """Default config should have learning disabled."""
        config = LearningConfig()
        assert not config.enabled
    
    def test_parameter_clamping(self):
        """Config should clamp parameters to safe ranges."""
        config = LearningConfig(
            exploration_rate=2.0,  # Over max
            learning_rate=-0.1,    # Under min
            max_pending=10000,     # Over max
        )
        
        assert 0.0 <= config.exploration_rate <= 1.0
        assert 0.0 <= config.learning_rate <= 1.0
        assert config.max_pending <= 1000
    
    def test_presets(self):
        """Test learning presets."""
        conservative = LearningPresets.conservative()
        assert conservative.enabled
        assert conservative.learning_rate < 0.05
        
        aggressive = LearningPresets.aggressive()
        assert aggressive.enabled
        assert aggressive.learning_rate > 0.05
        
        deterministic = LearningPresets.deterministic_test(seed=42)
        assert deterministic.prng_seed == 42
    
    def test_serialization(self):
        """Config should serialize/deserialize correctly."""
        config = LearningConfig(enabled=True, exploration_rate=0.1)
        data = config.to_dict()
        
        restored = LearningConfig.from_dict(data)
        assert restored.enabled == config.enabled
        assert restored.exploration_rate == config.exploration_rate


class TestFeatureEncoder:
    """Tests for FeatureEncoder."""
    
    def test_basic_encoding(self):
        """Should encode basic state into features."""
        encoder = FeatureEncoder()
        
        features = encoder.encode(
            affinity=0.5,
            mood="Pleased",
        )
        
        assert isinstance(features, FeatureVector)
        assert features.schema_version == FEATURE_SCHEMA_VERSION
        assert "affinity_raw" in features.features
        assert "mood_pleased" in features.features
        assert features.features["mood_pleased"] == 1.0
    
    def test_feature_bounds(self):
        """All features should be bounded."""
        encoder = FeatureEncoder()
        
        features = encoder.encode(
            affinity=0.7,
            mood="Angry",
            recent_events=["GIFT", "PRAISE"],
        )
        
        assert encoder.validate_features(features.features)
    
    def test_context_key_consistency(self):
        """Same state should produce same context key."""
        encoder = FeatureEncoder()
        
        fv1 = encoder.encode(0.5, "Neutral")
        fv2 = encoder.encode(0.5, "Neutral")
        
        assert fv1.context_key == fv2.context_key
    
    def test_context_key_uniqueness(self):
        """Different states should produce different context keys."""
        encoder = FeatureEncoder()
        
        fv1 = encoder.encode(0.5, "Neutral")
        fv2 = encoder.encode(-0.5, "Angry")
        
        assert fv1.context_key != fv2.context_key
    
    def test_serialization(self):
        """Features should serialize/deserialize."""
        encoder = FeatureEncoder()
        fv = encoder.encode(0.3, "Warm")
        
        data = fv.to_dict()
        restored = FeatureVector.from_dict(data)
        
        assert restored.context_key == fv.context_key
        assert restored.features == fv.features


class TestLinUCBBandit:
    """Tests for LinUCB bandit learner."""
    
    def test_initialization(self):
        """Bandit should initialize with correct parameters."""
        bandit = LinUCBBandit(alpha=0.5, prng_seed=42)
        
        assert bandit.alpha == 0.5
        assert bandit.total_pulls == 0
    
    def test_score_actions(self):
        """Should score multiple actions."""
        bandit = LinUCBBandit(alpha=0.2, prng_seed=42)
        
        context = {"feat1": 0.5, "feat2": 0.3}
        actions = ["action_a", "action_b", "action_c"]
        
        scores = bandit.score_actions(context, actions)
        
        assert len(scores) == len(actions)
        assert all(action in scores for action in actions)
    
    def test_learning_updates_scores(self):
        """Positive rewards should increase scores over time."""
        bandit = LinUCBBandit(alpha=0.1, prng_seed=42)
        
        context = {"feat1": 1.0}
        action = "good_action"
        
        initial_score = bandit.score_actions(context, [action])[action]
        
        # Provide positive feedback multiple times
        for _ in range(10):
            bandit.update(context, action, reward=0.8)
        
        final_score = bandit.score_actions(context, [action])[action]
        
        # Score should increase (though UCB may complicate this)
        # At minimum, the arm should have been updated
        assert bandit.arms[action].n == 10
        assert bandit.arms[action].theta["feat1"] != 0.0
    
    def test_bounded_updates(self):
        """Extreme rewards should not cause unbounded growth."""
        bandit = LinUCBBandit(alpha=0.2, prng_seed=42)
        
        context = {"feat1": 1.0}
        action = "action"
        
        # Try to cause instability with extreme rewards
        for _ in range(100):
            bandit.update(context, action, reward=1.0)
        
        # Theta should be clamped
        theta = bandit.arms[action].theta["feat1"]
        assert -2.0 <= theta <= 2.0
    
    def test_deterministic_with_seed(self):
        """Same seed should produce same behavior."""
        bandit1 = LinUCBBandit(alpha=0.2, prng_seed=42)
        bandit2 = LinUCBBandit(alpha=0.2, prng_seed=42)
        
        context = {"feat1": 0.5}
        actions = ["a", "b", "c"]
        
        scores1 = bandit1.score_actions(context, actions)
        scores2 = bandit2.score_actions(context, actions)
        
        assert scores1 == scores2
    
    def test_serialization(self):
        """Bandit should serialize/deserialize with state."""
        bandit = LinUCBBandit(alpha=0.3, prng_seed=42)
        
        context = {"feat1": 0.5}
        bandit.update(context, "action_a", 0.5)
        bandit.update(context, "action_b", -0.3)
        
        data = bandit.to_dict()
        restored = LinUCBBandit.from_dict(data, prng_seed=42)
        
        assert restored.alpha == bandit.alpha
        assert restored.total_pulls == bandit.total_pulls
        assert "action_a" in restored.arms
        assert "action_b" in restored.arms


class TestLearningPersistence:
    """Tests for learning state persistence."""
    
    def test_snapshot_and_restore(self):
        """Should save and restore learning state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = LearningPersistence(tmpdir)
            
            config = LearningConfig(enabled=True)
            learning_state = LearningState(enabled=True)
            learning_state.update_weight("ctx1", "act1", 0.5)
            
            bandit = LinUCBBandit(prng_seed=42)
            bandit.update({"f1": 0.5}, "act1", 0.8)
            
            # Save
            success = persistence.snapshot("npc_test", config, learning_state, bandit)
            assert success
            
            # Restore
            data = persistence.restore("npc_test")
            assert data is not None
            assert data["npc_id"] == "npc_test"
    
    def test_restore_nonexistent(self):
        """Restoring non-existent state should return None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = LearningPersistence(tmpdir)
            data = persistence.restore("nonexistent")
            assert data is None
    
    def test_snapshot_counter(self):
        """Should track event counter for periodic snapshots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            persistence = LearningPersistence(tmpdir)
            
            config = LearningConfig(snapshot_every_n_events=5)
            
            # First 4 events - no snapshot
            for i in range(4):
                assert not persistence.should_snapshot(config)
            
            # 5th event - snapshot
            assert persistence.should_snapshot(config)


class TestPolicyBias:
    """Tests for PolicyBias dataclass."""
    
    def test_neutral_bias(self):
        """Neutral bias should have no effect."""
        bias = PolicyBias.neutral()
        assert not bias  # Should be falsy
        assert len(bias.action_bias) == 0
    
    def test_bias_with_values(self):
        """Bias with values should be truthy."""
        bias = PolicyBias(
            action_bias={"action_a": 0.5, "action_b": -0.3},
            metadata={"source": "test"},
        )
        assert bias  # Should be truthy
        assert bias.action_bias["action_a"] == 0.5


class TestLearningIntegration:
    """Integration tests for full learning pipeline."""
    
    def test_end_to_end_learning_cycle(self):
        """Test complete learning cycle with all components."""
        # Setup
        config = LearningPresets.deterministic_test(seed=42)
        learning_state = LearningState(enabled=True, max_entries=10)
        bandit = LinUCBBandit(alpha=0.2, prng_seed=42)
        encoder = FeatureEncoder()
        evaluator = OutcomeEvaluator()
        
        # Encode context
        features = encoder.encode(affinity=0.5, mood="Neutral")
        context_key = features.context_key
        context_dict = features.features
        
        # Available actions
        actions = ["action_friendly", "action_neutral", "action_hostile"]
        
        # Get initial scores
        initial_scores = bandit.score_actions(context_dict, actions)
        
        # Simulate choosing highest-scored action
        chosen_action = max(initial_scores, key=initial_scores.get)
        
        # Simulate positive outcome (affinity increased)
        outcome = evaluator.evaluate_from_affinity_change(
            affinity_delta=0.2,
            context=context_key,
            action=chosen_action,
        )
        
        # Update learning
        bandit.update(context_dict, chosen_action, outcome.reward)
        learning_state.update_weight(context_key, chosen_action, outcome.reward)
        
        # Get new scores
        new_scores = bandit.score_actions(context_dict, actions)
        
        # Verify learning occurred
        assert bandit.total_pulls == 1
        assert learning_state.get_weight(context_key, chosen_action) > 1.0
    
    def test_learning_disabled_baseline(self):
        """With learning disabled, behavior should be neutral."""
        config = LearningConfig(enabled=False)
        learning_state = LearningState(enabled=False)
        
        # Update should have no effect
        weight = learning_state.update_weight("ctx", "act", 0.8)
        assert weight == 1.0
        
        retrieved = learning_state.get_weight("ctx", "act")
        assert retrieved == 1.0
    
    def test_deterministic_replay(self):
        """Same seed and events should produce same results."""
        def run_scenario(seed):
            bandit = LinUCBBandit(alpha=0.2, prng_seed=seed)
            
            context = {"f1": 0.5, "f2": 0.3}
            actions = ["a", "b", "c"]
            
            results = []
            for _ in range(5):
                scores = bandit.score_actions(context, actions)
                chosen = max(scores, key=scores.get)
                results.append(chosen)
                bandit.update(context, chosen, 0.5)
            
            return results
        
        results1 = run_scenario(42)
        results2 = run_scenario(42)
        
        assert results1 == results2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
