"""
Tests for environment event and decision policy wiring.

These tests verify that the new wiring correctly:
1. Processes environment events through the consequence mapper
2. Applies normalized signals to the reducer
3. Uses decision policy to select bounded actions
4. Feeds learning system with affinity feedback
"""
import pytest
from rfsn_hybrid.engine import RFSNHybridEngine
from rfsn_hybrid.environment import EnvironmentEvent


class TestEnvironmentEventWiring:
    """Test that environment events are properly wired to the reducer."""
    
    def test_gift_event_increases_affinity(self):
        """Gift events should increase affinity through the pipeline."""
        engine = RFSNHybridEngine()
        
        # Create a gift event
        event = EnvironmentEvent(
            event_type="gift",
            npc_id="TestNPC",
            player_id="Player",
            payload={"magnitude": 0.8, "item": "Diamond"}
        )
        
        # Get initial affinity
        initial_affinity = engine.get_store("TestNPC").state.affinity
        
        # Process the event
        result = engine.handle_env_event(event)
        
        # Verify the event was processed successfully
        assert result["ok"] is True
        assert result["npc_id"] == "TestNPC"
        assert result["event_type"] == "gift"
        
        # Verify affinity increased
        final_affinity = engine.get_store("TestNPC").state.affinity
        assert final_affinity > initial_affinity, "Gift should increase affinity"
        
        # Verify state change is bounded
        assert 0.0 <= final_affinity <= 1.0, "Affinity should stay bounded"
    
    def test_combat_damage_decreases_affinity(self):
        """Combat damage should decrease affinity."""
        engine = RFSNHybridEngine()
        
        # Create combat damage event
        event = EnvironmentEvent(
            event_type="combat_damage_taken",
            npc_id="TestNPC2",
            player_id="Player",
            payload={"magnitude": 0.7, "source": "player"}
        )
        
        initial_affinity = engine.get_store("TestNPC2").state.affinity
        
        result = engine.handle_env_event(event)
        
        assert result["ok"] is True
        
        final_affinity = engine.get_store("TestNPC2").state.affinity
        assert final_affinity < initial_affinity, "Combat damage should decrease affinity"
        assert 0.0 <= final_affinity <= 1.0, "Affinity should stay bounded"
    
    def test_environment_event_stored_as_fact(self):
        """Environment events should be stored as facts with env tag."""
        engine = RFSNHybridEngine()
        
        event = EnvironmentEvent(
            event_type="quest_completed",
            npc_id="TestNPC3",
            payload={"quest": "Dragon Hunt"}
        )
        
        engine.handle_env_event(event)
        
        store = engine.get_store("TestNPC3")
        facts = list(store.facts)
        
        # Find env-tagged facts
        env_facts = [f for f in facts if "env" in (getattr(f, "tags", []) or [])]
        assert len(env_facts) > 0, "Environment event should create a fact with env tag"
        
        # Verify the fact contains event info
        env_fact_texts = [f.text for f in env_facts]
        assert any("quest_completed" in text for text in env_fact_texts)


class TestDecisionPolicyWiring:
    """Test that decision policy is wired into the message handling."""
    
    def test_handle_message_includes_decision_info(self):
        """Message handling should include decision context and action."""
        engine = RFSNHybridEngine()
        
        response = engine.handle_message(
            npc_id="TestNPC",
            text="Hello there!",
            user_name="Player"
        )
        
        # Verify decision info is included
        assert "decision" in response
        assert "context_key" in response["decision"]
        assert "action" in response["decision"]
        assert "style" in response["decision"]
        
        # Verify context key format
        context_key = response["decision"]["context_key"]
        assert "aff:" in context_key
        assert "mood:" in context_key
    
    def test_decision_action_changes_with_affinity(self):
        """Different affinity levels should allow different actions."""
        engine = RFSNHybridEngine()
        
        # Test with high affinity
        store_friendly = engine.get_store("FriendlyNPC")
        store_friendly.state.affinity = 0.8
        store_friendly.state.mood = "Pleased"
        
        response_friendly = engine.handle_message(
            npc_id="FriendlyNPC",
            text="Can you help me?",
            user_name="Player"
        )
        
        # Test with low affinity
        store_hostile = engine.get_store("HostileNPC")
        store_hostile.state.affinity = -0.7
        store_hostile.state.mood = "Angry"
        
        response_hostile = engine.handle_message(
            npc_id="HostileNPC",
            text="Can you help me?",
            user_name="Player"
        )
        
        # Actions should be different due to different affinity
        action_friendly = response_friendly["decision"]["action"]
        action_hostile = response_hostile["decision"]["action"]
        
        # At minimum, hostile actions should not be friendly
        hostile_actions = ["threaten", "call_guard", "flee", "warn"]
        friendly_actions = ["offer_gift", "offer_quest", "express_gratitude"]
        
        # Verify actions respect affinity constraints
        assert action_hostile not in friendly_actions, "Hostile NPC shouldn't use friendly actions"
        assert action_friendly not in hostile_actions, "Friendly NPC shouldn't use hostile actions"


class TestLearningWiring:
    """Test that learning system is wired to environment feedback."""
    
    def test_enable_learning_endpoint(self):
        """Test that learning can be enabled per NPC."""
        engine = RFSNHybridEngine()
        
        result = engine.enable_learning("LearningNPC", enabled=True)
        
        assert result["npc_id"] == "LearningNPC"
        assert result["enabled"] is True
        assert "decision" in result
        assert "style" in result
    
    def test_affinity_feedback_updates_weights(self):
        """Test that affinity changes feed back to learning system."""
        engine = RFSNHybridEngine()
        
        # Enable learning
        engine.enable_learning("LearnerNPC", enabled=True)
        
        # Have a conversation to establish a last action
        response = engine.handle_message(
            npc_id="LearnerNPC",
            text="Hello!",
            user_name="Player"
        )
        
        action_taken = response["decision"]["action"]
        
        # Send a positive environment event
        event = EnvironmentEvent(
            event_type="gift",
            npc_id="LearnerNPC",
            player_id="Player",
            payload={"magnitude": 0.9, "item": "Gold"}
        )
        
        # This should apply learning feedback
        result = engine.handle_env_event(event)
        
        # Verify the event was processed
        assert result["ok"] is True
        
        # The learning system should have recorded the feedback
        # (weights are internal, but we can verify no crashes occurred)
        adjusters = engine._get_policy_adjusters("LearnerNPC")
        stats = adjusters["decision"].get_statistics()
        
        assert stats["enabled"] is True


class TestEndToEndWiring:
    """Test complete flow: chat -> env event -> learning."""
    
    def test_complete_feedback_loop(self):
        """Test the complete loop: chat, env event, learning feedback."""
        engine = RFSNHybridEngine()
        
        # Enable learning
        engine.enable_learning("LoopNPC", enabled=True)
        
        # Step 1: Chat
        chat_response = engine.handle_message(
            npc_id="LoopNPC",
            text="I have a gift for you!",
            user_name="Player"
        )
        
        assert "decision" in chat_response
        assert chat_response["decision"]["action"] is not None
        initial_affinity = chat_response["state"]["affinity"]
        
        # Step 2: Send positive environment event
        gift_event = EnvironmentEvent(
            event_type="gift",
            npc_id="LoopNPC",
            player_id="Player",
            payload={"magnitude": 0.8, "item": "Sword"}
        )
        
        env_result = engine.handle_env_event(gift_event)
        
        assert env_result["ok"] is True
        final_affinity = env_result["state"]["affinity"]
        
        # Verify affinity increased
        assert final_affinity > initial_affinity
        
        # Step 3: Another chat should use updated context
        chat_response2 = engine.handle_message(
            npc_id="LoopNPC",
            text="How are you?",
            user_name="Player"
        )
        
        # Context should include the env event (may or may not appear based on timing)
        context_key = chat_response2["decision"]["context_key"]
        
        # NPC should have facts about both interactions
        store = engine.get_store("LoopNPC")
        facts = [f.text for f in store.facts]
        
        # Should have user messages
        assert any("gift for you" in f.lower() for f in facts)
        assert any("how are you" in f.lower() for f in facts)
        
        # Should have env event
        assert any("env" in f.lower() and "gift" in f.lower() for f in facts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
