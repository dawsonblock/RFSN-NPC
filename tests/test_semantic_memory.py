"""
Tests for the semantic memory module.

These tests require the semantic extras to be installed:
    pip install ".[semantic]"

Tests are skipped if dependencies are not available.
"""
import os
import tempfile
import pytest

# Check if semantic dependencies are available
try:
    from rfsn_hybrid.semantic_memory import (
        is_semantic_available, 
        SemanticFactStore,
        try_get_semantic_store,
    )
    SEMANTIC_AVAILABLE = is_semantic_available()
except ImportError:
    SEMANTIC_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not SEMANTIC_AVAILABLE, 
    reason="Semantic dependencies not installed (pip install .[semantic])"
)


class TestSemanticFactStore:
    """Test the SemanticFactStore class."""
    
    def test_add_and_search(self):
        """Adding facts should make them searchable."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = SemanticFactStore(path)
            
            store.add_fact("Player gave Lydia a sword", ["gift"], 0.9)
            store.add_fact("Player punched a guard", ["violence"], 0.7)
            
            assert len(store) == 2
            
            # Search should find relevant facts
            results = store.search("weapons and gifts", k=2)
            assert len(results) > 0
            
            # First result should mention the sword (gift)
            texts = [text for text, _ in results]
            assert any("sword" in t.lower() for t in texts)
    
    def test_persistence(self):
        """Facts and embeddings should persist to disk."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            
            # Create and populate store
            store1 = SemanticFactStore(path)
            store1.add_fact("Test fact for persistence", ["test"], 0.8)
            
            # Reload from disk
            store2 = SemanticFactStore(path)
            
            assert len(store2) == 1
            assert store2.facts[0].text == "Test fact for persistence"
            assert store2.facts[0].embedding is not None
    
    def test_hybrid_search_combines_semantic_and_tags(self):
        """Hybrid search should blend semantic and tag matching."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = SemanticFactStore(path)
            
            # Add facts with different tags
            store.add_fact("Player went to the market", ["travel"], 0.5)
            store.add_fact("Player bought armor at shop", ["purchase"], 0.6)
            store.add_fact("Player gave Lydia gold coins", ["gift"], 0.9)
            store.add_fact("Player gave flowers to the innkeeper", ["gift"], 0.7)
            
            # Hybrid search with gift tag should prefer gift facts
            results = store.hybrid_search(
                query="Something about the market",
                want_tags=["gift"],
                k=2,
                semantic_weight=0.4,  # Give tags more weight
            )
            
            # Should return gift-tagged facts even though query is about market
            assert len(results) == 2
            assert any("gold" in r.lower() or "flowers" in r.lower() for r in results)
    
    def test_search_texts_returns_just_strings(self):
        """search_texts should return just the fact text, no scores."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = SemanticFactStore(path)
            
            store.add_fact("A simple test fact", ["test"], 0.5)
            
            results = store.search_texts("test", k=1)
            
            assert len(results) == 1
            assert isinstance(results[0], str)
            assert "simple test" in results[0]
    
    def test_wipe_clears_all_data(self):
        """wipe() should clear all facts and remove file."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = SemanticFactStore(path)
            
            store.add_fact("Will be wiped", ["test"], 0.5)
            assert len(store) == 1
            assert os.path.exists(path)
            
            store.wipe()
            
            assert len(store) == 0
            assert not os.path.exists(path)
    
    def test_min_similarity_threshold(self):
        """Search should respect min_similarity threshold."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = SemanticFactStore(path)
            
            store.add_fact("The sky is blue", ["nature"], 0.5)
            store.add_fact("Water is wet", ["nature"], 0.5)
            
            # Very high threshold should return nothing for unrelated query
            results = store.search(
                "Computer programming languages",
                k=10,
                min_similarity=0.9,
            )
            
            # Should return empty or very few results
            assert len(results) <= 1


class TestTryGetSemanticStore:
    """Test the convenience function for safe initialization."""
    
    def test_returns_store_when_available(self):
        """Should return a store when dependencies are installed."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "facts.json")
            store = try_get_semantic_store(path)
            
            assert store is not None
            assert isinstance(store, SemanticFactStore)
    
    def test_handles_invalid_path_gracefully(self):
        """Should handle errors gracefully."""
        # This shouldn't crash
        store = try_get_semantic_store("/nonexistent/path/that/should/work.json")
        # If directory doesn't exist, it will be created on first save
        assert store is not None
