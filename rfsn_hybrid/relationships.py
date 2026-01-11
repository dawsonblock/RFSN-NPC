"""
Multi-NPC relationship system.

Track relationships between NPCs and how they affect conversations.
NPCs can have opinions about each other, share information, and
their relationships with the player can influence each other.
"""
from __future__ import annotations

import os
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class NPCOpinion:
    """
    One NPC's opinion of another.
    
    Attributes:
        target_npc: Name of NPC being judged
        affinity: How much this NPC likes the target (-1 to 1)
        trust: How much this NPC trusts the target (0 to 1)
        respect: How much this NPC respects the target (0 to 1)
        last_interaction: When they last interacted
        notes: Facts this NPC knows about the target
    """
    target_npc: str
    affinity: float = 0.0
    trust: float = 0.5
    respect: float = 0.5
    last_interaction: str = ""
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NPCOpinion":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass 
class NPCRelationshipProfile:
    """
    Complete relationship profile for one NPC.
    
    Tracks this NPC's relationships with the player and other NPCs.
    """
    npc_name: str
    player_affinity: float = 0.5
    player_trust: float = 0.5
    allies: List[str] = field(default_factory=list)
    rivals: List[str] = field(default_factory=list)
    opinions: Dict[str, NPCOpinion] = field(default_factory=dict)
    shared_experiences: List[str] = field(default_factory=list)
    
    def get_opinion(self, target: str) -> NPCOpinion:
        """Get or create opinion of another NPC."""
        if target not in self.opinions:
            self.opinions[target] = NPCOpinion(target_npc=target)
        return self.opinions[target]
    
    def set_ally(self, npc_name: str) -> None:
        """Mark another NPC as an ally."""
        if npc_name not in self.allies:
            self.allies.append(npc_name)
        if npc_name in self.rivals:
            self.rivals.remove(npc_name)
        self.get_opinion(npc_name).affinity = max(0.5, self.get_opinion(npc_name).affinity)
    
    def set_rival(self, npc_name: str) -> None:
        """Mark another NPC as a rival."""
        if npc_name not in self.rivals:
            self.rivals.append(npc_name)
        if npc_name in self.allies:
            self.allies.remove(npc_name)
        self.get_opinion(npc_name).affinity = min(-0.3, self.get_opinion(npc_name).affinity)
    
    def to_dict(self) -> Dict:
        data = {
            "npc_name": self.npc_name,
            "player_affinity": self.player_affinity,
            "player_trust": self.player_trust,
            "allies": self.allies,
            "rivals": self.rivals,
            "opinions": {k: v.to_dict() for k, v in self.opinions.items()},
            "shared_experiences": self.shared_experiences,
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "NPCRelationshipProfile":
        opinions = {}
        if "opinions" in data:
            opinions = {k: NPCOpinion.from_dict(v) for k, v in data["opinions"].items()}
        
        return cls(
            npc_name=data["npc_name"],
            player_affinity=data.get("player_affinity", 0.5),
            player_trust=data.get("player_trust", 0.5),
            allies=data.get("allies", []),
            rivals=data.get("rivals", []),
            opinions=opinions,
            shared_experiences=data.get("shared_experiences", []),
        )


class RelationshipNetwork:
    """
    Manages relationships between all NPCs and the player.
    
    Example:
        >>> network = RelationshipNetwork("./relationships.json")
        >>> network.update_relationship("Lydia", "Belethor", affinity=-0.3)
        >>> opinion = network.get_opinion("Lydia", "Belethor")
    """
    
    def __init__(self, path: str):
        """
        Initialize relationship network.
        
        Args:
            path: Path to JSON file for persistence
        """
        self.path = path
        self.profiles: Dict[str, NPCRelationshipProfile] = {}
        self._load()
    
    def _load(self) -> None:
        """Load from disk."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, profile_data in data.items():
                self.profiles[name] = NPCRelationshipProfile.from_dict(profile_data)
        except Exception as e:
            logger.warning(f"Failed to load relationships: {e}")
    
    def _save(self) -> None:
        """Persist to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        data = {name: p.to_dict() for name, p in self.profiles.items()}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def get_profile(self, npc_name: str) -> NPCRelationshipProfile:
        """Get or create profile for an NPC."""
        if npc_name not in self.profiles:
            self.profiles[npc_name] = NPCRelationshipProfile(npc_name=npc_name)
        return self.profiles[npc_name]
    
    def get_opinion(self, from_npc: str, about_npc: str) -> NPCOpinion:
        """Get one NPC's opinion of another."""
        profile = self.get_profile(from_npc)
        return profile.get_opinion(about_npc)
    
    def update_relationship(
        self,
        from_npc: str,
        to_npc: str,
        affinity_delta: float = 0.0,
        trust_delta: float = 0.0,
        respect_delta: float = 0.0,
    ) -> NPCOpinion:
        """
        Update relationship between two NPCs.
        
        Args:
            from_npc: NPC whose opinion is changing
            to_npc: NPC being judged
            affinity_delta: Change in affinity
            trust_delta: Change in trust
            respect_delta: Change in respect
            
        Returns:
            Updated opinion
        """
        opinion = self.get_opinion(from_npc, to_npc)
        
        opinion.affinity = max(-1.0, min(1.0, opinion.affinity + affinity_delta))
        opinion.trust = max(0.0, min(1.0, opinion.trust + trust_delta))
        opinion.respect = max(0.0, min(1.0, opinion.respect + respect_delta))
        opinion.last_interaction = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Auto-classify as ally/rival based on thresholds
        profile = self.get_profile(from_npc)
        if opinion.affinity >= 0.6:
            profile.set_ally(to_npc)
        elif opinion.affinity <= -0.5:
            profile.set_rival(to_npc)
        
        self._save()
        return opinion
    
    def add_shared_experience(
        self,
        npcs: List[str],
        experience: str,
    ) -> None:
        """
        Record a shared experience between NPCs.
        
        This creates mutual connections and positive sentiment.
        """
        for npc in npcs:
            profile = self.get_profile(npc)
            if experience not in profile.shared_experiences:
                profile.shared_experiences.append(experience)
            
            # Build relationships with other NPCs in the experience
            for other in npcs:
                if other != npc:
                    self.update_relationship(npc, other, affinity_delta=0.05)
        
        self._save()
    
    def add_note(self, from_npc: str, about_npc: str, note: str) -> None:
        """Add a note/fact one NPC knows about another."""
        opinion = self.get_opinion(from_npc, about_npc)
        if note not in opinion.notes:
            opinion.notes.append(note)
        self._save()
    
    def get_allies(self, npc_name: str) -> List[str]:
        """Get list of NPC's allies."""
        return self.get_profile(npc_name).allies
    
    def get_rivals(self, npc_name: str) -> List[str]:
        """Get list of NPC's rivals."""
        return self.get_profile(npc_name).rivals
    
    def get_relationship_summary(self, npc_name: str) -> str:
        """
        Get a text summary of an NPC's relationships.
        
        Useful for including in prompts.
        """
        profile = self.get_profile(npc_name)
        lines = [f"{npc_name}'s relationships:"]
        
        if profile.allies:
            lines.append(f"  Allies: {', '.join(profile.allies)}")
        if profile.rivals:
            lines.append(f"  Rivals: {', '.join(profile.rivals)}")
        
        for target, opinion in profile.opinions.items():
            if abs(opinion.affinity) > 0.3 or opinion.trust != 0.5:
                sentiment = "likes" if opinion.affinity > 0 else "dislikes"
                lines.append(f"  {sentiment} {target} (affinity: {opinion.affinity:.2f})")
        
        return "\n".join(lines) if len(lines) > 1 else f"{npc_name} has no notable relationships."
    
    def propagate_player_reputation(
        self,
        acting_npc: str,
        player_action: str,
        affinity_change: float,
    ) -> Dict[str, float]:
        """
        Propagate player reputation changes through NPC network.
        
        When player does something good/bad to one NPC, it affects
        the opinions of that NPC's allies and rivals.
        
        Returns:
            Dictionary of NPC names to their affinity changes
        """
        changes = {}
        profile = self.get_profile(acting_npc)
        
        # Allies are influenced positively
        for ally in profile.allies:
            # Allies adopt 50% of the sentiment
            ally_change = affinity_change * 0.5
            ally_profile = self.get_profile(ally)
            ally_profile.player_affinity = max(
                -1.0, min(1.0, ally_profile.player_affinity + ally_change)
            )
            changes[ally] = ally_change
        
        # Rivals are influenced negatively (contrarian)
        for rival in profile.rivals:
            # Rivals adopt opposite of 30% of the sentiment
            rival_change = -affinity_change * 0.3
            rival_profile = self.get_profile(rival)
            rival_profile.player_affinity = max(
                -1.0, min(1.0, rival_profile.player_affinity + rival_change)
            )
            changes[rival] = rival_change
        
        self._save()
        return changes
    
    def wipe(self) -> None:
        """Clear all relationships."""
        self.profiles = {}
        if os.path.exists(self.path):
            os.remove(self.path)


def get_relevant_npcs_for_topic(
    network: RelationshipNetwork,
    current_npc: str,
    topic: str,
) -> List[str]:
    """
    Find NPCs relevant to a topic in conversation.
    
    Searches through the network's notes and relationships
    to find NPCs that might be relevant.
    """
    relevant = set()
    profile = network.get_profile(current_npc)
    
    topic_lower = topic.lower()
    
    # Check opinions/notes
    for npc_name, opinion in profile.opinions.items():
        for note in opinion.notes:
            if topic_lower in note.lower():
                relevant.add(npc_name)
    
    # Check shared experiences
    for exp in profile.shared_experiences:
        if topic_lower in exp.lower():
            # Find other NPCs that share this experience
            for other_name, other_profile in network.profiles.items():
                if other_name != current_npc and exp in other_profile.shared_experiences:
                    relevant.add(other_name)
    
    return list(relevant)
