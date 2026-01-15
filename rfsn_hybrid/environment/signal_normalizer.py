"""
Signal normalizer for environment feedback.

Normalizes and bounds consequence signals before they affect NPC state.
Ensures signals remain consistent and don't cause runaway effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .consequence_mapper import ConsequenceSignal, ConsequenceType


@dataclass
class NormalizedSignal:
    """
    A normalized consequence signal ready for reducer consumption.
    
    Attributes:
        consequence_type: Type of consequence
        intensity: Normalized intensity (0.0 to 1.0)
        affinity_delta: How this affects affinity
        mood_impact: How this affects mood (mood name)
        relationship_delta: Specific relationship value changes
        metadata: Additional signal metadata
    """
    consequence_type: ConsequenceType
    intensity: float
    affinity_delta: float = 0.0
    mood_impact: Optional[str] = None
    relationship_delta: Dict[str, float] = None
    metadata: Dict = None
    
    def __post_init__(self):
        """Initialize optional fields."""
        if self.relationship_delta is None:
            self.relationship_delta = {}
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            "consequence_type": self.consequence_type.value,
            "intensity": self.intensity,
            "affinity_delta": self.affinity_delta,
            "mood_impact": self.mood_impact,
            "relationship_delta": self.relationship_delta,
            "metadata": self.metadata,
        }


class SignalNormalizer:
    """
    Normalizes consequence signals for consistent state updates.
    
    Key responsibilities:
    - Bound signal intensities
    - Convert signals to state changes
    - Apply dampening to prevent overreaction
    - Aggregate multiple signals
    """
    
    # Map consequence types to affinity deltas
    AFFINITY_IMPACT: Dict[ConsequenceType, float] = {
        ConsequenceType.BONDING: 0.08,
        ConsequenceType.ALIENATION: -0.12,
        ConsequenceType.ACHIEVEMENT: 0.05,
        ConsequenceType.FAILURE: -0.04,
        ConsequenceType.JUSTICE: 0.06,
        ConsequenceType.INJUSTICE: -0.10,
        ConsequenceType.STRESS: -0.02,
        ConsequenceType.RELIEF: 0.01,
        ConsequenceType.THREAT: -0.03,
        ConsequenceType.SAFETY: 0.02,
    }
    
    # Map consequence types to mood changes
    MOOD_IMPACT: Dict[ConsequenceType, str] = {
        ConsequenceType.STRESS: "Anxious",
        ConsequenceType.RELIEF: "Calm",
        ConsequenceType.THREAT: "Fearful",
        ConsequenceType.SAFETY: "Secure",
        ConsequenceType.BONDING: "Warm",
        ConsequenceType.ALIENATION: "Distant",
        ConsequenceType.ACHIEVEMENT: "Proud",
        ConsequenceType.FAILURE: "Disappointed",
        ConsequenceType.INJUSTICE: "Outraged",
        ConsequenceType.JUSTICE: "Satisfied",
    }
    
    def __init__(
        self,
        dampening_factor: float = 0.5,
        max_affinity_change: float = 0.15,
        enabled: bool = True,
    ):
        """
        Initialize signal normalizer.
        
        Args:
            dampening_factor: Multiplier for all signals (0.0 to 1.0)
            max_affinity_change: Maximum affinity change per signal
            enabled: Whether to process signals
        """
        self.dampening_factor = max(0.0, min(1.0, dampening_factor))
        self.max_affinity_change = max(0.0, min(1.0, max_affinity_change))
        self.enabled = enabled
    
    def normalize(
        self,
        signal: ConsequenceSignal,
    ) -> NormalizedSignal:
        """
        Normalize a single consequence signal.
        
        Args:
            signal: Consequence signal to normalize
            
        Returns:
            Normalized signal ready for reducer
        """
        if not self.enabled:
            return NormalizedSignal(
                consequence_type=signal.consequence_type,
                intensity=0.0,
            )
        
        # Apply dampening
        damped_intensity = signal.intensity * self.dampening_factor
        
        # Calculate affinity impact
        base_affinity = self.AFFINITY_IMPACT.get(signal.consequence_type, 0.0)
        affinity_delta = base_affinity * damped_intensity
        
        # Clamp affinity change
        affinity_delta = max(
            -self.max_affinity_change,
            min(self.max_affinity_change, affinity_delta)
        )
        
        # Determine mood impact (if strong enough)
        mood_impact = None
        if damped_intensity > 0.4:  # Threshold for mood change
            mood_impact = self.MOOD_IMPACT.get(signal.consequence_type)
        
        return NormalizedSignal(
            consequence_type=signal.consequence_type,
            intensity=damped_intensity,
            affinity_delta=affinity_delta,
            mood_impact=mood_impact,
            metadata={
                "source_event": signal.source_event.value,
                "decay_rate": signal.decay_rate,
            },
        )
    
    def normalize_batch(
        self,
        signals: List[ConsequenceSignal],
    ) -> List[NormalizedSignal]:
        """
        Normalize multiple signals.
        
        Args:
            signals: List of consequence signals
            
        Returns:
            List of normalized signals
        """
        return [self.normalize(s) for s in signals]
    
    def aggregate(
        self,
        signals: List[ConsequenceSignal],
    ) -> NormalizedSignal:
        """
        Aggregate multiple signals into one normalized signal.
        
        Useful when multiple events occur simultaneously.
        
        Args:
            signals: Signals to aggregate
            
        Returns:
            Single aggregated normalized signal
        """
        if not signals:
            # Return neutral signal
            return NormalizedSignal(
                consequence_type=ConsequenceType.RELIEF,
                intensity=0.0,
            )
        
        # Normalize all signals first
        normalized = self.normalize_batch(signals)
        
        # Sum affinity deltas (with dampening for multiple signals)
        total_affinity = sum(s.affinity_delta for s in normalized)
        # Apply diminishing returns for many signals
        dampened_affinity = total_affinity * (0.8 ** (len(signals) - 1))
        dampened_affinity = max(
            -self.max_affinity_change,
            min(self.max_affinity_change, dampened_affinity)
        )
        
        # Average intensity
        avg_intensity = sum(s.intensity for s in normalized) / len(normalized)
        
        # Pick strongest mood impact
        mood_impact = None
        strongest = max(normalized, key=lambda s: s.intensity)
        if strongest.mood_impact:
            mood_impact = strongest.mood_impact
        
        # Use most common consequence type
        type_counts = {}
        for s in normalized:
            type_counts[s.consequence_type] = type_counts.get(s.consequence_type, 0) + 1
        most_common_type = max(type_counts, key=type_counts.get)
        
        return NormalizedSignal(
            consequence_type=most_common_type,
            intensity=avg_intensity,
            affinity_delta=dampened_affinity,
            mood_impact=mood_impact,
            metadata={"aggregated_from": len(signals)},
        )
    
    def filter_by_intensity(
        self,
        signals: List[ConsequenceSignal],
        min_intensity: float = 0.1,
    ) -> List[ConsequenceSignal]:
        """
        Filter out weak signals below threshold.
        
        Args:
            signals: Signals to filter
            min_intensity: Minimum intensity to keep
            
        Returns:
            Filtered signals
        """
        return [s for s in signals if s.intensity >= min_intensity]
    
    def filter_by_affects(
        self,
        signals: List[ConsequenceSignal],
        target: str,
    ) -> List[ConsequenceSignal]:
        """
        Filter signals that affect a specific target.
        
        Args:
            signals: Signals to filter
            target: Target to filter for (e.g., "mood", "relationship")
            
        Returns:
            Filtered signals
        """
        return [s for s in signals if target in s.affects]
