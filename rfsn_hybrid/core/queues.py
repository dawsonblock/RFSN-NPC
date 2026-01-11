"""
Bounded queues with backpressure handling.

Prevents runaway latency and memory growth by:
- Limiting queue size
- Dropping items on overflow
- Logging drops for metrics
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Deque, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DropPolicy(str, Enum):
    """Policy for handling overflow."""
    OLDEST = "oldest"   # Drop oldest item when full
    NEWEST = "newest"   # Drop incoming item when full
    BLOCK = "block"     # Block until space available


@dataclass
class DropEvent:
    """Record of a dropped item."""
    stage: str
    timestamp: str
    policy: DropPolicy
    queue_size: int
    item_type: str
    
    def to_dict(self):
        return {
            "stage": self.stage,
            "timestamp": self.timestamp,
            "policy": self.policy.value,
            "queue_size": self.queue_size,
            "item_type": self.item_type,
        }


class BoundedQueue(Generic[T]):
    """
    Thread-safe bounded queue with configurable overflow handling.
    
    Used between pipeline stages to prevent backpressure issues:
    - Generator → Sentence splitter
    - Splitter → TTS
    - TTS → Audio playback
    
    Example:
        >>> q = BoundedQueue[str](maxsize=3, stage="generator")
        >>> q.put("hello")  # True
        >>> q.put("world")  # True
        >>> q.put("!")      # True
        >>> q.put("drop")   # False (oldest dropped)
    """
    
    def __init__(
        self,
        maxsize: int = 3,
        drop_policy: DropPolicy = DropPolicy.OLDEST,
        stage: str = "unknown",
        on_drop: Optional[Callable[[DropEvent], None]] = None,
    ):
        """
        Initialize bounded queue.
        
        Args:
            maxsize: Maximum items in queue
            drop_policy: What to do when full
            stage: Name for logging/metrics
            on_drop: Callback when item is dropped
        """
        self.maxsize = maxsize
        self.drop_policy = drop_policy
        self.stage = stage
        self.on_drop = on_drop
        
        self._queue: Deque[T] = deque(maxlen=None)  # We manage size manually
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        
        # Metrics
        self._put_count = 0
        self._get_count = 0
        self._drop_count = 0
        self._drops: List[DropEvent] = []
    
    def put(self, item: T, timeout: Optional[float] = None) -> bool:
        """
        Add item to queue.
        
        Args:
            item: Item to add
            timeout: Max seconds to wait (for BLOCK policy)
            
        Returns:
            True if added, False if dropped
        """
        with self._lock:
            self._put_count += 1
            
            if len(self._queue) >= self.maxsize:
                if self.drop_policy == DropPolicy.OLDEST:
                    # Drop oldest, add new
                    dropped = self._queue.popleft()
                    self._record_drop(type(dropped).__name__)
                    self._queue.append(item)
                    self._not_empty.notify()
                    return True
                    
                elif self.drop_policy == DropPolicy.NEWEST:
                    # Drop incoming
                    self._record_drop(type(item).__name__)
                    return False
                    
                elif self.drop_policy == DropPolicy.BLOCK:
                    # Wait for space
                    if not self._not_full.wait(timeout):
                        return False
            
            self._queue.append(item)
            self._not_empty.notify()
            return True
    
    def get(self, timeout: Optional[float] = None) -> Optional[T]:
        """
        Get item from queue.
        
        Args:
            timeout: Max seconds to wait
            
        Returns:
            Item or None if timeout
        """
        with self._lock:
            if not self._queue:
                if not self._not_empty.wait(timeout):
                    return None
                if not self._queue:
                    return None
            
            self._get_count += 1
            item = self._queue.popleft()
            self._not_full.notify()
            return item
    
    def get_nowait(self) -> Optional[T]:
        """Get item without waiting."""
        with self._lock:
            if self._queue:
                self._get_count += 1
                item = self._queue.popleft()
                self._not_full.notify()
                return item
            return None
    
    def _record_drop(self, item_type: str) -> None:
        """Record a drop event."""
        self._drop_count += 1
        
        event = DropEvent(
            stage=self.stage,
            timestamp=datetime.now().isoformat(),
            policy=self.drop_policy,
            queue_size=len(self._queue),
            item_type=item_type,
        )
        self._drops.append(event)
        
        logger.warning(
            f"Queue {self.stage}: dropped {item_type} "
            f"(policy={self.drop_policy.value}, size={len(self._queue)})"
        )
        
        if self.on_drop:
            try:
                self.on_drop(event)
            except Exception as e:
                logger.warning(f"Drop callback error: {e}")
    
    def clear(self) -> int:
        """Clear queue, return number of items removed."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            self._not_full.notify_all()
            return count
    
    def size(self) -> int:
        """Current queue size."""
        with self._lock:
            return len(self._queue)
    
    def is_empty(self) -> bool:
        """Check if empty."""
        with self._lock:
            return len(self._queue) == 0
    
    def is_full(self) -> bool:
        """Check if at capacity."""
        with self._lock:
            return len(self._queue) >= self.maxsize
    
    def stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                "stage": self.stage,
                "current_size": len(self._queue),
                "maxsize": self.maxsize,
                "put_count": self._put_count,
                "get_count": self._get_count,
                "drop_count": self._drop_count,
                "drop_rate": self._drop_count / max(1, self._put_count),
            }
    
    def get_drops(self) -> List[DropEvent]:
        """Get recent drop events."""
        with self._lock:
            return list(self._drops)


class Pipeline:
    """
    Pipeline of bounded queues for multi-stage processing.
    
    Example:
        >>> pipeline = Pipeline()
        >>> pipeline.add_stage("tokens", maxsize=10)
        >>> pipeline.add_stage("sentences", maxsize=3)
        >>> pipeline.add_stage("audio", maxsize=3)
    """
    
    def __init__(
        self,
        default_maxsize: int = 3,
        default_policy: DropPolicy = DropPolicy.OLDEST,
    ):
        self.default_maxsize = default_maxsize
        self.default_policy = default_policy
        self._queues: dict[str, BoundedQueue] = {}
        self._drop_callback: Optional[Callable[[DropEvent], None]] = None
    
    def set_drop_callback(
        self, 
        callback: Callable[[DropEvent], None],
    ) -> None:
        """Set global callback for all drops."""
        self._drop_callback = callback
    
    def add_stage(
        self,
        name: str,
        maxsize: Optional[int] = None,
        policy: Optional[DropPolicy] = None,
    ) -> BoundedQueue:
        """Add a queue stage to the pipeline."""
        q = BoundedQueue(
            maxsize=maxsize or self.default_maxsize,
            drop_policy=policy or self.default_policy,
            stage=name,
            on_drop=self._drop_callback,
        )
        self._queues[name] = q
        return q
    
    def get_stage(self, name: str) -> Optional[BoundedQueue]:
        """Get a queue by name."""
        return self._queues.get(name)
    
    def clear_all(self) -> None:
        """Clear all queues."""
        for q in self._queues.values():
            q.clear()
    
    def stats(self) -> dict:
        """Get stats for all stages."""
        return {name: q.stats() for name, q in self._queues.items()}
    
    def total_drops(self) -> int:
        """Get total drops across all stages."""
        return sum(q._drop_count for q in self._queues.values())
