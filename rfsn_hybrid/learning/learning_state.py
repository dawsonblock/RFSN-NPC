"""
Learning state tracking for NPC behavior adaptation.

Maintains bounded state about action weights and their performance.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from collections import deque


@dataclass
class ActionWeight:
    """
    Weight and statistics for a specific action in a specific context.
    
    Attributes:
        action: Action identifier (e.g., "GIFT_response", "INSULT_response")
        context_key: Context hash (e.g., "affinity:high,mood:pleased")
        weight: Current weight multiplier (0.5 to 2.0, default 1.0)
        success_count: Number of successful outcomes
        failure_count: Number of failed outcomes
        total_count: Total times this action was taken
        last_reward: Most recent reward signal
    """
    action: str
    context_key: str
    weight: float = 1.0
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    last_reward: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_count == 0:
            return 0.5  # Neutral prior
        return self.success_count / self.total_count
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> ActionWeight:
        return cls(**data)


class LearningState:
    """
    Bounded learning state for NPC behavior adaptation.
    
    Tracks action weights and their performance in different contexts.
    Enforces strict memory bounds to prevent unbounded growth.
    
    Configuration:
        max_entries: Maximum number of (context, action) pairs to track
        min_weight: Minimum allowed weight (prevents complete suppression)
        max_weight: Maximum allowed weight (prevents runaway amplification)
    """
    
    def __init__(
        self,
        path: Optional[str] = None,
        max_entries: int = 100,
        min_weight: float = 0.5,
        max_weight: float = 2.0,
        enabled: bool = False,
    ):
        self.path = path
        self.max_entries = max_entries
        self.min_weight = min_weight
        self.max_weight = max_weight
        self.enabled = enabled
        
        # Bounded storage: LRU eviction when full
        self.weights: Dict[Tuple[str, str], ActionWeight] = {}
        self.access_order: deque = deque(maxlen=max_entries)
        
        if path:
            self._load()
    
    def get_weight(self, context_key: str, action: str) -> float:
        """
        Get current weight for an action in a context.
        
        Returns 1.0 (neutral) if not tracked or learning disabled.
        """
        if not self.enabled:
            return 1.0
        
        key = (context_key, action)
        if key not in self.weights:
            return 1.0
        
        # Update LRU tracking
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        return self.weights[key].weight
    
    def update_weight(
        self,
        context_key: str,
        action: str,
        reward: float,
        learning_rate: float = 0.1,
    ) -> float:
        """
        Update weight based on outcome reward.
        
        Args:
            context_key: Context identifier
            action: Action identifier
            reward: Reward signal (-1.0 to 1.0)
            learning_rate: How quickly to adjust (0.0 to 1.0)
            
        Returns:
            New weight value
        """
        if not self.enabled:
            return 1.0
        
        key = (context_key, action)
        
        # Create entry if doesn't exist (with LRU eviction if needed)
        if key not in self.weights:
            if len(self.weights) >= self.max_entries:
                # Evict least recently used
                oldest = self.access_order.popleft()
                del self.weights[oldest]
            
            self.weights[key] = ActionWeight(
                action=action,
                context_key=context_key,
            )
        
        # Update statistics
        entry = self.weights[key]
        entry.total_count += 1
        entry.last_reward = reward
        
        if reward > 0:
            entry.success_count += 1
        elif reward < 0:
            entry.failure_count += 1
        
        # Adjust weight (gradient ascent)
        # Positive reward -> increase weight
        # Negative reward -> decrease weight
        delta = learning_rate * reward
        entry.weight = max(
            self.min_weight,
            min(self.max_weight, entry.weight + delta)
        )
        
        # Update LRU
        if key in self.access_order:
            self.access_order.remove(key)
        self.access_order.append(key)
        
        if self.path:
            self._save()
        
        return entry.weight
    
    def get_stats(self, context_key: str, action: str) -> Optional[ActionWeight]:
        """Get statistics for a specific (context, action) pair."""
        key = (context_key, action)
        return self.weights.get(key)
    
    def get_all_weights(self) -> List[ActionWeight]:
        """Get all tracked weights."""
        return list(self.weights.values())
    
    def reset(self) -> None:
        """Clear all learning state."""
        self.weights = {}
        self.access_order.clear()
        if self.path:
            self._save()
    
    def _load(self) -> None:
        """Load from disk."""
        if not self.path or not os.path.exists(self.path):
            return
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.enabled = data.get("enabled", self.enabled)
            weights_data = data.get("weights", [])
            
            for w_dict in weights_data:
                weight = ActionWeight.from_dict(w_dict)
                key = (weight.context_key, weight.action)
                self.weights[key] = weight
                self.access_order.append(key)
        except Exception:
            # Fail gracefully - start fresh
            self.weights = {}
            self.access_order.clear()
    
    def _save(self) -> None:
        """Persist to disk."""
        if not self.path:
            return
        
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        
        data = {
            "enabled": self.enabled,
            "max_entries": self.max_entries,
            "weights": [w.to_dict() for w in self.weights.values()],
        }
        
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def to_dict(self) -> Dict:
        """Serialize state for debugging."""
        return {
            "enabled": self.enabled,
            "max_entries": self.max_entries,
            "current_entries": len(self.weights),
            "weights": [w.to_dict() for w in self.weights.values()],
        }
