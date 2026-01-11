"""
Tests for the intent classifier module.

These tests verify both keyword-based fallback and LLM-based classification.
"""
import pytest
from unittest.mock import MagicMock, patch

from rfsn_hybrid.intent_classifier import (
    classify_intent,
    classify_intent_with_llm,
    IntentClassifier,
    EVENT_CONFIG,
    VALID_INTENTS,
)
from rfsn_hybrid.types import Event


class MockLlama:
    """Mock LLM for testing intent classification."""
    
    def __init__(self, response: str = "PRAISE"):
        self.response = response
        self.call_count = 0
    
    def __call__(self, prompt: str, **kwargs):
        self.call_count += 1
        return {"choices": [{"text": f" {self.response}"}]}


class TestClassifyIntentWithLlm:
    """Test LLM-based intent classification."""
    
    def test_returns_valid_intent(self):
        """LLM returning valid intent should be recognized."""
        llm = MockLlama("PRAISE")
        result = classify_intent_with_llm(llm, "Thank you so much!")
        
        assert result == "PRAISE"
        assert llm.call_count == 1
    
    def test_extracts_intent_from_verbose_response(self):
        """Should extract intent even from verbose LLM response."""
        llm = MockLlama("The category is GIFT because the player is giving something")
        result = classify_intent_with_llm(llm, "Here take this")
        
        assert result == "GIFT"
    
    def test_returns_none_for_invalid_response(self):
        """Unrecognized response should return None."""
        llm = MockLlama("I don't understand")
        result = classify_intent_with_llm(llm, "something")
        
        assert result is None
    
    def test_handles_llm_exception(self):
        """LLM errors should be handled gracefully."""
        llm = MagicMock(side_effect=Exception("LLM error"))
        result = classify_intent_with_llm(llm, "test")
        
        assert result is None


class TestClassifyIntent:
    """Test the main classify_intent function."""
    
    def test_uses_llm_when_available(self):
        """Should use LLM classification when enabled."""
        llm = MockLlama("GIFT")
        event = classify_intent("Here take this gold", llm=llm, use_llm=True)
        
        assert event.type == "GIFT"
        assert llm.call_count == 1
    
    def test_falls_back_to_keyword_when_llm_fails(self):
        """Should fall back to keyword parsing if LLM returns None."""
        llm = MockLlama("UNKNOWN_INTENT")
        event = classify_intent("I stole the gold", llm=llm, use_llm=True)
        
        # LLM returns invalid intent, should fall back to keyword
        # "stole" triggers THEFT in keyword parser
        assert event.type == "THEFT"
    
    def test_keyword_only_when_llm_disabled(self):
        """Should skip LLM when use_llm=False."""
        llm = MockLlama("GIFT")
        event = classify_intent("Thanks for everything", llm=llm, use_llm=False)
        
        # Should use keyword parsing, not LLM
        assert llm.call_count == 0
        assert event.type == "PRAISE"  # "thanks" triggers PRAISE
    
    def test_keyword_only_when_no_llm(self):
        """Should use keyword parsing when llm is None."""
        event = classify_intent("I'm going to kill you", llm=None, use_llm=True)
        
        # "kill" triggers THREATEN in keyword parser
        assert event.type == "THREATEN"


class TestIntentClassifier:
    """Test the IntentClassifier class."""
    
    def test_tracks_classification_count(self):
        """Should track total classifications."""
        llm = MockLlama("PRAISE")
        classifier = IntentClassifier(llm=llm, use_llm=True)
        
        classifier.classify("Thanks")
        classifier.classify("Thanks again")
        classifier.classify("More thanks")
        
        assert classifier.stats["total"] == 3
    
    def test_tracks_llm_success_rate(self):
        """Should track LLM success rate accurately."""
        # LLM returns valid intent half the time
        llm = MockLlama("PRAISE")
        classifier = IntentClassifier(llm=llm, use_llm=True)
        
        classifier.classify("Test 1")
        classifier.classify("Test 2")
        
        stats = classifier.stats
        assert stats["total"] == 2
        assert stats["llm_successes"] == 2
        assert stats["llm_rate"] == 1.0
    
    def test_works_without_llm(self):
        """Should work with keyword-only mode."""
        classifier = IntentClassifier(llm=None, use_llm=False)
        
        event = classifier.classify("You stupid fool!")
        
        # "stupid" triggers INSULT
        assert event.type == "INSULT"
        assert classifier.stats["llm_successes"] == 0


class TestEventConfig:
    """Test event configuration consistency."""
    
    def test_all_valid_intents_have_config(self):
        """Every valid intent should have a config entry."""
        for intent in VALID_INTENTS:
            assert intent in EVENT_CONFIG
            assert "strength" in EVENT_CONFIG[intent]
            assert "tags" in EVENT_CONFIG[intent]
    
    def test_config_values_are_valid(self):
        """Config values should be in valid ranges."""
        for intent, config in EVENT_CONFIG.items():
            assert 0.0 <= config["strength"] <= 2.0
            assert isinstance(config["tags"], list)
            assert all(isinstance(t, str) for t in config["tags"])
