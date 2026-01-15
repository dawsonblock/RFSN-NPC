"""
Enhanced relationship dynamics for RFSN NPC system.

Extends the existing relationship system with continuous dynamics:
- Trust (grows slowly, decays quickly)
- Fear (spikes quickly, fades slowly)
- Attraction (chemistry, charisma response)
- Resentment (accumulates, decays slowly)
- Obligation (sense of debt or duty)

All changes flow through the reducer. No autonomous behavior.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Decay and growth constants (per hour of game time)
DECAY_RATES = {
    "trust": 0.01,          # Trust decays slowly
    "fear": 0.05,           # Fear fades faster
    "attraction": 0.03,     # Attraction decays slowly
    "resentment": 0.02,     # Resentment decays slowly
    "obligation": 0.03,     # Obligations fade slowly
}

GROWTH_RATES = {
    "trust": 0.05,          # Trust builds slowly
    "fear": 0.12,           # Fear grows quickly
    "attraction": 0.06,     # Attraction builds steadily
    "resentment": 0.10,     # Resentment accumulates quickly
    "obligation": 0.08,     # Obligations build moderately
}

DECAY_RATES = {
    "trust": 0.01,          # Trust decays slowly
    "fear": 0.05,           # Fear fades faster
    "attraction": 0.03,     # Attraction fades moderately
    "resentment": 0.02,     # Resentment lingers
    "obligation": 0.04,     # Obligations fade with time
}


@dataclass
class RelationshipDynamics:
    """
    Continuous relationship dynamics for player-NPC relationships.
    
    These values change gradually over time through reducer-controlled updates.
    All changes are explicit and debuggable.
    
    Attributes:
        trust: How much NPC trusts player (0.0 to 1.0)
        fear: How much NPC fears player (0.0 to 1.0)
        attraction: Positive draw toward player (0.0 to 1.0)
        resentment: Accumulated negative feeling (0.0 to 1.0)
        obligation: Sense of debt or duty (0.0 to 1.0)
        last_updated: When values were last changed
    """
    trust: float = 0.5
    fear: float = 0.0
    attraction: float = 0.3
    resentment: float = 0.0
    obligation: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Decay rates (how quickly values return to neutral per hour)
    TRUST_DECAY_RATE = 0.01
    FEAR_DECAY_RATE = 0.05
    ATTRACTION_DECAY_RATE = 0.02
    RESENTMENT_DECAY_RATE = 0.03
    OBLIGATION_DECAY_RATE = 0.04
    
    def apply_decay(self, hours_passed: float) -> None:
        """
        Apply time-based decay to relationship dynamics.
        
        Trust slowly decays toward 0.5 (neutral).
        Fear, resentment decay toward 0.0.
        Attraction decays slowly toward 0.3 (slight baseline).
        Obligation decays toward 0.0.
        
        Args:
            hours_passed: Game hours elapsed
        """
        # Trust decays toward neutral (0.5)
        if self.trust > 0.5:
            self.trust = max(0.5, self.trust - self.TRUST_DECAY_RATE * hours_passed)
        elif self.trust < 0.5:
            self.trust = min(0.5, self.trust + self.TRUST_DECAY_RATE * hours_passed)
        
        # Fear decays toward 0
        self.fear = max(0.0, self.fear - self.FEAR_DECAY_RATE * hours_passed)
        
        # Attraction decays toward baseline (0.3)
        if self.attraction > 0.3:
            self.attraction = max(0.3, self.attraction - self.ATTRACTION_DECAY_RATE * hours_passed)
        elif self.attraction < 0.3:
            self.attraction = min(0.3, self.attraction + self.ATTRACTION_DECAY_RATE * hours_passed)
        
        # Resentment decays toward 0
        self.resentment = max(0.0, self.resentment - self.RESENTMENT_DECAY_RATE * hours_passed)
        
        # Obligation decays toward 0
        self.obligation = max(0.0, self.obligation - self.OBLIGATION_DECAY_RATE * hours_passed)
        
        self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "trust": self.trust,
            "fear": self.fear,
            "attraction": self.attraction,
            "resentment": self.resentment,
            "obligation": self.obligation,
            "last_updated": self.last_updated,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "RelationshipDynamics":
        return cls(**{k: v for k, v in data.items() if k in ["trust", "fear", "attraction", "resentment", "obligation", "last_updated"]})
    
    def get_summary(self) -> str:
        """Get human-readable summary of relationship dynamics."""
        parts = []
        
        if self.trust > 0.7:
            parts.append("deeply trusting")
        elif self.trust < 0.3:
            parts.append("distrustful")
        
        if self.fear > 0.6:
            parts.append("fearful")
        elif self.fear > 0.3:
            parts.append("cautious")
        
        if self.attraction > 0.7:
            parts.append("strongly drawn")
        elif self.attraction < 0.1:
            parts.append("indifferent")
        
        if self.resentment > 0.6:
            parts.append("resentful")
        elif self.resentment > 0.3:
            parts.append("bothered")
        
        if self.obligation > 0.6:
            parts.append("deeply indebted")
        elif self.obligation > 0.3:
            parts.append("obligated")
        
        return ", ".join(parts) if parts else "neutral feelings"


# Add RelationshipDynamics to existing NPCOpinion
@dataclass
class EnhancedNPCOpinion(NPCOpinion):
    """
    Enhanced NPC opinion with continuous relationship dynamics.
    
    Extends NPCOpinion with new dynamic attributes that
    change over time and decay naturally.
    """
    dynamics: RelationshipDynamics = field(default_factory=RelationshipDynamics)
    
    def to_dict(self) -> Dict:
        d = super().to_dict()
        d["dynamics"] = self.dynamics.to_dict()
        return d
    
    @classmethod
    def from_dict(cls, data: Dict) -> "EnhancedNPCOpinion":
        dynamics_data = data.pop("dynamics", {})
        opinion = super().from_dict(data)
        if dynamics_data:
            opinion.dynamics = RelationshipDynamics.from_dict(dynamics_data)
        return opinion
