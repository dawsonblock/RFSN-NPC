"""
Persistence hooks for learning state.

Provides snapshot and restore functionality for the learning system
to support crash recovery and replay.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from .learning_config import LearningConfig
from .learning_state import LearningState
from .bandit import LinUCBBandit
from .feature_encoder import FeatureEncoder, FEATURE_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class LearningPersistence:
    """
    Handles persistence of learning state to disk.
    
    Features:
    - Atomic writes (temp file + rename)
    - Version compatibility checking
    - Graceful degradation on load failure
    """
    
    def __init__(self, base_path: str):
        """
        Initialize persistence handler.
        
        Args:
            base_path: Directory for storing learning state
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.event_counter = 0
    
    def snapshot(
        self,
        npc_id: str,
        config: LearningConfig,
        learning_state: LearningState,
        bandit: Optional[LinUCBBandit] = None,
    ) -> bool:
        """
        Save learning state to disk.
        
        Args:
            npc_id: NPC identifier
            config: Learning configuration
            learning_state: Learning state object
            bandit: Optional bandit learner
            
        Returns:
            True if save succeeded
        """
        try:
            snapshot_data = {
                "version": 1,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "npc_id": npc_id,
                "config": config.to_dict(),
                "learning_state": learning_state.to_dict(),
                "bandit": bandit.to_dict() if bandit else None,
                "event_counter": self.event_counter,
            }
            
            # Write to temp file first
            path = self._get_path(npc_id)
            temp_path = path.with_suffix(".tmp")
            
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(path)
            
            logger.debug(f"Learning state snapshot saved for {npc_id}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to save learning state for {npc_id}: {e}")
            return False
    
    def restore(
        self,
        npc_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Restore learning state from disk.
        
        Args:
            npc_id: NPC identifier
            
        Returns:
            Dictionary with restored state, or None if not found/invalid
        """
        path = self._get_path(npc_id)
        
        if not path.exists():
            logger.debug(f"No saved learning state found for {npc_id}")
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Version compatibility check
            version = data.get("version", 1)
            if version != 1:
                logger.warning(f"Incompatible learning state version: {version}")
                return None
            
            # Feature schema compatibility check
            schema_version = data.get("feature_schema_version", 1)
            if schema_version != FEATURE_SCHEMA_VERSION:
                logger.warning(
                    f"Feature schema mismatch: saved={schema_version}, "
                    f"current={FEATURE_SCHEMA_VERSION}. "
                    f"Learning state will be reset."
                )
                return None
            
            self.event_counter = data.get("event_counter", 0)
            logger.debug(f"Learning state restored for {npc_id}")
            return data
            
        except Exception as e:
            logger.warning(f"Failed to restore learning state for {npc_id}: {e}")
            return None
    
    def should_snapshot(self, config: LearningConfig) -> bool:
        """
        Check if it's time to take a snapshot.
        
        Args:
            config: Learning configuration
            
        Returns:
            True if snapshot should be taken
        """
        self.event_counter += 1
        return (self.event_counter % config.snapshot_every_n_events) == 0
    
    def _get_path(self, npc_id: str) -> Path:
        """Get file path for NPC learning state."""
        safe_id = "".join(c if c.isalnum() else "_" for c in npc_id)
        return self.base_path / f"{safe_id}_learning.json"
    
    def delete(self, npc_id: str) -> bool:
        """
        Delete saved learning state for an NPC.
        
        Args:
            npc_id: NPC identifier
            
        Returns:
            True if deletion succeeded or file didn't exist
        """
        path = self._get_path(npc_id)
        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Deleted learning state for {npc_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to delete learning state for {npc_id}: {e}")
            return False


def restore_learning_components(
    npc_id: str,
    persistence: LearningPersistence,
) -> tuple[LearningConfig, LearningState, Optional[LinUCBBandit]]:
    """
    Restore all learning components from disk.
    
    Args:
        npc_id: NPC identifier
        persistence: Persistence handler
        
    Returns:
        Tuple of (config, learning_state, bandit)
        Returns defaults if restoration fails
    """
    data = persistence.restore(npc_id)
    
    if data is None:
        # Return defaults
        config = LearningConfig()
        learning_state = LearningState(enabled=False)
        return config, learning_state, None
    
    try:
        # Restore config
        config = LearningConfig.from_dict(data.get("config", {}))
        
        # Restore learning state
        learning_state_data = data.get("learning_state", {})
        learning_state = LearningState(
            enabled=learning_state_data.get("enabled", False),
            max_entries=learning_state_data.get("max_entries", 100),
        )
        
        # Restore weights
        for weight_data in learning_state_data.get("weights", []):
            from .learning_state import ActionWeight
            weight = ActionWeight.from_dict(weight_data)
            key = (weight.context_key, weight.action)
            learning_state.weights[key] = weight
            learning_state.access_order.append(key)
        
        # Restore bandit if present
        bandit = None
        bandit_data = data.get("bandit")
        if bandit_data:
            bandit = LinUCBBandit.from_dict(bandit_data, prng_seed=config.prng_seed)
        
        return config, learning_state, bandit
        
    except Exception as e:
        logger.warning(f"Error restoring learning components: {e}")
        # Return defaults on error
        config = LearningConfig()
        learning_state = LearningState(enabled=False)
        return config, learning_state, None
