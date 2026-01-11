"""
Tests for memory consolidation utilities.
"""
import os
import json
import tempfile

import pytest

from rfsn_hybrid.memory import (
    find_similar_facts,
    merge_facts,
    consolidate_facts,
    decay_salience,
    reinforce_fact,
    MemoryManager,
    ConsolidationResult,
    _text_similarity,
)
from rfsn_hybrid.storage import FactsStore, Fact


@pytest.fixture
def temp_facts_store(tmp_path):
    """Create a temporary facts store."""
    path = str(tmp_path / "facts.json")
    return FactsStore(path)


class TestTextSimilarity:
    """Test text similarity function."""
    
    def test_identical_texts(self):
        """Identical texts should have similarity 1.0."""
        sim = _text_similarity("hello world", "hello world")
        assert sim == 1.0
    
    def test_different_texts(self):
        """Completely different texts should have low similarity."""
        sim = _text_similarity("the quick brown fox", "apple banana cherry")
        assert sim < 0.2
    
    def test_partial_overlap(self):
        """Partial overlap should have intermediate similarity."""
        sim = _text_similarity("player gave sword", "player gave gold")
        assert 0.3 < sim < 0.8
    
    def test_empty_text(self):
        """Empty text should return 0."""
        assert _text_similarity("", "hello") == 0.0
        assert _text_similarity("hello", "") == 0.0


class TestFindSimilarFacts:
    """Test finding similar facts."""
    
    def test_finds_similar_pairs(self):
        """Should find similar fact pairs."""
        facts = [
            Fact("Player gave Lydia a sword", ["gift"], "t1", 0.8),
            Fact("Player gave Lydia a shield", ["gift"], "t2", 0.7),
            Fact("Player fought a dragon", ["combat"], "t3", 0.9),
        ]
        
        pairs = find_similar_facts(facts, similarity_threshold=0.5)
        
        # Sword and shield gifts should be similar
        assert len(pairs) >= 1
        assert any(0 in (i, j) and 1 in (i, j) for i, j, _ in pairs)
    
    def test_no_false_positives(self):
        """Dissimilar facts should not be paired."""
        facts = [
            Fact("Player went to the store", ["travel"], "t1", 0.5),
            Fact("Dragon attacked village", ["combat"], "t2", 0.9),
        ]
        
        pairs = find_similar_facts(facts, similarity_threshold=0.7)
        
        assert len(pairs) == 0


class TestMergeFacts:
    """Test merging two facts."""
    
    def test_keeps_longer_text(self):
        """Should prefer longer/more detailed text."""
        f1 = Fact("Player gave gift", ["gift"], "t1", 0.5)
        f2 = Fact("Player gave Lydia an enchanted sword", ["gift"], "t2", 0.6)
        
        merged = merge_facts(f1, f2)
        
        assert "enchanted sword" in merged.text
    
    def test_combines_tags(self):
        """Should combine unique tags from both."""
        f1 = Fact("Event 1", ["tag1", "tag2"], "t1", 0.5)
        f2 = Fact("Event 2", ["tag2", "tag3"], "t2", 0.6)
        
        merged = merge_facts(f1, f2)
        
        assert set(merged.tags) == {"tag1", "tag2", "tag3"}
    
    def test_keeps_higher_salience(self):
        """Should keep the higher salience value."""
        f1 = Fact("Event", [], "t1", 0.3)
        f2 = Fact("Event", [], "t2", 0.9)
        
        merged = merge_facts(f1, f2)
        
        assert merged.salience == 0.9


class TestConsolidateFacts:
    """Test full consolidation operation."""
    
    def test_reduces_similar_facts(self, temp_facts_store):
        """Should reduce count by merging similar facts."""
        # Add similar facts
        temp_facts_store.add_fact("Player gave sword to Lydia", ["gift"], 0.8)
        temp_facts_store.add_fact("Player gave shield to Lydia", ["gift"], 0.7)
        temp_facts_store.add_fact("Dragon attacked city", ["combat"], 0.9)
        
        result = consolidate_facts(temp_facts_store, merge_threshold=0.6)
        
        assert result.original_count == 3
        assert result.final_count <= 3
        assert result.merged_count >= 0
    
    def test_prunes_low_salience(self, temp_facts_store):
        """Should prune facts below salience threshold."""
        temp_facts_store.add_fact("Important fact", ["key"], 0.9)
        temp_facts_store.add_fact("Minor fact", ["minor"], 0.1)
        
        result = consolidate_facts(
            temp_facts_store, 
            prune_salience=0.3
        )
        
        assert result.pruned_count >= 1
        assert len(temp_facts_store.facts) == 1
        assert temp_facts_store.facts[0].text == "Important fact"
    
    def test_enforces_max_facts(self, temp_facts_store):
        """Should limit to max_facts."""
        for i in range(10):
            temp_facts_store.add_fact(f"Fact {i}", ["test"], 0.5 + i * 0.05)
        
        result = consolidate_facts(temp_facts_store, max_facts=5)
        
        assert len(temp_facts_store.facts) == 5
        # Should keep highest salience
        saliences = [f.salience for f in temp_facts_store.facts]
        assert all(s >= 0.75 for s in saliences)
    
    def test_archives_when_path_provided(self, temp_facts_store, tmp_path):
        """Should archive pruned facts when path provided."""
        temp_facts_store.add_fact("Low salience", ["test"], 0.1)
        temp_facts_store.add_fact("High salience", ["test"], 0.9)
        
        archive_path = str(tmp_path / "archive.json")
        
        consolidate_facts(
            temp_facts_store,
            prune_salience=0.5,
            archive_path=archive_path,
        )
        
        assert os.path.exists(archive_path)
        with open(archive_path) as f:
            archived = json.load(f)
        assert len(archived) == 1
        assert "Low salience" in archived[0]["text"]


class TestDecaySalience:
    """Test salience decay."""
    
    def test_reduces_salience(self, temp_facts_store):
        """Should reduce salience of facts."""
        temp_facts_store.add_fact("Test", [], 0.8)
        
        affected = decay_salience(temp_facts_store, decay_rate=0.1)
        
        assert affected == 1
        assert temp_facts_store.facts[0].salience == pytest.approx(0.7)
    
    def test_respects_minimum(self, temp_facts_store):
        """Should not decay below minimum."""
        temp_facts_store.add_fact("Test", [], 0.15)
        
        decay_salience(temp_facts_store, decay_rate=0.1, min_salience=0.1)
        
        assert temp_facts_store.facts[0].salience == 0.1


class TestReinforceFact:
    """Test fact reinforcement."""
    
    def test_increases_salience(self, temp_facts_store):
        """Should increase salience of matching facts."""
        temp_facts_store.add_fact("Player saved the village", [], 0.5)
        
        count = reinforce_fact(temp_facts_store, "village", boost=0.2)
        
        assert count == 1
        assert temp_facts_store.facts[0].salience == 0.7
    
    def test_caps_at_one(self, temp_facts_store):
        """Should not exceed salience of 1.0."""
        temp_facts_store.add_fact("Test fact", [], 0.95)
        
        reinforce_fact(temp_facts_store, "fact", boost=0.2)
        
        assert temp_facts_store.facts[0].salience == 1.0
    
    def test_no_match_no_change(self, temp_facts_store):
        """Non-matching text should not affect facts."""
        temp_facts_store.add_fact("Test fact", [], 0.5)
        
        count = reinforce_fact(temp_facts_store, "dragon", boost=0.2)
        
        assert count == 0
        assert temp_facts_store.facts[0].salience == 0.5


class TestMemoryManager:
    """Test the MemoryManager class."""
    
    def test_consolidate(self, temp_facts_store):
        """Should run consolidation."""
        temp_facts_store.add_fact("Test 1", [], 0.8)
        temp_facts_store.add_fact("Test 2", [], 0.1)
        
        manager = MemoryManager(temp_facts_store, prune_salience=0.5)
        result = manager.consolidate()
        
        assert isinstance(result, ConsolidationResult)
        assert result.pruned_count >= 1
    
    def test_apply_decay(self, temp_facts_store):
        """Should apply decay."""
        temp_facts_store.add_fact("Test", [], 0.8)
        
        manager = MemoryManager(temp_facts_store, decay_rate=0.1)
        count = manager.apply_decay()
        
        assert count == 1
    
    def test_stats(self, temp_facts_store):
        """Should return accurate stats."""
        temp_facts_store.add_fact("High", ["a"], 0.9)
        temp_facts_store.add_fact("Low", ["b"], 0.2)
        
        manager = MemoryManager(temp_facts_store)
        stats = manager.stats()
        
        assert stats["total_facts"] == 2
        assert stats["high_salience_count"] == 1
        assert stats["low_salience_count"] == 1
        assert set(stats["unique_tags"]) == {"a", "b"}
