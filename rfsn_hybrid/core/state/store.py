"""
State store with event queue and transaction support.

The store is the single writer for all state mutations.
All writes go through dispatch(), all reads through get_snapshot().

This prevents race conditions by:
- Queueing all events
- Processing in order
- Providing read-only snapshots
"""
from __future__ import annotations

import copy
import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Deque, Dict, List, Optional, Set

from .event_types import (
    StateEvent,
    EventType,
    transaction_begin_event,
    transaction_commit_event,
    transaction_abort_event,
)
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
    Central state store with event sourcing.
    
    All state mutations go through this store:
    - dispatch(event) queues an event for processing
    - get_snapshot() returns a read-only copy of current state
    
    Features:
    - Thread-safe
    - Transaction support (buffer until commit)
    - Event logging for replay
    - Subscriber notifications
    
    Example:
        >>> store = StateStore(initial_state)
        >>> store.dispatch(affinity_delta_event("lydia", 0.1))
        >>> snapshot = store.get_snapshot()
    """
    
    def __init__(
        self,
        initial_state: RFSNState,
        initial_facts: Optional[List[Fact]] = None,
        max_event_log: int = 1000,
    ):
        """
        Initialize the store.
        
        Args:
            initial_state: Starting NPC state
            initial_facts: Starting facts list
            max_event_log: Max events to keep in log (for replay)
        """
        self._state = copy.deepcopy(initial_state)
        self._facts = copy.deepcopy(initial_facts) if initial_facts else []
        self._lock = threading.RLock()
        self._seq = 0
        self._max_event_log = max_event_log
        
        # Event log for replay/debugging
        self._event_log: Deque[StateEvent] = deque(maxlen=max_event_log)
        
        # Active transactions (keyed by convo_id)
        self._transactions: Dict[str, Transaction] = {}
        
        # Subscribers for state changes
        self._subscribers: List[Callable[[RFSNState, StateEvent], None]] = []
    
    def dispatch(self, event: StateEvent) -> bool:
        """
        Dispatch an event to modify state.
        
        This is the ONLY way to modify state.
        
        Args:
            event: The event to dispatch
            
        Returns:
            True if event was applied, False if buffered in transaction
        """
        with self._lock:
            # Assign sequence number
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
            
            # Log event
            self._event_log.append(event)
            
            # Handle transaction control events
            if event.event_type == EventType.TRANSACTION_BEGIN:
                self._begin_transaction(event)
                return False
                
            elif event.event_type == EventType.TRANSACTION_COMMIT:
                return self._commit_transaction(event)
                
            elif event.event_type == EventType.TRANSACTION_ABORT:
                self._abort_transaction(event)
                return False
            
            # Check if event belongs to active transaction
            if event.convo_id and event.convo_id in self._transactions:
                # Buffer in transaction
                self._transactions[event.convo_id].events.append(event)
                logger.debug(f"Buffered event in transaction {event.convo_id}")
                return False
            
            # Apply immediately
            return self._apply_event(event)
    
    def _apply_event(self, event: StateEvent) -> bool:
        """Apply a single event to state (internal, with lock held)."""
        try:
            new_state, new_facts, _ = reduce_state(
                self._state, event, self._facts
            )
            self._state = new_state
            if new_facts is not None:
                self._facts = new_facts
            
            # Notify subscribers
            for sub in self._subscribers:
                try:
                    sub(self._state, event)
                except Exception as e:
                    logger.warning(f"Subscriber error: {e}")
            
            logger.debug(f"Applied event: {event.event_type.value} seq={event.seq}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply event {event.event_type}: {e}")
            return False
    
    def _begin_transaction(self, event: StateEvent) -> None:
        """Start a new transaction."""
        convo_id = event.convo_id or str(uuid.uuid4())
        
        if convo_id in self._transactions:
            logger.warning(f"Transaction {convo_id} already active, ignoring begin")
            return
        
        self._transactions[convo_id] = Transaction(
            convo_id=convo_id,
            npc_id=event.npc_id,
        )
        logger.info(f"Transaction {convo_id} started")
    
    def _commit_transaction(self, event: StateEvent) -> bool:
        """Commit a transaction, applying all buffered events."""
        convo_id = event.convo_id
        if not convo_id or convo_id not in self._transactions:
            logger.warning(f"No transaction {convo_id} to commit")
            return False
        
        txn = self._transactions.pop(convo_id)
        logger.info(f"Committing transaction {convo_id} with {len(txn.events)} events")
        
        # Apply all buffered events
        for buffered_event in txn.events:
            self._apply_event(buffered_event)
        
        return True
    
    def _abort_transaction(self, event: StateEvent) -> None:
        """Abort a transaction, discarding all buffered events."""
        convo_id = event.convo_id
        if not convo_id or convo_id not in self._transactions:
            logger.warning(f"No transaction {convo_id} to abort")
            return
        
        txn = self._transactions.pop(convo_id)
        reason = event.payload.get("reason", "unknown")
        logger.warning(
            f"Aborted transaction {convo_id}: {reason}. "
            f"Discarded {len(txn.events)} events"
        )
    
    def get_snapshot(self) -> RFSNState:
        """
        Get a read-only copy of current state.
        
        This is the ONLY way to read state.
        The returned object is a deep copy - safe to use without locks.
        """
        with self._lock:
            return copy.deepcopy(self._state)
    
    def get_facts_snapshot(self) -> List[Fact]:
        """Get a read-only copy of current facts."""
        with self._lock:
            return copy.deepcopy(self._facts)
    
    def get_event_log(self, n: Optional[int] = None) -> List[StateEvent]:
        """Get recent events from log."""
        with self._lock:
            events = list(self._event_log)
            if n is not None:
                events = events[-n:]
            return events
    
    def subscribe(
        self,
        callback: Callable[[RFSNState, StateEvent], None],
    ) -> Callable[[], None]:
        """
        Subscribe to state changes.
        
        Args:
            callback: Called with (new_state, event) after each mutation
            
        Returns:
            Unsubscribe function
        """
        with self._lock:
            self._subscribers.append(callback)
        
        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        
        return unsubscribe
    
    def has_active_transaction(self, convo_id: str) -> bool:
        """Check if a transaction is active."""
        with self._lock:
            return convo_id in self._transactions
    
    def get_pending_event_count(self, convo_id: str) -> int:
        """Get number of events pending in a transaction."""
        with self._lock:
            if convo_id in self._transactions:
                return len(self._transactions[convo_id].events)
            return 0


# Global store instance (optional - can create per-NPC stores)
_global_stores: Dict[str, StateStore] = {}


def get_store(npc_id: str) -> Optional[StateStore]:
    """Get the store for an NPC."""
    return _global_stores.get(npc_id)


def create_store(
    npc_id: str,
    initial_state: RFSNState,
    initial_facts: Optional[List[Fact]] = None,
) -> StateStore:
    """Create or replace a store for an NPC."""
    store = StateStore(initial_state, initial_facts)
    _global_stores[npc_id] = store
    return store


def remove_store(npc_id: str) -> None:
    """Remove a store."""
    _global_stores.pop(npc_id, None)
