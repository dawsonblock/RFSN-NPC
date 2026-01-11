"""
Memory consolidation utilities for managing long-term fact storage.

As conversations grow, the number of facts can become unwieldy.
This module provides utilities to:
- Merge similar facts
- Summarize old conversations
- Prune low-salience facts
- Archive old data
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

from .storage import FactsStore, Fact
from .types import RFSNState

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    """Results from a consolidation operation."""
    original_count: int
    final_count: int
    merged_count: int
    pruned_count: int
    archived_count: int
    
    @property
    def reduction_percent(self) -> float:
        """Percentage reduction in facts."""
        if self.original_count == 0:
            return 0.0
        return (1 - self.final_count / self.original_count) * 100


def find_similar_facts(
    facts: List[Fact],
    similarity_threshold: float = 0.8,
) -> List[Tuple[int, int, float]]:
    """
    Find pairs of similar facts using simple text similarity.
    
    Args:
        facts: List of facts to compare
        similarity_threshold: Minimum similarity (0-1) to consider similar
        
    Returns:
        List of (idx1, idx2, similarity) tuples
    """
    similar_pairs = []
    
    for i in range(len(facts)):
        for j in range(i + 1, len(facts)):
            sim = _text_similarity(facts[i].text, facts[j].text)
            if sim >= similarity_threshold:
                similar_pairs.append((i, j, sim))
    
    return similar_pairs


def _text_similarity(text1: str, text2: str) -> float:
    """
    Simple word-overlap text similarity.
    
    Returns value between 0 and 1.
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union)


def merge_facts(fact1: Fact, fact2: Fact) -> Fact:
    """
    Merge two similar facts into one.
    
    Keeps the higher salience and combines tags.
    """
    # Prefer longer/more detailed text
    text = fact1.text if len(fact1.text) >= len(fact2.text) else fact2.text
    
    # Combine tags
    all_tags = list(set(fact1.tags + fact2.tags))
    
    # Take higher salience
    salience = max(fact1.salience, fact2.salience)
    
    # Use earlier time
    time = fact1.time if fact1.time <= fact2.time else fact2.time
    
    return Fact(
        text=text,
        tags=all_tags,
        time=time,
        salience=salience,
    )


def consolidate_facts(
    facts_store: FactsStore,
    merge_threshold: float = 0.8,
    prune_salience: float = 0.2,
    max_facts: int = 100,
    archive_path: Optional[str] = None,
) -> ConsolidationResult:
    """
    Consolidate a facts store by merging similar and pruning low-value facts.
    
    Args:
        facts_store: The facts store to consolidate
        merge_threshold: Similarity threshold for merging (0-1)
        prune_salience: Prune facts below this salience
        max_facts: Maximum facts to keep after consolidation
        archive_path: Path to archive pruned facts (optional)
        
    Returns:
        ConsolidationResult with statistics
    """
    original_count = len(facts_store.facts)
    archived = []
    pruned = []
    
    # Step 1: Find and merge similar facts
    merged_count = 0
    facts = list(facts_store.facts)  # Copy to work with
    
    similar_pairs = find_similar_facts(facts, merge_threshold)
    # Sort by similarity descending
    similar_pairs.sort(key=lambda x: x[2], reverse=True)
    
    merged_indices: Set[int] = set()
    for i, j, sim in similar_pairs:
        if i in merged_indices or j in merged_indices:
            continue
        
        # Merge facts[j] into facts[i]
        facts[i] = merge_facts(facts[i], facts[j])
        merged_indices.add(j)
        merged_count += 1
    
    # Remove merged facts
    facts = [f for idx, f in enumerate(facts) if idx not in merged_indices]
    
    # Step 2: Prune low-salience facts
    high_salience = [f for f in facts if f.salience >= prune_salience]
    pruned = [f for f in facts if f.salience < prune_salience]
    facts = high_salience
    
    # Step 3: Enforce max_facts limit (keep highest salience)
    if len(facts) > max_facts:
        facts.sort(key=lambda f: f.salience, reverse=True)
        archived.extend(facts[max_facts:])
        facts = facts[:max_facts]
    
    # Archive if requested
    if archive_path and (pruned or archived):
        _archive_facts(pruned + archived, archive_path)
    
    # Update store
    facts_store.facts = facts
    facts_store._save()
    
    return ConsolidationResult(
        original_count=original_count,
        final_count=len(facts),
        merged_count=merged_count,
        pruned_count=len(pruned),
        archived_count=len(archived),
    )


def _archive_facts(facts: List[Fact], archive_path: str) -> None:
    """Archive facts to a JSON file."""
    os.makedirs(os.path.dirname(archive_path) or ".", exist_ok=True)
    
    # Load existing archive
    existing = []
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r") as f:
                existing = json.load(f)
        except:
            pass
    
    # Add new facts
    for fact in facts:
        existing.append({
            "text": fact.text,
            "tags": fact.tags,
            "time": fact.time,
            "salience": fact.salience,
            "archived_at": datetime.now().isoformat(),
        })
    
    with open(archive_path, "w") as f:
        json.dump(existing, f, indent=2)


def decay_salience(
    facts_store: FactsStore,
    decay_rate: float = 0.05,
    min_salience: float = 0.1,
) -> int:
    """
    Reduce salience of all facts over time.
    
    This simulates "forgetting" - older facts become less prominent
    unless reinforced.
    
    Args:
        facts_store: Store to apply decay to
        decay_rate: Amount to reduce salience by
        min_salience: Don't decay below this value
        
    Returns:
        Number of facts affected
    """
    affected = 0
    
    for fact in facts_store.facts:
        if fact.salience > min_salience:
            fact.salience = max(min_salience, fact.salience - decay_rate)
            affected += 1
    
    facts_store._save()
    return affected


def reinforce_fact(
    facts_store: FactsStore,
    text_fragment: str,
    boost: float = 0.1,
) -> int:
    """
    Increase salience of facts matching a text fragment.
    
    Use this when a fact is referenced in conversation to
    keep it from being forgotten.
    
    Args:
        facts_store: Store to search
        text_fragment: Text to match (case-insensitive)
        boost: Amount to increase salience
        
    Returns:
        Number of facts reinforced
    """
    reinforced = 0
    fragment_lower = text_fragment.lower()
    
    for fact in facts_store.facts:
        if fragment_lower in fact.text.lower():
            fact.salience = min(1.0, fact.salience + boost)
            reinforced += 1
    
    if reinforced:
        facts_store._save()
    
    return reinforced


class MemoryManager:
    """
    High-level manager for NPC memory operations.
    
    Handles consolidation, decay, and archiving of facts.
    
    Example:
        >>> manager = MemoryManager(facts_store, archive_dir="./archive")
        >>> manager.consolidate()
        >>> manager.apply_decay()
    """
    
    def __init__(
        self,
        facts_store: FactsStore,
        archive_dir: Optional[str] = None,
        merge_threshold: float = 0.8,
        prune_salience: float = 0.2,
        max_facts: int = 100,
        decay_rate: float = 0.05,
    ):
        self.facts_store = facts_store
        self.archive_dir = archive_dir
        self.merge_threshold = merge_threshold
        self.prune_salience = prune_salience
        self.max_facts = max_facts
        self.decay_rate = decay_rate
    
    def consolidate(self) -> ConsolidationResult:
        """Run full consolidation."""
        archive_path = None
        if self.archive_dir:
            archive_path = os.path.join(
                self.archive_dir,
                f"archive_{datetime.now().strftime('%Y%m%d')}.json"
            )
        
        return consolidate_facts(
            self.facts_store,
            merge_threshold=self.merge_threshold,
            prune_salience=self.prune_salience,
            max_facts=self.max_facts,
            archive_path=archive_path,
        )
    
    def apply_decay(self) -> int:
        """Apply salience decay to all facts."""
        return decay_salience(self.facts_store, self.decay_rate)
    
    def reinforce(self, text: str, boost: float = 0.1) -> int:
        """Reinforce facts matching text."""
        return reinforce_fact(self.facts_store, text, boost)
    
    def stats(self) -> Dict:
        """Get memory statistics."""
        facts = self.facts_store.facts
        
        if not facts:
            return {
                "total_facts": 0,
                "avg_salience": 0,
                "high_salience_count": 0,
                "low_salience_count": 0,
                "unique_tags": [],
            }
        
        avg_salience = sum(f.salience for f in facts) / len(facts)
        high = sum(1 for f in facts if f.salience >= 0.7)
        low = sum(1 for f in facts if f.salience < 0.3)
        
        all_tags: Set[str] = set()
        for f in facts:
            all_tags.update(f.tags)
        
        return {
            "total_facts": len(facts),
            "avg_salience": round(avg_salience, 3),
            "high_salience_count": high,
            "low_salience_count": low,
            "unique_tags": sorted(all_tags),
        }
