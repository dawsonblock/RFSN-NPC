"""
Configuration system for NPC personality presets.

Load NPC configurations from YAML files for easy customization
without modifying code.
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NPCConfig:
    """
    Configuration for an NPC personality.
    
    This defines the NPC's name, role, initial state, and behavioral parameters.
    Can be loaded from YAML/JSON files or created programmatically.
    
    Attributes:
        name: NPC's display name
        role: NPC's role/occupation
        initial_affinity: Starting affinity (-1.0 to 1.0)
        initial_mood: Starting mood string
        personality_traits: List of personality descriptors
        speech_style: How the NPC speaks (formal, casual, gruff, etc.)
        backstory: Brief backstory for context
        likes: Things that increase affinity
        dislikes: Things that decrease affinity
    """
    name: str
    role: str
    initial_affinity: float = 0.5
    initial_mood: str = "Neutral"
    personality_traits: List[str] = field(default_factory=list)
    speech_style: str = "formal"
    backstory: str = ""
    likes: List[str] = field(default_factory=list)
    dislikes: List[str] = field(default_factory=list)
    
    # Advanced parameters
    affinity_gain_rate: float = 0.15
    affinity_loss_rate: float = 0.20
    decay_rate: float = 0.02
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NPCConfig":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def save(self, path: str) -> None:
        """Save config to JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> Optional["NPCConfig"]:
        """Load config from JSON or YAML file."""
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Try YAML first (if available), then JSON
            if path.endswith((".yaml", ".yml")):
                try:
                    import yaml
                    data = yaml.safe_load(content)
                except ImportError:
                    logger.warning("YAML support requires PyYAML: pip install pyyaml")
                    return None
            else:
                data = json.loads(content)
            
            return cls.from_dict(data)
            
        except Exception as e:
            logger.warning(f"Failed to load config from {path}: {e}")
            return None


# Built-in NPC presets
PRESETS: Dict[str, NPCConfig] = {
    "lydia": NPCConfig(
        name="Lydia",
        role="Housecarl",
        initial_affinity=0.6,
        initial_mood="Loyal",
        personality_traits=["loyal", "stoic", "protective", "sarcastic"],
        speech_style="formal but dry",
        backstory="Appointed as the Dragonborn's housecarl after their recognition as Thane of Whiterun.",
        likes=["combat", "loyalty", "respect"],
        dislikes=["cowardice", "betrayal", "disrespect"],
    ),
    "merchant": NPCConfig(
        name="Belethor",
        role="General Goods Merchant",
        initial_affinity=0.3,
        initial_mood="Eager",
        personality_traits=["greedy", "sycophantic", "shrewd"],
        speech_style="overly friendly, salesman-like",
        backstory="Owns a general goods store in Whiterun. Would sell anything for coin.",
        likes=["gold", "trade", "bargains"],
        dislikes=["theft", "haggling", "time-wasters"],
        affinity_gain_rate=0.1,
        affinity_loss_rate=0.3,
    ),
    "guard": NPCConfig(
        name="Whiterun Guard",
        role="City Guard",
        initial_affinity=0.4,
        initial_mood="Suspicious",
        personality_traits=["dutiful", "bored", "knee-injury"],
        speech_style="gruff, repetitive",
        backstory="A guard of Whiterun who used to be an adventurer.",
        likes=["order", "respect for law"],
        dislikes=["crime", "thieves", "troublemakers"],
    ),
    "innkeeper": NPCConfig(
        name="Hulda",
        role="Innkeeper",
        initial_affinity=0.5,
        initial_mood="Welcoming",
        personality_traits=["hospitable", "gossipy", "business-minded"],
        speech_style="warm, conversational",
        backstory="Owner of the Bannered Mare inn in Whiterun.",
        likes=["coin", "good stories", "regular customers"],
        dislikes=["trouble", "unpaid tabs"],
    ),
    "mage": NPCConfig(
        name="Farengar",
        role="Court Wizard",
        initial_affinity=0.2,
        initial_mood="Distracted",
        personality_traits=["arrogant", "obsessive", "knowledgeable"],
        speech_style="condescending, academic",
        backstory="Serves as court wizard to Jarl Balgruuf, obsessed with dragons.",
        likes=["magic", "artifacts", "research"],
        dislikes=["interruptions", "mundane tasks", "ignorance"],
        affinity_gain_rate=0.08,
    ),
}


def get_preset(name: str) -> Optional[NPCConfig]:
    """Get a built-in NPC preset by name."""
    return PRESETS.get(name.lower())


def list_presets() -> List[str]:
    """List available preset names."""
    return list(PRESETS.keys())


class ConfigManager:
    """
    Manages NPC configurations with preset + custom file support.
    
    Example:
        >>> manager = ConfigManager("./configs")
        >>> config = manager.get("lydia")  # Uses built-in preset
        >>> config = manager.get("custom_npc")  # Loads from ./configs/custom_npc.json
    """
    
    def __init__(self, config_dir: str = "./npc_configs"):
        """
        Initialize config manager.
        
        Args:
            config_dir: Directory for custom NPC configs
        """
        self.config_dir = config_dir
        self._cache: Dict[str, NPCConfig] = {}
    
    def get(self, name: str) -> Optional[NPCConfig]:
        """
        Get NPC config by name.
        
        Checks in order:
        1. Cache
        2. Custom file (config_dir/name.json or .yaml)
        3. Built-in presets
        
        Args:
            name: NPC name or preset name
            
        Returns:
            NPCConfig or None if not found
        """
        name_lower = name.lower()
        
        # Check cache
        if name_lower in self._cache:
            return self._cache[name_lower]
        
        # Check custom file
        for ext in [".json", ".yaml", ".yml"]:
            path = os.path.join(self.config_dir, f"{name_lower}{ext}")
            config = NPCConfig.load(path)
            if config:
                self._cache[name_lower] = config
                return config
        
        # Check presets
        preset = get_preset(name_lower)
        if preset:
            self._cache[name_lower] = preset
            return preset
        
        return None
    
    def save(self, config: NPCConfig, name: Optional[str] = None) -> str:
        """
        Save an NPC config to file.
        
        Args:
            config: The config to save
            name: Override name (defaults to config.name)
            
        Returns:
            Path where config was saved
        """
        name = name or config.name.lower()
        os.makedirs(self.config_dir, exist_ok=True)
        path = os.path.join(self.config_dir, f"{name}.json")
        config.save(path)
        self._cache[name.lower()] = config
        return path
    
    def list_available(self) -> List[str]:
        """List all available NPCs (presets + custom files)."""
        available = set(list_presets())
        
        if os.path.exists(self.config_dir):
            for f in os.listdir(self.config_dir):
                if f.endswith((".json", ".yaml", ".yml")):
                    available.add(os.path.splitext(f)[0])
        
        return sorted(available)
