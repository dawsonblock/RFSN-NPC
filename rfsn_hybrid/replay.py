"""
Dialogue replay and state diffing utilities.

Provides:
- DialogueTrace: Record of a conversation turn
- TraceRecorder: Append-only logger for traces
- StateDiff: Utility to compare RFSNState objects
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .types import RFSNState

logger = logging.getLogger(__name__)


@dataclass
class StateDiff:
    """Represents differences between two states."""
    old_state: Dict[str, Any]
    new_state: Dict[str, Any]
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)
    
    @classmethod
    def compute(cls, old: RFSNState, new: RFSNState) -> "StateDiff":
        """Compute diff between two states."""
        d_old = old.to_dict()
        d_new = new.to_dict()
        changes = {}
        
        for k, v in d_new.items():
            if k in d_old and d_old[k] != v:
                changes[k] = (d_old[k], v)
            elif k not in d_old:
                changes[k] = (None, v)
        
        return cls(old_state=d_old, new_state=d_new, changes=changes)
    
    def summary(self) -> str:
        """Human-readable summary of changes."""
        if not self.changes:
            return "No state changes."
        
        lines = ["State Changes:"]
        for k, (old, new) in self.changes.items():
            lines.append(f"  {k}: {old} -> {new}")
        return "\n".join(lines)


@dataclass
class DialogueTurn:
    """Single turn in a dialogue trace."""
    turn_id: int
    timestamp: str
    npc_id: str
    user_input: str
    npc_response: str
    state_diff: Optional[Dict] = None  # Serialized changes
    processing_time_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class TraceRecorder:
    """
    Records dialogue traces for replay and debugging.
    
    Example:
        >>> recorder = TraceRecorder("./traces")
        >>> recorder.start_session("lydia")
        >>> recorder.record_turn(...)
    """
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self._current_session: Optional[str] = None
        self._session_path: Optional[Path] = None
        self._turn_count = 0
        self._lock = threading.Lock()
    
    def start_session(self, npc_id: str, session_id: str = None) -> str:
        """Start a new recording session."""
        if not session_id:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = f"{npc_id}_{timestamp}"
        
        with self._lock:
            self._current_session = session_id
            self._session_path = self.base_path / f"{session_id}.jsonl"
            self._turn_count = 0
            
            # Write header
            header = {
                "type": "session_start",
                "session_id": session_id,
                "npc_id": npc_id,
                "timestamp": datetime.now().isoformat(),
            }
            self._write(header)
            
        logger.info(f"Started trace session: {session_id}")
        return session_id
    
    def record_turn(
        self,
        user_input: str,
        npc_response: str,
        old_state: Optional[RFSNState] = None,
        new_state: Optional[RFSNState] = None,
        processing_time_ms: float = 0.0,
    ) -> None:
        """Record a dialogue turn."""
        if not self._current_session:
            return
            
        with self._lock:
            self._turn_count += 1
            
            changes = None
            if old_state and new_state:
                diff = StateDiff.compute(old_state, new_state)
                changes = diff.changes
            
            turn = DialogueTurn(
                turn_id=self._turn_count,
                timestamp=datetime.now().isoformat(),
                npc_id=self._current_session.split("_")[0],
                user_input=user_input,
                npc_response=npc_response,
                state_diff=changes,
                processing_time_ms=processing_time_ms,
            )
            
            self._write({"type": "turn", "data": turn.to_dict()})
    
    def end_session(self) -> None:
        """End the current session."""
        if not self._current_session:
            return
            
        with self._lock:
            footer = {
                "type": "session_end",
                "timestamp": datetime.now().isoformat(),
                "total_turns": self._turn_count,
            }
            self._write(footer)
            
            self._current_session = None
            self._session_path = None
    
    def _write(self, data: Dict) -> None:
        """Append data to session file."""
        if not self._session_path:
            return
        
        try:
            with open(self._session_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            logger.error(f"Failed to write trace: {e}")
    
    def load_trace(self, session_id: str) -> List[Dict]:
        """Load a trace session."""
        path = self.base_path / f"{session_id}.jsonl"
        if not path.exists():
            return []
        
        events = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return events


# Global recorder instance
_recorder: Optional[TraceRecorder] = None


def get_trace_recorder(base_path: str = "./traces") -> TraceRecorder:
    """Get or create global trace recorder."""
    global _recorder
    if _recorder is None:
        _recorder = TraceRecorder(base_path)
    return _recorder
