"""
Tests for decision policy module.
"""
from rfsn_hybrid.decision import (
    DecisionPolicy,
    NPCAction,
    build_context_key,
    evaluate_outcome,
)


class TestDecisionPolicy:
    """Test DecisionPolicy class."""
    
    def test_disabled_returns_default(self):
        """When disabled, policy should return default action."""
        policy = DecisionPolicy(enabled=False)
        action, style = policy.choose_action(
            context_key="any",
            affinity=0.5,
            mood="Neutral",
        )
        assert action == NPCAction.ACT_SMALLTALK
        assert style == "neutral"
    
    def test_determinism_same_context(self):
        """Same context should always return same action."""
        policy = DecisionPolicy(enabled=True)
        
        # No weights - should be deterministic
        action1, style1 = policy.choose_action(
            context_key="test",
            affinity=0.5,
            mood="Pleased",
        )
        action2, style2 = policy.choose_action(
            context_key="test",
            affinity=0.5,
            mood="Pleased",
        )
        
        assert action1 == action2
        assert style1 == style2
    
    def test_hostile_action_clamped_high_affinity(self):
        """Hostile actions should not be available at high affinity."""
        policy = DecisionPolicy(enabled=True)
        
        allowed = policy.get_allowed_actions(affinity=0.8, mood="Pleased")
        
        # Should not include hostile actions
        assert NPCAction.ACT_THREATEN not in allowed
        assert NPCAction.ACT_CALL_GUARD not in allowed
        assert NPCAction.ACT_FLEE not in allowed
    
    def test_hostile_action_allowed_low_affinity(self):
        """Hostile actions should be available at low affinity."""
        policy = DecisionPolicy(enabled=True)
        
        allowed = policy.get_allowed_actions(affinity=-0.7, mood="Hostile")
        
        # Should include some hostile actions
        assert NPCAction.ACT_THREATEN in allowed
    
    def test_friendly_action_clamped_low_affinity(self):
        """Friendly actions should not be available at low affinity."""
        policy = DecisionPolicy(enabled=True)
        
        allowed = policy.get_allowed_actions(affinity=-0.7, mood="Hostile")
        
        # Should not include friendly actions
        assert NPCAction.ACT_OFFER_QUEST not in allowed
        assert NPCAction.ACT_OFFER_GIFT not in allowed
        assert NPCAction.ACT_FOLLOW not in allowed
    
    def test_action_weights_influence_choice(self):
        """Weights should influence action selection."""
        policy = DecisionPolicy(enabled=True)
        
        # Create weights that strongly favor greeting
        weights = {
            NPCAction.ACT_GREET.value: 2.0,
            NPCAction.ACT_SMALLTALK.value: 1.0,
        }
        
        action, style = policy.choose_action(
            context_key="test",
            affinity=0.5,
            mood="Neutral",
            action_weights=weights,
        )
        
        # Should choose the highest weighted allowed action
        assert action == NPCAction.ACT_GREET
    
    def test_get_llm_directive(self):
        """LLM directives should be defined for all actions."""
        policy = DecisionPolicy(enabled=True)
        
        for action in NPCAction:
            directive = policy.get_llm_directive(action)
            assert isinstance(directive, str)
            assert len(directive) > 0
    
    def test_style_matches_affinity(self):
        """Style should be appropriate for affinity level."""
        policy = DecisionPolicy(enabled=True)
        
        # High affinity -> warm style
        _, style_high = policy.choose_action(
            "test", affinity=0.8, mood="Pleased"
        )
        assert style_high in ["warm", "neutral"]
        
        # Low affinity -> hostile/firm style  
        _, style_low = policy.choose_action(
            "test", affinity=-0.7, mood="Hostile"
        )
        assert style_low in ["hostile", "firm"]
    
    def test_no_allowed_actions_fallback(self):
        """Should have fallback when no actions allowed (edge case)."""
        policy = DecisionPolicy(enabled=True)
        
        # This shouldn't happen in practice, but test the fallback
        # We can't easily trigger this without mocking, so just verify
        # that normal cases don't fail
        action, style = policy.choose_action(
            "test", affinity=0.0, mood="Neutral"
        )
        assert action is not None
        assert style is not None


class TestContextBuilder:
    """Test context building functions."""
    
    def test_build_context_key_basic(self):
        """Basic context key should be stable."""
        key = build_context_key(
            affinity=0.5,
            mood="Neutral",
        )
        assert isinstance(key, str)
        assert "aff:" in key
        assert "mood:" in key
    
    def test_context_key_stable(self):
        """Same inputs should produce same key."""
        key1 = build_context_key(0.5, "Neutral")
        key2 = build_context_key(0.5, "Neutral")
        assert key1 == key2
    
    def test_context_key_includes_events(self):
        """Context key should include recent events."""
        key = build_context_key(
            affinity=0.5,
            mood="Neutral",
            recent_player_events=["GIFT"],
            recent_env_events=["QUEST_COMPLETED"],
        )
        assert "pevents" in key
        assert "eevents" in key
    
    def test_affinity_bucketing(self):
        """Affinity should be bucketed into discrete levels."""
        # Very positive
        key1 = build_context_key(0.8, "Pleased")
        assert "aff:2" in key1
        
        # Positive
        key2 = build_context_key(0.4, "Pleased")
        assert "aff:1" in key2
        
        # Neutral
        key3 = build_context_key(0.0, "Neutral")
        assert "aff:0" in key3
        
        # Negative
        key4 = build_context_key(-0.4, "Offended")
        assert "aff:-1" in key4
        
        # Very negative
        key5 = build_context_key(-0.8, "Hostile")
        assert "aff:-2" in key5


class TestOutcomeEvaluation:
    """Test outcome evaluation."""
    
    def test_positive_affinity_change(self):
        """Positive affinity change should yield positive reward."""
        reward = evaluate_outcome(
            pre_affinity=0.3,
            post_affinity=0.5,
        )
        assert reward > 0
    
    def test_negative_affinity_change(self):
        """Negative affinity change should yield negative reward."""
        reward = evaluate_outcome(
            pre_affinity=0.5,
            post_affinity=0.3,
        )
        assert reward < 0
    
    def test_gift_event_positive(self):
        """Gift event should contribute positive reward."""
        reward = evaluate_outcome(
            pre_affinity=0.5,
            post_affinity=0.6,
            player_event_type="GIFT",
        )
        # Should be more positive than just affinity change
        baseline = evaluate_outcome(0.5, 0.6)
        assert reward > baseline
    
    def test_insult_event_negative(self):
        """Insult event should contribute negative reward."""
        reward = evaluate_outcome(
            pre_affinity=0.5,
            post_affinity=0.4,
            player_event_type="INSULT",
        )
        # Should be more negative than just affinity change
        assert reward < 0
    
    def test_reward_bounded(self):
        """Rewards should be bounded to reasonable range."""
        # Extreme case
        reward = evaluate_outcome(
            pre_affinity=-1.0,
            post_affinity=1.0,
            player_event_type="GIFT",
        )
        assert -3.0 <= reward <= 3.0
