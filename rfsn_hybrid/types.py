from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Literal, Optional, List, Dict, Any
import json
import os

@dataclass
class RFSNState:
    """
    Represents the current state of an NPC in the RFSN system.
    
    Attributes:
        npc_name: The NPC's display name (e.g., "Lydia")
        role: The NPC's role/occupation (e.g., "Housecarl")
        affinity: Relationship score from -1.0 (hostile) to 1.0 (devoted)
        mood: Current emotional state (e.g., "Neutral", "Angry", "Pleased")
        player_name: The player character's name
        player_playstyle: Player archetype ("Combatant", "Thief", "Mage", "Explorer")
        recent_memory: Last significant event this NPC remembers
    """
    npc_name: str
    role: str
    affinity: float        # -1.0 .. 1.0
    mood: str
    player_name: str
    player_playstyle: str  # "Combatant", "Thief", "Mage", "Explorer"
    recent_memory: str = ""

    def attitude(self) -> str:
        """Returns a descriptive attitude string based on current affinity level."""
        a = self.affinity
        if a >= 0.75: return "Devoted, warm, protective."
        if a >= 0.25: return "Friendly, cooperative."
        if a > -0.25: return "Neutral, professional."
        if a > -0.75: return "Cold, suspicious, dismissive."
        return "Hostile, contemptuous."

    def style_rules(self) -> str:
        """Returns dialogue style guidelines for the LLM."""
        return (
            "Use archaic fantasy tone. Skyrim-like cadence and slang "
            "(milk-drinker, Divines, Thane, etc.). Keep it 1–2 sentences."
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to a dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RFSNState":
        """Deserialize state from a dictionary."""
        return cls(**data)

    def save(self, path: str) -> None:
        """Persist state to a JSON file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> Optional["RFSNState"]:
        """Load state from a JSON file. Returns None if file doesn't exist."""
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

EventType = Literal[
    "TALK","GIFT","PUNCH","INSULT","PRAISE","HELP","THEFT","QUEST_COMPLETE","THREATEN"
]

@dataclass
class Event:
    type: EventType
    raw_text: str
    strength: float = 1.0  # 0.0..2.0
    tags: Optional[List[str]] = None
