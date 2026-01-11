"""
Integration tests for the RFSN Hybrid Engine.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from rfsn_hybrid.types import RFSNState, Event
from rfsn_hybrid.state_machine import parse_event, transition
from rfsn_hybrid.storage import ConversationMemory, FactsStore, select_facts, Turn
from rfsn_hybrid.prompting import render_llama3, render_phi3_chatml


class TestConversationFlow:
    """Test full conversation flow with state transitions."""
    
    def test_gift_increases_affinity_and_updates_facts(self):
        state = RFSNState(
            npc_name="Lydia", role="Housecarl", affinity=0.5,
            mood="Neutral", player_name="Dragonborn", player_playstyle="Combatant",
        )
        event = parse_event("gift")
        new_state, facts = transition(state, event)
        
        assert new_state.affinity > state.affinity
        assert new_state.mood == "Pleased"
        assert len(facts) == 1
    
    def test_insult_chain_leads_to_hostility(self):
        state = RFSNState(
            npc_name="Lydia", role="Housecarl", affinity=0.0,
            mood="Neutral", player_name="Dragonborn", player_playstyle="Combatant",
        )
        for _ in range(5):
            event = parse_event("You're pathetic")
            state, _ = transition(state, event)
        
        assert state.affinity < -0.5
    
    def test_conversation_history_accumulates(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "convo.json")
            memory = ConversationMemory(path)
            
            memory.add("user", "Hello there")
            memory.add("assistant", "Greetings, my Thane")
            
            assert len(memory.turns) == 2
            
            memory2 = ConversationMemory(path)
            assert len(memory2.turns) == 2


class TestPersistence:
    """Test persistence and state recovery."""
    
    def test_state_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            
            original = RFSNState(
                npc_name="Lydia", role="Housecarl", affinity=0.75,
                mood="Happy", player_name="Hero", player_playstyle="Mage",
                recent_memory="Fought dragons together",
            )
            original.save(path)
            
            loaded = RFSNState.load(path)
            
            assert loaded is not None
            assert loaded.affinity == 0.75
            assert loaded.mood == "Happy"
    
    def test_facts_survive_restart(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            
            store = FactsStore(path)
            store.add_fact("Player is the Dragonborn", ["identity"], 1.0)
            
            store2 = FactsStore(path)
            
            assert len(store2.facts) == 1


class TestIntentClassification:
    """Test intent classification with keyword-based parser."""
    
    def test_praise_detection(self):
        event = parse_event("Thanks for your help!")
        assert event.type == "PRAISE"
    
    def test_threat_detection(self):
        event = parse_event("I will end you if you betray me")
        assert event.type == "THREATEN"
    
    def test_theft_detection(self):
        event = parse_event("I stole from the merchant")
        assert event.type == "THEFT"
    
    def test_help_detection(self):
        event = parse_event("Can you help me with this quest?")
        assert event.type == "HELP"
    
    def test_default_is_talk(self):
        event = parse_event("The weather is nice today")
        assert event.type == "TALK"


class TestPromptRendering:
    """Test prompt rendering for different templates."""
    
    def test_llama3_template_has_system_header(self):
        history = [Turn(role="user", content="Hello", time="t")]
        prompt = render_llama3("System prompt", history, "New message")
        
        assert "system" in prompt.lower()
        assert "System prompt" in prompt
        assert "New message" in prompt
    
    def test_phi3_template_has_system_tag(self):
        history = [Turn(role="user", content="Hello", time="t")]
        prompt = render_phi3_chatml("System prompt", history, "New message")
        
        assert "system" in prompt.lower()
        assert "System prompt" in prompt


class TestEngineIntegration:
    """Test engine functionality without loading real models."""
    
    def test_system_prompt_includes_state(self):
        """The system prompt should include NPC state information."""
        # Import the class but don't instantiate (avoid loading model)
        from rfsn_hybrid.engine import RFSNHybridEngine
        
        state = RFSNState(
            npc_name="Lydia", role="Housecarl", affinity=0.75,
            mood="Happy", player_name="Hero", player_playstyle="Combatant",
        )
        
        # Create a minimal engine instance without loading model
        engine = object.__new__(RFSNHybridEngine)
        engine.template = "llama3"
        engine.model_path = "test.gguf"
        
        system_text = engine.build_system_text(state, ["A test fact"])
        
        assert "Lydia" in system_text
        assert "Housecarl" in system_text
        assert "Happy" in system_text
        assert "A test fact" in system_text
    
    def test_fact_retrieval_method(self):
        """Test the _retrieve_facts method."""
        from rfsn_hybrid.engine import RFSNHybridEngine
        
        with tempfile.TemporaryDirectory() as d:
            facts_path = os.path.join(d, "facts.json")
            facts = FactsStore(facts_path)
            facts.add_fact("Player saved the village", ["quest"], 0.9)
            facts.add_fact("Player gave NPC a sword", ["gift"], 0.8)
            
            # Create minimal engine
            engine = object.__new__(RFSNHybridEngine)
            
            retrieved = engine._retrieve_facts(
                user_text="Thanks for before",
                facts=facts,
                semantic_facts=None,
                fact_tags=["quest"],
                k=1,
            )
            
            assert len(retrieved) == 1
            assert "village" in retrieved[0].lower()
