"""
Feature encoder for contextual bandit learning.

Converts NPC state, relationships, and environment signals into
a fixed-size feature representation for the learning system.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

# Feature schema version - increment when changing feature format
FEATURE_SCHEMA_VERSION = 1


@dataclass
class FeatureVector:
    """
    Fixed-size feature representation for learning.
    
    Attributes:
        context_key: Human-readable context identifier
        features: Dictionary of feature name -> value
        schema_version: Feature schema version for compatibility
    """
    context_key: str
    features: Dict[str, float]
    schema_version: int = FEATURE_SCHEMA_VERSION
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "context_key": self.context_key,
            "features": self.features,
            "schema_version": self.schema_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureVector":
        """Deserialize from dictionary."""
        return cls(
            context_key=data["context_key"],
            features=data["features"],
            schema_version=data.get("schema_version", 1),
        )


class FeatureEncoder:
    """
    Encodes NPC state and context into feature vectors.
    
    Features are:
    - Fixed-size (no unbounded growth)
    - Stable across versions (schema versioning)
    - Normalized (bounded values)
    - Interpretable (meaningful names)
    """
    
    def __init__(self):
        """Initialize feature encoder."""
        self.schema_version = FEATURE_SCHEMA_VERSION
    
    def encode(
        self,
        affinity: float,
        mood: str,
        recent_events: Optional[List[str]] = None,
        relationship_state: Optional[Dict[str, Any]] = None,
        environment_signals: Optional[Dict[str, float]] = None,
    ) -> FeatureVector:
        """
        Encode state into feature vector.
        
        Args:
            affinity: Current affinity (-1.0 to 1.0)
            mood: Current mood string
            recent_events: Optional list of recent event types
            relationship_state: Optional relationship metadata
            environment_signals: Optional environment signals (tension, hostility, etc.)
            
        Returns:
            FeatureVector with normalized features
        """
        features: Dict[str, float] = {}
        
        # Core state features (always present)
        features["affinity_raw"] = affinity
        features["affinity_bucket"] = self._discretize_affinity(affinity)
        
        # Mood features (one-hot encoding of common moods)
        mood_lower = mood.lower()
        for mood_name in ["neutral", "pleased", "warm", "grateful", "angry", 
                          "offended", "hostile", "suspicious"]:
            features[f"mood_{mood_name}"] = 1.0 if mood_lower == mood_name else 0.0
        
        # Recent event features (if provided)
        if recent_events:
            features["has_recent_events"] = 1.0
            # Hash recent events into a small number of features
            event_hash = self._hash_events(recent_events[-3:])  # Last 3 events
            features["event_pattern"] = event_hash
        else:
            features["has_recent_events"] = 0.0
            features["event_pattern"] = 0.0
        
        # Relationship features (if provided)
        if relationship_state:
            features["relationship_duration"] = min(1.0, 
                relationship_state.get("duration_normalized", 0.0))
            features["interaction_count"] = min(1.0,
                relationship_state.get("interaction_count", 0.0) / 100.0)
        else:
            features["relationship_duration"] = 0.0
            features["interaction_count"] = 0.0
        
        # Environment signal features (if provided)
        if environment_signals:
            features["env_tension"] = environment_signals.get("tension", 0.0)
            features["env_hostility"] = environment_signals.get("hostility", 0.0)
            features["env_proximity"] = environment_signals.get("proximity", 0.0)
        else:
            features["env_tension"] = 0.0
            features["env_hostility"] = 0.0
            features["env_proximity"] = 0.0
        
        # Build context key for grouping similar situations
        context_key = self._build_context_key(affinity, mood, recent_events)
        
        return FeatureVector(
            context_key=context_key,
            features=features,
            schema_version=self.schema_version,
        )
    
    def _discretize_affinity(self, affinity: float) -> float:
        """
        Discretize affinity into buckets.
        
        Returns a normalized value 0-1 representing the bucket.
        """
        if affinity >= 0.6:
            return 0.8  # High
        elif affinity >= 0.2:
            return 0.6  # Mid
        elif affinity >= -0.2:
            return 0.4  # Neutral
        elif affinity >= -0.6:
            return 0.2  # Low
        else:
            return 0.0  # Hostile
    
    def _hash_events(self, events: List[str]) -> float:
        """
        Hash a sequence of events to a normalized float.
        
        This provides a stable, bounded representation of event patterns.
        """
        if not events:
            return 0.0
        
        # Create a stable hash of the event sequence
        event_str = "|".join(sorted(events))
        hash_val = int(hashlib.sha256(event_str.encode()).hexdigest()[:8], 16)
        
        # Normalize to 0-1
        return (hash_val % 1000) / 1000.0
    
    def _build_context_key(
        self,
        affinity: float,
        mood: str,
        recent_events: Optional[List[str]] = None,
    ) -> str:
        """
        Build a human-readable context key for grouping.
        
        Args:
            affinity: Current affinity
            mood: Current mood
            recent_events: Recent event types
            
        Returns:
            Context key string
        """
        # Discretize affinity
        if affinity >= 0.6:
            aff_bucket = "high"
        elif affinity >= 0.2:
            aff_bucket = "mid"
        elif affinity >= -0.2:
            aff_bucket = "neutral"
        elif affinity >= -0.6:
            aff_bucket = "low"
        else:
            aff_bucket = "hostile"
        
        parts = [f"aff:{aff_bucket}", f"mood:{mood.lower()}"]
        
        # Optionally include recent event context
        if recent_events:
            event_str = "_".join(recent_events[-2:])  # Last 2 events
            parts.append(f"events:{event_str}")
        
        return "|".join(parts)
    
    def validate_features(self, features: Dict[str, float]) -> bool:
        """
        Validate that all features are in expected ranges.
        
        Returns:
            True if features are valid
        """
        for key, value in features.items():
            if not isinstance(value, (int, float)):
                return False
            if key.startswith("mood_") or key == "has_recent_events":
                # Binary features
                if value not in (0.0, 1.0):
                    return False
            else:
                # Continuous features should be bounded
                if not (0.0 <= value <= 1.0 or -1.0 <= value <= 1.0):
                    return False
        
        return True
