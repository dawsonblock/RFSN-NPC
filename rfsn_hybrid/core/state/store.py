"""
Optimized state store with snapshot caching.

Key optimizations:
- Cached snapshots (only regenerate on state change)
- Reduced lock contention
- Batch event support
"""
from __future__ import annotations

import copy
import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Deque, Dict, List, Optional

from .event_types import StateEvent, EventType
from .reducer import reduce_state
from ...types import RFSNState
from ...storage import Fact

logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Buffered transaction awaiting commit or abort."""
    convo_id: str
    npc_id: str
    events: List[StateEvent] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


class StateStore:
    """
    Optimized state store with event sourcing and snapshot caching.
    
    Performance optimizations:
    - Snapshot caching (avoids repeated deep copies)
    - Dirty flag tracking
    - Batch event dispatch
    """
    
    __slots__ = (
        '_state', '_facts', '_lock', '_seq', '_max_event_log',
        '_event_log', '_transactions', '_subscribers',
        '_snapshot_cache', '_snapshot_dirty', '_facts_cache', '_facts_dirty'
    )
    
    def __init__(
        self,
        initial_state: RFSNState,
        initial_facts: Optional[List[Fact]] = None,
        max_event_log: int = 1000,
    ):
        self._state = initial_state  # No initial deep copy needed
        self._facts: List[Fact] = initial_facts if initial_facts else []
        self._lock = threading.RLock()
        self._seq = 0
        self._max_event_log = max_event_log
        
        self._event_log: Deque[StateEvent] = deque(maxlen=max_event_log)
        self._transactions: Dict[str, Transaction] = {}
        self._subscribers: List[Callable[[RFSNState, StateEvent], None]] = []
        
        # Snapshot caching
        self._snapshot_cache: Optional[RFSNState] = None
        self._snapshot_dirty = True
        self._facts_cache: Optional[List[Fact]] = None
        self._facts_cache: Optional[List[Fact]] = None
        self._facts_dirty = True
        
    @property
    def state(self) -> RFSNState:
        """Current state snapshot."""
        with self._lock:
            return self._state

    @property
    def facts(self) -> List[Fact]:
        """Current facts."""
        with self._lock:
            return list(self._facts)

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Retrieve conversation history from event log."""
        with self._lock:
            # Filter for chat events
            history = []
            for event in self._event_log:
                if event.event_type == EventType.FACT_ADD:
                    tags = event.payload.get("tags", [])
                    if "chat" in tags:
                        # Determine role
                        role = "npc" if "npc" in tags else "user"
                        # Extract content (strip prefix "Name: ")
                        text = event.payload.get("text", "")
                        if ": " in text:
                            _, content = text.split(": ", 1)
                        else:
                            content = text
                            
                        history.append({
                            "role": role,
                            "content": content,
                            "timestamp": event.timestamp
                        })
            return history[-limit:]
    
    def dispatch(self, event: StateEvent) -> bool:
        """Dispatch an event to modify state."""
        with self._lock:
            self._seq += 1
            event = StateEvent(
                event_type=event.event_type,
                npc_id=event.npc_id,
                payload=event.payload,
                timestamp=event.timestamp,
                seq=self._seq,
                convo_id=event.convo_id,
                source=event.source,
            )
            
            self._event_log.append(event)
            
            if event.event_type == EventType.TRANSACTION_BEGIN:
                self._begin_transaction(event)
                return False
            elif event.event_type == EventType.TRANSACTION_COMMIT:
                return self._commit_transaction(event)
            elif event.event_type == EventType.TRANSACTION_ABORT:
                self._abort_transaction(event)
                return False
            
            if event.convo_id and event.convo_id in self._transactions:
                self._transactions[event.convo_id].events.append(event)
                return False
            
            return self._apply_event(event)
    
    def dispatch_batch(self, events: List[StateEvent]) -> int:
        """Dispatch multiple events efficiently. Returns count applied."""
        applied = 0
        with self._lock:
            for event in events:
                if self.dispatch(event):
                    applied += 1
        return applied
    
    def _apply_event(self, event: StateEvent) -> bool:
        """Apply event and invalidate caches."""
        try:
            new_state, new_facts, _ = reduce_state(
                self._state, event, self._facts
            )
            
            # Update state and invalidate caches
            if new_state is not self._state:
                self._state = new_state
                self._snapshot_dirty = True
            
            if new_facts is not self._facts:
                self._facts = new_facts
                self._facts_dirty = True
            
            # Notify subscribers
            for sub in self._subscribers:
                try:
                    sub(self._state, event)
                except Exception as e:
                    logger.warning(f"Subscriber error: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply event: {e}")
            return False
    
    def _begin_transaction(self, event: StateEvent) -> None:
        convo_id = event.convo_id or str(uuid.uuid4())
        if convo_id not in self._transactions:
            self._transactions[convo_id] = Transaction(
                convo_id=convo_id,
                npc_id=event.npc_id,
            )
    
    def _commit_transaction(self, event: StateEvent) -> bool:
        convo_id = event.convo_id
        if not convo_id or convo_id not in self._transactions:
            return False
        
        txn = self._transactions.pop(convo_id)
        for buffered in txn.events:
            self._apply_event(buffered)
        return True
    
    def _abort_transaction(self, event: StateEvent) -> None:
        convo_id = event.convo_id
        if convo_id:
            self._transactions.pop(convo_id, None)
    
    def get_snapshot(self) -> RFSNState:
        """
        Get cached read-only copy of state.
        
        Only creates new copy if state has changed since last call.
        """
        with self._lock:
            if self._snapshot_dirty or self._snapshot_cache is None:
                self._snapshot_cache = copy.deepcopy(self._state)
                self._snapshot_dirty = False
            return self._snapshot_cache
    
    def get_facts_snapshot(self) -> List[Fact]:
        """Get cached read-only copy of facts."""
        with self._lock:
            if self._facts_dirty or self._facts_cache is None:
                self._facts_cache = copy.deepcopy(self._facts)
                self._facts_dirty = False
            return self._facts_cache
    
    def get_state_direct(self) -> RFSNState:
        """
        Get direct reference to state (no copy).
        
        WARNING: Only use for read operations. Do not modify.
        """
        with self._lock:
            return self._state
    
    def get_event_log(self, n: Optional[int] = None) -> List[StateEvent]:
        with self._lock:
            events = list(self._event_log)
            return events[-n:] if n else events
    
    def subscribe(
        self,
        callback: Callable[[RFSNState, StateEvent], None],
    ) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)
        
        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        return unsubscribe
    
    def has_active_transaction(self, convo_id: str) -> bool:
        with self._lock:
            return convo_id in self._transactions
    
    def get_pending_event_count(self, convo_id: str) -> int:
        with self._lock:
            txn = self._transactions.get(convo_id)
            return len(txn.events) if txn else 0


# Global store registry
_global_stores: Dict[str, StateStore] = {}


def get_store(npc_id: str) -> Optional[StateStore]:
    return _global_stores.get(npc_id)


def create_store(
    npc_id: str,
    initial_state: RFSNState,
    initial_facts: Optional[List[Fact]] = None,
) -> StateStore:
    store = StateStore(initial_state, initial_facts)
    _global_stores[npc_id] = store
    return store


def remove_store(npc_id: str) -> None:
    _global_stores.pop(npc_id, None)
