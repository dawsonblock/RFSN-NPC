"""
FRAME protocol for transactional streaming.

All streaming output is organized into frames:
- FRAME_START: Begin a new stream
- FRAME_TEXT: Incremental text delta  
- FRAME_AUDIO: Audio chunk (if using TTS)
- FRAME_COMMIT: Finalize and apply state changes
- FRAME_ABORT: Cancel and discard all changes

State changes only happen at FRAME_COMMIT.
If anything fails, FRAME_ABORT discards all pending changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class FrameType(str, Enum):
    """Types of stream frames."""
    START = "start"
    TEXT = "text"
    AUDIO = "audio"
    COMMIT = "commit"
    ABORT = "abort"
    METADATA = "metadata"


@dataclass(frozen=True)
class Frame:
    """
    Base frame in the streaming protocol.
    
    All frames are immutable and contain:
    - convo_id: Unique conversation identifier
    - npc_id: Target NPC
    - seq: Sequence number for ordering
    - timestamp: When frame was created
    """
    frame_type: FrameType
    convo_id: str
    npc_id: str
    seq: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/transmission."""
        return {
            "frame_type": self.frame_type.value,
            "convo_id": self.convo_id,
            "npc_id": self.npc_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class FrameStart(Frame):
    """
    Start a new streaming session.
    
    Opens a transaction - no state changes until commit.
    """
    frame_type: FrameType = field(default=FrameType.START, init=False)
    player_input: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["player_input"] = self.player_input
        return d


@dataclass(frozen=True)
class FrameText(Frame):
    """
    Incremental text from the generator.
    
    Accumulated text is buffered until commit.
    """
    frame_type: FrameType = field(default=FrameType.TEXT, init=False)
    delta: str = ""
    is_final: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["delta"] = self.delta
        d["is_final"] = self.is_final
        return d


@dataclass(frozen=True)
class FrameAudio(Frame):
    """
    Audio chunk for TTS playback.
    
    Audio is queued until commit, then played.
    """
    frame_type: FrameType = field(default=FrameType.AUDIO, init=False)
    chunk_id: int = 0
    audio_data: bytes = field(default=b"", repr=False)
    sample_rate: int = 22050
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["chunk_id"] = self.chunk_id
        d["audio_bytes"] = len(self.audio_data)
        d["sample_rate"] = self.sample_rate
        return d


@dataclass(frozen=True)
class FrameCommit(Frame):
    """
    Commit the stream - apply all state changes.
    
    Contains:
    - final_text: Complete generated response
    - metrics: Timing and performance data
    - state_changes: What will be applied
    """
    frame_type: FrameType = field(default=FrameType.COMMIT, init=False)
    final_text: str = ""
    metrics: Dict[str, Any] = field(default_factory=dict)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["final_text"] = self.final_text
        d["metrics"] = self.metrics
        d["state_changes"] = self.state_changes
        return d


@dataclass(frozen=True)
class FrameAbort(Frame):
    """
    Abort the stream - discard all changes.
    
    Used when:
    - Generator fails
    - TTS fails
    - User interrupts
    - Timeout
    """
    frame_type: FrameType = field(default=FrameType.ABORT, init=False)
    reason: str = ""
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["reason"] = self.reason
        d["error_code"] = self.error_code
        return d


@dataclass(frozen=True)
class FrameMetadata(Frame):
    """
    Metadata update (non-text content).
    
    Used for:
    - Event classification results
    - Fact retrieval info
    - Debug data
    """
    frame_type: FrameType = field(default=FrameType.METADATA, init=False)
    key: str = ""
    value: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["key"] = self.key
        d["value"] = self.value
        return d


# Type alias for any frame
from typing import Union
AnyFrame = Union[FrameStart, FrameText, FrameAudio, FrameCommit, FrameAbort, FrameMetadata]


def create_frame_start(
    convo_id: str,
    npc_id: str,
    player_input: str,
    seq: int = 0,
) -> FrameStart:
    """Create a stream start frame."""
    return FrameStart(
        convo_id=convo_id,
        npc_id=npc_id,
        seq=seq,
        player_input=player_input,
    )


def create_frame_text(
    convo_id: str,
    npc_id: str,
    delta: str,
    seq: int,
    is_final: bool = False,
) -> FrameText:
    """Create a text delta frame."""
    return FrameText(
        convo_id=convo_id,
        npc_id=npc_id,
        seq=seq,
        delta=delta,
        is_final=is_final,
    )


def create_frame_commit(
    convo_id: str,
    npc_id: str,
    final_text: str,
    seq: int,
    metrics: Optional[Dict] = None,
    state_changes: Optional[Dict] = None,
) -> FrameCommit:
    """Create a commit frame."""
    return FrameCommit(
        convo_id=convo_id,
        npc_id=npc_id,
        seq=seq,
        final_text=final_text,
        metrics=metrics or {},
        state_changes=state_changes or {},
    )


def create_frame_abort(
    convo_id: str,
    npc_id: str,
    reason: str,
    seq: int,
    error_code: Optional[str] = None,
) -> FrameAbort:
    """Create an abort frame."""
    return FrameAbort(
        convo_id=convo_id,
        npc_id=npc_id,
        seq=seq,
        reason=reason,
        error_code=error_code,
    )
