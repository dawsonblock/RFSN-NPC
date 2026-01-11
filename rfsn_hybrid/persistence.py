"""
Crash-resilient state persistence.

Provides:
- File-based state snapshots
- State recovery on restart
- NPC memory persistence across crashes
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .types import RFSNState
from .storage import Fact

logger = logging.getLogger(__name__)


class StateSnapshot:
    """
    Persists NPC state to disk for crash recovery.
    
    Features:
    - Atomic writes (temp file + rename)
    - Automatic backups
    - Periodic auto-save
    - Recovery on startup
    
    Example:
        >>> snapshot = StateSnapshot("./state")
        >>> snapshot.save("lydia", state, facts, memory)
        >>> # After crash:
        >>> state, facts, memory = snapshot.load("lydia")
    """
    
    BACKUP_COUNT = 3  # Keep N backups
    
    def __init__(self, base_path: str, auto_save_interval: float = 30.0):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.auto_save_interval = auto_save_interval
        self._dirty: Dict[str, bool] = {}
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # Auto-save thread
        self._running = False
        self._save_thread: Optional[threading.Thread] = None
    
    def start_auto_save(self) -> None:
        """Start background auto-save thread."""
        self._running = True
        self._save_thread = threading.Thread(
            target=self._auto_save_loop,
            daemon=True,
            name="state-autosave",
        )
        self._save_thread.start()
        logger.info(f"Auto-save started (interval: {self.auto_save_interval}s)")
    
    def stop_auto_save(self) -> None:
        """Stop auto-save and flush pending writes."""
        self._running = False
        if self._save_thread:
            self._save_thread.join(timeout=5.0)
        self._flush_all()
    
    def _auto_save_loop(self) -> None:
        """Background loop for periodic saves."""
        while self._running:
            time.sleep(self.auto_save_interval)
            self._flush_all()
    
    def _flush_all(self) -> None:
        """Save all dirty state to disk."""
        with self._lock:
            for npc_id, is_dirty in list(self._dirty.items()):
                if is_dirty and npc_id in self._cache:
                    self._write_to_disk(npc_id, self._cache[npc_id])
                    self._dirty[npc_id] = False
    
    def _get_path(self, npc_id: str) -> Path:
        """Get file path for NPC state."""
        safe_id = "".join(c if c.isalnum() else "_" for c in npc_id)
        return self.base_path / f"{safe_id}.json"
    
    def _get_backup_path(self, npc_id: str, n: int) -> Path:
        """Get backup file path."""
        safe_id = "".join(c if c.isalnum() else "_" for c in npc_id)
        return self.base_path / f"{safe_id}.backup{n}.json"
    
    def save(
        self,
        npc_id: str,
        state: RFSNState,
        facts: Optional[List[Fact]] = None,
        memory_turns: Optional[List[Dict]] = None,
        immediate: bool = False,
    ) -> None:
        """
        Save NPC state snapshot.
        
        Args:
            npc_id: NPC identifier
            state: Current NPC state
            facts: Optional facts list
            memory_turns: Optional conversation history
            immediate: If True, write to disk immediately
        """
        data = {
            "npc_id": npc_id,
            "timestamp": datetime.now().isoformat(),
            "state": state.to_dict(),
            "facts": [asdict(f) for f in facts] if facts else [],
            "memory": memory_turns or [],
        }
        
        with self._lock:
            self._cache[npc_id] = data
            self._dirty[npc_id] = True
        
        if immediate:
            self._write_to_disk(npc_id, data)
            with self._lock:
                self._dirty[npc_id] = False
    
    def _write_to_disk(self, npc_id: str, data: Dict) -> None:
        """Atomically write state to disk with backup rotation."""
        path = self._get_path(npc_id)
        temp_path = path.with_suffix(".tmp")
        
        try:
            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            # Rotate backups
            if path.exists():
                self._rotate_backups(npc_id)
            
            # Atomic rename
            shutil.move(str(temp_path), str(path))
            logger.debug(f"Saved state for {npc_id}")
            
        except Exception as e:
            logger.error(f"Failed to save state for {npc_id}: {e}")
            if temp_path.exists():
                temp_path.unlink()
    
    def _rotate_backups(self, npc_id: str) -> None:
        """Rotate backup files."""
        path = self._get_path(npc_id)
        
        # Delete oldest backup
        oldest = self._get_backup_path(npc_id, self.BACKUP_COUNT)
        if oldest.exists():
            oldest.unlink()
        
        # Shift backups
        for i in range(self.BACKUP_COUNT - 1, 0, -1):
            src = self._get_backup_path(npc_id, i)
            dst = self._get_backup_path(npc_id, i + 1)
            if src.exists():
                shutil.move(str(src), str(dst))
        
        # Current becomes backup1
        backup1 = self._get_backup_path(npc_id, 1)
        shutil.copy2(str(path), str(backup1))
    
    def load(self, npc_id: str) -> Optional[Dict]:
        """
        Load NPC state from disk.
        
        Returns:
            Dict with 'state', 'facts', 'memory', or None if not found
        """
        # Check cache first
        with self._lock:
            if npc_id in self._cache:
                return self._cache[npc_id]
        
        path = self._get_path(npc_id)
        
        if not path.exists():
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            with self._lock:
                self._cache[npc_id] = data
                self._dirty[npc_id] = False
            
            logger.info(f"Loaded state for {npc_id} (saved: {data.get('timestamp', 'unknown')})")
            return data
            
        except Exception as e:
            logger.error(f"Failed to load state for {npc_id}: {e}")
            return self._try_recover_from_backup(npc_id)
    
    def _try_recover_from_backup(self, npc_id: str) -> Optional[Dict]:
        """Attempt recovery from backup files."""
        for i in range(1, self.BACKUP_COUNT + 1):
            backup_path = self._get_backup_path(npc_id, i)
            if backup_path.exists():
                try:
                    with open(backup_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    logger.warning(f"Recovered {npc_id} from backup{i}")
                    return data
                except Exception:
                    continue
        
        logger.error(f"No valid backup found for {npc_id}")
        return None
    
    def recover_state(self, npc_id: str) -> Optional[RFSNState]:
        """
        Recover just the RFSNState object.
        
        Convenience method for crash recovery.
        """
        data = self.load(npc_id)
        if data and "state" in data:
            try:
                return RFSNState.from_dict(data["state"])
            except Exception as e:
                logger.error(f"Failed to deserialize state: {e}")
        return None
    
    def list_npcs(self) -> List[str]:
        """List all NPCs with saved state."""
        npcs = []
        for path in self.base_path.glob("*.json"):
            if not path.name.startswith(".") and "backup" not in path.name:
                npcs.append(path.stem)
        return npcs
    
    def delete(self, npc_id: str) -> None:
        """Delete state for an NPC."""
        with self._lock:
            self._cache.pop(npc_id, None)
            self._dirty.pop(npc_id, None)
        
        path = self._get_path(npc_id)
        if path.exists():
            path.unlink()
        
        # Delete backups too
        for i in range(1, self.BACKUP_COUNT + 1):
            backup = self._get_backup_path(npc_id, i)
            if backup.exists():
                backup.unlink()
    
    def stats(self) -> Dict:
        """Get snapshot statistics."""
        return {
            "base_path": str(self.base_path),
            "cached_npcs": len(self._cache),
            "dirty_count": sum(1 for v in self._dirty.values() if v),
            "saved_npcs": len(self.list_npcs()),
            "auto_save_running": self._running,
        }


# Global snapshot instance
_snapshot: Optional[StateSnapshot] = None


def get_state_snapshot(base_path: str = "./npc_state") -> StateSnapshot:
    """Get or create global state snapshot manager."""
    global _snapshot
    if _snapshot is None:
        _snapshot = StateSnapshot(base_path)
    return _snapshot
