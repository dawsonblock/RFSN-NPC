"""
Semantic memory module using FAISS for vector similarity search.

This module provides embedding-based fact retrieval as an alternative to
the tag-based heuristic in storage.py. It uses sentence-transformers for
embeddings and FAISS for efficient similarity search.

Dependencies are optional - install with: pip install rfsn_hybrid_engine[semantic]
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

# Check for optional dependencies
_SEMANTIC_AVAILABLE = False
try:
    import numpy as np
    import faiss
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_AVAILABLE = True
except ImportError:
    pass


def is_semantic_available() -> bool:
    """Check if semantic memory dependencies are installed."""
    return _SEMANTIC_AVAILABLE


@dataclass
class SemanticFact:
    """A fact with its embedding for semantic search."""
    text: str
    tags: List[str]
    time: str
    salience: float
    embedding: Optional[List[float]] = field(default=None, repr=False)


class SemanticFactStore:
    """
    Embedding-based fact storage with FAISS similarity search.
    
    This provides semantic retrieval of facts based on query similarity,
    rather than simple tag matching. Falls back gracefully if dependencies
    aren't installed.
    
    Attributes:
        model_name: The sentence-transformers model to use for embeddings
        path: Path to persist the fact store
    
    Example:
        >>> store = SemanticFactStore("./facts.json")
        >>> store.add_fact("Player gave Lydia a sword", ["gift"], 0.9)
        >>> results = store.search("Has anyone given me a weapon?", k=3)
    """
    
    DEFAULT_MODEL = "all-MiniLM-L6-v2"  # Fast, good quality, 384-dim
    
    def __init__(
        self,
        path: str,
        model_name: str = DEFAULT_MODEL,
        lazy_load: bool = True,
    ):
        """
        Initialize the semantic fact store.
        
        Args:
            path: Path to persist facts (JSON format)
            model_name: Sentence-transformers model name
            lazy_load: If True, delay loading the model until first use
        """
        if not _SEMANTIC_AVAILABLE:
            raise ImportError(
                "Semantic memory requires additional dependencies.\n"
                "Install with: pip install rfsn_hybrid_engine[semantic]"
            )
        
        self.path = path
        self.model_name = model_name
        self.facts: List[SemanticFact] = []
        self._model: Optional[SentenceTransformer] = None
        self._index: Optional[faiss.IndexFlatIP] = None
        self._embedding_dim: Optional[int] = None
        
        if not lazy_load:
            self._ensure_model()
        
        self._load()
    
    def _ensure_model(self) -> SentenceTransformer:
        """Lazy-load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            self._embedding_dim = self._model.get_sentence_embedding_dimension()
        return self._model
    
    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from current facts."""
        if not self.facts:
            self._index = None
            return
        
        self._ensure_model()
        
        # Stack all embeddings into a matrix
        embeddings = []
        for f in self.facts:
            if f.embedding is not None:
                embeddings.append(f.embedding)
            else:
                # Re-embed if embedding is missing
                emb = self._model.encode(f.text, normalize_embeddings=True)
                f.embedding = emb.tolist()
                embeddings.append(f.embedding)
        
        if not embeddings:
            self._index = None
            return
        
        # Create FAISS index (Inner Product = cosine similarity with normalized vectors)
        matrix = np.array(embeddings, dtype=np.float32)
        self._index = faiss.IndexFlatIP(matrix.shape[1])
        self._index.add(matrix)
    
    def _load(self) -> None:
        """Load facts from disk."""
        if not os.path.exists(self.path):
            return
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            
            self.facts = []
            for item in raw:
                fact = SemanticFact(
                    text=item["text"],
                    tags=item["tags"],
                    time=item["time"],
                    salience=item["salience"],
                    embedding=item.get("embedding"),
                )
                self.facts.append(fact)
            
            self._rebuild_index()
            logger.info(f"Loaded {len(self.facts)} facts from {self.path}")
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load facts from {self.path}: {e}")
            self.facts = []
    
    def _save(self) -> None:
        """Persist facts to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        
        data = []
        for f in self.facts:
            data.append({
                "text": f.text,
                "tags": f.tags,
                "time": f.time,
                "salience": f.salience,
                "embedding": f.embedding,
            })
        
        with open(self.path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
    
    def add_fact(self, text: str, tags: List[str], salience: float) -> None:
        """
        Add a new fact with semantic embedding.
        
        Args:
            text: The fact text to store
            tags: Associated tags for hybrid retrieval
            salience: Importance score (0.0 to 1.0)
        """
        model = self._ensure_model()
        
        # Generate embedding
        embedding = model.encode(text, normalize_embeddings=True)
        
        fact = SemanticFact(
            text=text,
            tags=tags,
            time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            salience=max(0.0, min(1.0, salience)),
            embedding=embedding.tolist(),
        )
        
        self.facts.append(fact)
        self._rebuild_index()
        self._save()
    
    def search(
        self,
        query: str,
        k: int = 3,
        min_similarity: float = 0.0,
    ) -> List[Tuple[str, float]]:
        """
        Find facts semantically similar to the query.
        
        Args:
            query: The search query
            k: Number of results to return
            min_similarity: Minimum cosine similarity threshold
            
        Returns:
            List of (fact_text, similarity_score) tuples, sorted by relevance
        """
        if not self.facts or self._index is None:
            return []
        
        model = self._ensure_model()
        
        # Encode query
        query_emb = model.encode(query, normalize_embeddings=True)
        query_emb = np.array([query_emb], dtype=np.float32)
        
        # Search
        k = min(k, len(self.facts))
        scores, indices = self._index.search(query_emb, k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and score >= min_similarity:
                results.append((self.facts[idx].text, float(score)))
        
        return results
    
    def search_texts(self, query: str, k: int = 3) -> List[str]:
        """
        Convenience method returning just the fact texts.
        
        Args:
            query: The search query
            k: Number of results to return
            
        Returns:
            List of fact texts, sorted by relevance
        """
        return [text for text, _ in self.search(query, k)]
    
    def hybrid_search(
        self,
        query: str,
        want_tags: List[str],
        k: int = 3,
        semantic_weight: float = 0.6,
    ) -> List[str]:
        """
        Combine semantic similarity with tag matching for hybrid retrieval.
        
        Args:
            query: The search query for semantic matching
            want_tags: Tags to boost matching facts
            k: Number of results to return
            semantic_weight: Weight for semantic score (1 - this = tag weight)
            
        Returns:
            List of fact texts, sorted by combined score
        """
        if not self.facts:
            return []
        
        if self._index is None:
            self._rebuild_index()
        
        if self._index is None:
            return []
        
        model = self._ensure_model()
        
        # Get semantic scores
        query_emb = model.encode(query, normalize_embeddings=True)
        query_emb = np.array([query_emb], dtype=np.float32)
        
        # Search all facts
        scores, indices = self._index.search(query_emb, len(self.facts))
        
        # Build combined scores
        want_set = set(want_tags or [])
        scored_facts = []
        
        for sem_score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            
            fact = self.facts[idx]
            
            # Tag overlap score (0 to 1)
            if want_set:
                tag_overlap = len(want_set.intersection(set(fact.tags))) / len(want_set)
            else:
                tag_overlap = 0.0
            
            # Combined score
            combined = (semantic_weight * sem_score) + ((1 - semantic_weight) * tag_overlap)
            
            # Boost by salience
            combined *= (0.5 + 0.5 * fact.salience)
            
            scored_facts.append((fact.text, combined))
        
        # Sort by combined score and return top k
        scored_facts.sort(key=lambda x: x[1], reverse=True)
        return [text for text, _ in scored_facts[:k]]
    
    def wipe(self) -> None:
        """Clear all facts and remove persisted data."""
        self.facts = []
        self._index = None
        if os.path.exists(self.path):
            os.remove(self.path)
    
    def __len__(self) -> int:
        return len(self.facts)


# Convenience function for checking availability
def try_get_semantic_store(
    path: str,
    model_name: str = SemanticFactStore.DEFAULT_MODEL,
) -> Optional[SemanticFactStore]:
    """
    Try to create a SemanticFactStore, returning None if dependencies missing.
    
    This is useful for graceful fallback to tag-based retrieval.
    """
    if not _SEMANTIC_AVAILABLE:
        return None
    
    try:
        return SemanticFactStore(path, model_name)
    except Exception as e:
        logger.warning(f"Failed to initialize semantic store: {e}")
        return None
