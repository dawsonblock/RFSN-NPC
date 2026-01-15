"""
Learning configuration and feature flags.

Controls the behavior of the learning system through bounded,
safe parameters with sensible defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LearningConfig:
    """
    Configuration for the learning system.
    
    All parameters are bounded and have safe defaults.
    Learning is disabled by default for backward compatibility.
    
    Attributes:
        enabled: Master switch for learning (default: False)
        exploration_rate: Epsilon-greedy exploration probability (0.0 to 1.0)
        learning_rate: How quickly to update weights (0.0 to 1.0)
        max_pending: Maximum pending outcomes for eligibility trace
        snapshot_every_n_events: Save learner state every N events
        clamp_alpha: Limits update magnitude to prevent instability
        min_weight: Minimum action weight (prevents complete suppression)
        max_weight: Maximum action weight (prevents runaway amplification)
        max_entries: Maximum number of (context, action) pairs to track
        prng_seed: Seed for deterministic exploration (None = random)
    """
    # Master switch
    enabled: bool = False
    
    # Learning parameters
    exploration_rate: float = 0.05  # 5% exploration
    learning_rate: float = 0.05     # Slow, stable learning
    
    # Bounded storage
    max_pending: int = 50           # Eligibility trace queue size
    max_entries: int = 100          # Max (context, action) pairs
    
    # Persistence
    snapshot_every_n_events: int = 10
    
    # Stability constraints
    clamp_alpha: float = 0.2        # Max update per step
    min_weight: float = 0.5         # Prevent complete action suppression
    max_weight: float = 2.0         # Prevent runaway amplification
    
    # Determinism
    prng_seed: Optional[int] = None  # None = random, int = deterministic
    
    def __post_init__(self):
        """Validate and clamp all parameters to safe ranges."""
        self.exploration_rate = max(0.0, min(1.0, self.exploration_rate))
        self.learning_rate = max(0.0, min(1.0, self.learning_rate))
        self.max_pending = max(1, min(1000, self.max_pending))
        self.max_entries = max(1, min(10000, self.max_entries))
        self.snapshot_every_n_events = max(1, self.snapshot_every_n_events)
        self.clamp_alpha = max(0.01, min(1.0, self.clamp_alpha))
        self.min_weight = max(0.1, min(1.0, self.min_weight))
        self.max_weight = max(1.0, min(10.0, self.max_weight))
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "enabled": self.enabled,
            "exploration_rate": self.exploration_rate,
            "learning_rate": self.learning_rate,
            "max_pending": self.max_pending,
            "max_entries": self.max_entries,
            "snapshot_every_n_events": self.snapshot_every_n_events,
            "clamp_alpha": self.clamp_alpha,
            "min_weight": self.min_weight,
            "max_weight": self.max_weight,
            "prng_seed": self.prng_seed,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "LearningConfig":
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


# Default configuration instance
DEFAULT_LEARNING_CONFIG = LearningConfig()


# Safe tuning presets
class LearningPresets:
    """Pre-configured safe learning presets."""
    
    @staticmethod
    def disabled() -> LearningConfig:
        """Learning completely disabled (default)."""
        return LearningConfig(enabled=False)
    
    @staticmethod
    def conservative() -> LearningConfig:
        """Very slow, very safe learning."""
        return LearningConfig(
            enabled=True,
            exploration_rate=0.10,
            learning_rate=0.02,
            clamp_alpha=0.1,
        )
    
    @staticmethod
    def moderate() -> LearningConfig:
        """Balanced learning (recommended)."""
        return LearningConfig(
            enabled=True,
            exploration_rate=0.05,
            learning_rate=0.05,
            clamp_alpha=0.2,
        )
    
    @staticmethod
    def aggressive() -> LearningConfig:
        """Fast learning (use with caution)."""
        return LearningConfig(
            enabled=True,
            exploration_rate=0.15,
            learning_rate=0.10,
            clamp_alpha=0.3,
        )
    
    @staticmethod
    def deterministic_test(seed: int = 42) -> LearningConfig:
        """Deterministic configuration for testing."""
        return LearningConfig(
            enabled=True,
            exploration_rate=0.05,
            learning_rate=0.05,
            prng_seed=seed,
        )
