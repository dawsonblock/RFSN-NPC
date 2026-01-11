"""
Metrics collection for performance monitoring.

Tracks:
- Latency histograms (generation, TTS, end-to-end)
- Queue drop counters
- Error counts by subsystem
- Request counts
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LatencyStats:
    """Statistics for a latency measurement."""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    
    # For percentile calculation (approximate)
    _samples: List[float] = field(default_factory=list)
    _max_samples: int = 1000
    
    def record(self, ms: float) -> None:
        """Record a latency sample."""
        self.count += 1
        self.total_ms += ms
        self.min_ms = min(self.min_ms, ms)
        self.max_ms = max(self.max_ms, ms)
        
        # Keep recent samples for percentiles
        self._samples.append(ms)
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples:]
    
    @property
    def avg_ms(self) -> float:
        """Average latency."""
        return self.total_ms / max(1, self.count)
    
    def percentile(self, p: float) -> float:
        """Get percentile (0-100)."""
        if not self._samples:
            return 0.0
        
        sorted_samples = sorted(self._samples)
        idx = int(len(sorted_samples) * p / 100)
        idx = min(idx, len(sorted_samples) - 1)
        return sorted_samples[idx]
    
    @property
    def p50(self) -> float:
        """Median latency."""
        return self.percentile(50)
    
    @property
    def p95(self) -> float:
        """95th percentile latency."""
        return self.percentile(95)
    
    @property
    def p99(self) -> float:
        """99th percentile latency."""
        return self.percentile(99)
    
    def to_dict(self) -> Dict:
        """Export as dictionary."""
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 2),
            "min_ms": round(self.min_ms, 2) if self.count > 0 else 0,
            "max_ms": round(self.max_ms, 2),
            "p50_ms": round(self.p50, 2),
            "p95_ms": round(self.p95, 2),
            "p99_ms": round(self.p99, 2),
        }


class Counter:
    """Thread-safe counter."""
    
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def inc(self, n: int = 1) -> int:
        """Increment and return new value."""
        with self._lock:
            self._value += n
            return self._value
    
    @property
    def value(self) -> int:
        with self._lock:
            return self._value
    
    def reset(self) -> int:
        """Reset and return old value."""
        with self._lock:
            old = self._value
            self._value = 0
            return old


class MetricsCollector:
    """
    Central metrics collection.
    
    Example:
        >>> metrics = MetricsCollector()
        >>> metrics.record_latency("generation", 150.5)
        >>> metrics.increment("errors", subsystem="tts")
        >>> print(metrics.summary())
    """
    
    _instance: Optional["MetricsCollector"] = None
    
    @classmethod
    def get_instance(cls) -> "MetricsCollector":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = datetime.now()
        
        # Latency histograms by operation
        self._latencies: Dict[str, LatencyStats] = defaultdict(LatencyStats)
        
        # Counters by name
        self._counters: Dict[str, Counter] = defaultdict(Counter)
        
        # Error counts by subsystem
        self._errors: Dict[str, Counter] = defaultdict(Counter)
        
        # Drop counts by stage
        self._drops: Dict[str, Counter] = defaultdict(Counter)
    
    def record_latency(self, operation: str, ms: float) -> None:
        """Record a latency measurement."""
        with self._lock:
            self._latencies[operation].record(ms)
    
    def time_operation(self, operation: str) -> "LatencyContext":
        """Context manager for timing an operation."""
        return LatencyContext(self, operation)
    
    def increment(
        self,
        counter: str,
        n: int = 1,
        subsystem: Optional[str] = None,
    ) -> int:
        """Increment a counter."""
        key = f"{subsystem}.{counter}" if subsystem else counter
        return self._counters[key].inc(n)
    
    def record_error(self, subsystem: str, error_type: str = "unknown") -> None:
        """Record an error."""
        key = f"{subsystem}.{error_type}"
        self._errors[key].inc()
    
    def record_drop(self, stage: str) -> None:
        """Record a queue drop."""
        self._drops[stage].inc()
    
    def get_latency_stats(self, operation: str) -> LatencyStats:
        """Get latency stats for an operation."""
        with self._lock:
            return self._latencies[operation]
    
    def get_counter(self, counter: str) -> int:
        """Get counter value."""
        return self._counters[counter].value
    
    def get_total_errors(self) -> int:
        """Get total error count."""
        return sum(c.value for c in self._errors.values())
    
    def get_total_drops(self) -> int:
        """Get total drop count."""
        return sum(c.value for c in self._drops.values())
    
    def summary(self) -> Dict:
        """Get full metrics summary."""
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        return {
            "uptime_seconds": round(uptime, 1),
            "latencies": {
                op: stats.to_dict()
                for op, stats in self._latencies.items()
            },
            "counters": {
                name: c.value
                for name, c in self._counters.items()
            },
            "errors": {
                name: c.value
                for name, c in self._errors.items()
            },
            "drops": {
                stage: c.value
                for stage, c in self._drops.items()
            },
            "totals": {
                "errors": self.get_total_errors(),
                "drops": self.get_total_drops(),
            },
        }
    
    def export_json(self, path: str) -> None:
        """Export metrics to JSON file."""
        summary = self.summary()
        summary["exported_at"] = datetime.now().isoformat()
        
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
    
    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._latencies.clear()
            self._counters.clear()
            self._errors.clear()
            self._drops.clear()
            self._start_time = datetime.now()


class LatencyContext:
    """Context manager for timing operations."""
    
    def __init__(self, collector: MetricsCollector, operation: str):
        self.collector = collector
        self.operation = operation
        self.start_time: Optional[float] = None
    
    def __enter__(self) -> "LatencyContext":
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args) -> None:
        if self.start_time is not None:
            elapsed_ms = (time.perf_counter() - self.start_time) * 1000
            self.collector.record_latency(self.operation, elapsed_ms)


# Convenience functions
def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return MetricsCollector.get_instance()


def record_latency(operation: str, ms: float) -> None:
    """Record a latency measurement."""
    get_metrics().record_latency(operation, ms)


def time_operation(operation: str) -> LatencyContext:
    """Time an operation."""
    return get_metrics().time_operation(operation)


def record_error(subsystem: str, error_type: str = "unknown") -> None:
    """Record an error."""
    get_metrics().record_error(subsystem, error_type)
