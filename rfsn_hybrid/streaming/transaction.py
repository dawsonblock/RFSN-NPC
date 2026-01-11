"""
Stream transaction manager.

Manages the lifecycle of a streaming conversation:
1. FRAME_START opens transaction
2. FRAME_TEXT/AUDIO accumulates content
3. FRAME_COMMIT applies all state changes
4. FRAME_ABORT discards everything

No state is modified until commit.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Any

from .frames import (
    AnyFrame,
    Frame,
    FrameType,
    FrameStart,
    FrameText,
    FrameAudio,
    FrameCommit,
    FrameAbort,
    create_frame_commit,
    create_frame_abort,
)
from ..core.state.event_types import (
    StateEvent,
    EventType,
    transaction_begin_event,
    transaction_commit_event,
    transaction_abort_event,
    affinity_delta_event,
    mood_set_event,
    fact_add_event,
    turn_add_event,
)
from ..core.state.store import StateStore

logger = logging.getLogger(__name__)


@dataclass
class StreamTransaction:
    """
    Manages a single streaming transaction.
    
    Buffers all frames and state changes until commit.
    On abort, discards everything.
    
    Example:
        >>> txn = StreamTransaction("lydia", store)
        >>> txn.start("Hello Lydia!")
        >>> txn.add_text("Greetings, ")
        >>> txn.add_text("my Thane.")
        >>> txn.commit()  # Now state is updated
    """
    npc_id: str
    store: StateStore
    convo_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Internal state
    _seq: int = field(default=0, init=False)
    _started: bool = field(default=False, init=False)
    _committed: bool = field(default=False, init=False)
    _aborted: bool = field(default=False, init=False)
    _start_time: Optional[datetime] = field(default=None, init=False)
    
    # Accumulated content
    _text_buffer: List[str] = field(default_factory=list, init=False)
    _audio_chunks: List[bytes] = field(default_factory=list, init=False)
    _pending_events: List[StateEvent] = field(default_factory=list, init=False)
    _frames: List[AnyFrame] = field(default_factory=list, init=False)
    _metadata: Dict[str, Any] = field(default_factory=dict, init=False)
    
    # Callbacks
    _on_frame: Optional[Callable[[AnyFrame], None]] = field(default=None, init=False)
    
    @property
    def is_active(self) -> bool:
        """Transaction is started but not finished."""
        return self._started and not self._committed and not self._aborted
    
    @property
    def final_text(self) -> str:
        """Get accumulated text."""
        return "".join(self._text_buffer)
    
    def set_frame_callback(
        self, 
        callback: Callable[[AnyFrame], None],
    ) -> None:
        """Set callback for frame events (for logging/streaming)."""
        self._on_frame = callback
    
    def _next_seq(self) -> int:
        """Get next sequence number."""
        self._seq += 1
        return self._seq
    
    def _emit_frame(self, frame: AnyFrame) -> None:
        """Emit a frame and log it."""
        self._frames.append(frame)
        logger.debug(f"Frame: {frame.to_dict()}")
        
        if self._on_frame:
            try:
                self._on_frame(frame)
            except Exception as e:
                logger.warning(f"Frame callback error: {e}")
    
    def start(self, player_input: str) -> FrameStart:
        """
        Start the transaction.
        
        Args:
            player_input: The player's message
            
        Returns:
            FrameStart
        """
        if self._started:
            raise RuntimeError("Transaction already started")
        
        self._started = True
        self._start_time = datetime.now()
        
        # Begin transaction in store
        self.store.dispatch(transaction_begin_event(
            self.npc_id,
            self.convo_id,
        ))
        
        frame = FrameStart(
            convo_id=self.convo_id,
            npc_id=self.npc_id,
            seq=self._next_seq(),
            player_input=player_input,
        )
        self._emit_frame(frame)
        
        # Buffer player turn event
        self._pending_events.append(turn_add_event(
            self.npc_id,
            "user",
            player_input,
            self.convo_id,
        ))
        
        return frame
    
    def add_text(self, delta: str, is_final: bool = False) -> FrameText:
        """
        Add text to the buffer.
        
        Args:
            delta: Text fragment
            is_final: Whether this is the last fragment
            
        Returns:
            FrameText
        """
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._text_buffer.append(delta)
        
        frame = FrameText(
            convo_id=self.convo_id,
            npc_id=self.npc_id,
            seq=self._next_seq(),
            delta=delta,
            is_final=is_final,
        )
        self._emit_frame(frame)
        return frame
    
    def add_audio(self, audio_data: bytes, sample_rate: int = 22050) -> FrameAudio:
        """
        Add audio chunk to buffer.
        
        Args:
            audio_data: Raw audio bytes
            sample_rate: Audio sample rate
            
        Returns:
            FrameAudio
        """
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        chunk_id = len(self._audio_chunks)
        self._audio_chunks.append(audio_data)
        
        frame = FrameAudio(
            convo_id=self.convo_id,
            npc_id=self.npc_id,
            seq=self._next_seq(),
            chunk_id=chunk_id,
            audio_data=audio_data,
            sample_rate=sample_rate,
        )
        self._emit_frame(frame)
        return frame
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata that will be included in commit."""
        self._metadata[key] = value
    
    def queue_affinity_change(self, delta: float, reason: str = "") -> None:
        """Queue an affinity change (applied at commit)."""
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._pending_events.append(affinity_delta_event(
            self.npc_id,
            delta,
            reason,
            self.convo_id,
        ))
    
    def queue_mood_change(self, mood: str) -> None:
        """Queue a mood change (applied at commit)."""
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._pending_events.append(mood_set_event(
            self.npc_id,
            mood,
            self.convo_id,
        ))
    
    def queue_fact(self, text: str, tags: List[str], salience: float = 0.7) -> None:
        """Queue a new fact (applied at commit)."""
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._pending_events.append(fact_add_event(
            self.npc_id,
            text,
            tags,
            salience,
            self.convo_id,
        ))
    
    def commit(self) -> FrameCommit:
        """
        Commit the transaction - apply all state changes.
        
        This is the ONLY point where state is modified.
        
        Returns:
            FrameCommit with final text and metrics
        """
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._committed = True
        final_text = self.final_text
        
        # Calculate metrics
        elapsed_ms = 0.0
        if self._start_time:
            elapsed_ms = (datetime.now() - self._start_time).total_seconds() * 1000
        
        metrics = {
            "latency_ms": elapsed_ms,
            "text_frames": sum(1 for f in self._frames if isinstance(f, FrameText)),
            "audio_chunks": len(self._audio_chunks),
            "events_applied": len(self._pending_events),
            **self._metadata,
        }
        
        state_changes = {
            "events": [e.to_dict() for e in self._pending_events],
        }
        
        # Add assistant turn
        self._pending_events.append(turn_add_event(
            self.npc_id,
            "assistant",
            final_text,
            self.convo_id,
        ))
        
        # Apply all pending events through store
        for event in self._pending_events:
            self.store.dispatch(event)
        
        # Commit transaction
        self.store.dispatch(transaction_commit_event(
            self.npc_id,
            self.convo_id,
        ))
        
        frame = create_frame_commit(
            self.convo_id,
            self.npc_id,
            final_text,
            self._next_seq(),
            metrics,
            state_changes,
        )
        self._emit_frame(frame)
        
        logger.info(
            f"Transaction {self.convo_id} committed: "
            f"{len(final_text)} chars, {elapsed_ms:.1f}ms"
        )
        
        return frame
    
    def abort(self, reason: str, error_code: Optional[str] = None) -> FrameAbort:
        """
        Abort the transaction - discard all changes.
        
        State remains unchanged.
        
        Args:
            reason: Why the transaction was aborted
            error_code: Optional error code
            
        Returns:
            FrameAbort
        """
        if not self.is_active:
            raise RuntimeError("Transaction not active")
        
        self._aborted = True
        
        # Abort in store (discards buffered events)
        self.store.dispatch(transaction_abort_event(
            self.npc_id,
            self.convo_id,
            reason,
        ))
        
        frame = create_frame_abort(
            self.convo_id,
            self.npc_id,
            reason,
            self._next_seq(),
            error_code,
        )
        self._emit_frame(frame)
        
        logger.warning(
            f"Transaction {self.convo_id} aborted: {reason}. "
            f"Discarded {len(self._pending_events)} pending events"
        )
        
        return frame
    
    def get_frames(self) -> List[AnyFrame]:
        """Get all frames from this transaction."""
        return list(self._frames)
