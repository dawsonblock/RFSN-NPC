"""
Health heartbeat protocol for Python ↔ SKSE bridge communication.

Provides:
- Structured heartbeat messages
- Bridge health status
- "AI Offline" fallback triggers
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class BridgeStatus(Enum):
    """Status of the AI bridge."""
    ONLINE = "online"
    DEGRADED = "degraded"  # Slow but working
    OFFLINE = "offline"    # Not responding
    STARTING = "starting"  # Initializing
    SHUTTING_DOWN = "shutting_down"


@dataclass
class HeartbeatMessage:
    """Heartbeat message for bridge communication."""
    timestamp: str
    status: str
    sequence: int
    latency_ms: float = 0.0
    queue_depth: int = 0
    active_npcs: int = 0
    error: Optional[str] = None
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> "HeartbeatMessage":
        return cls(**json.loads(data))


@dataclass
class BridgeHealth:
    """Current health state of the bridge."""
    status: BridgeStatus
    last_heartbeat: Optional[str] = None
    consecutive_failures: int = 0
    avg_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    
    def is_healthy(self) -> bool:
        return self.status in (BridgeStatus.ONLINE, BridgeStatus.DEGRADED)
    
    def should_fallback(self) -> bool:
        """Should trigger fallback dialogue?"""
        return self.status == BridgeStatus.OFFLINE


class HeartbeatProtocol:
    """
    Manages heartbeat communication between Python and SKSE bridge.
    
    Usage:
        >>> protocol = HeartbeatProtocol()
        >>> protocol.start()
        >>> 
        >>> # In worker loop:
        >>> protocol.send_heartbeat()
        >>> 
        >>> # Check health:
        >>> if protocol.health.should_fallback():
        ...     use_fallback_dialogue()
    """
    
    DEGRADED_LATENCY_MS = 500.0   # Above this = degraded
    OFFLINE_TIMEOUT_S = 30.0       # No heartbeat = offline
    
    def __init__(
        self,
        on_status_change: Optional[Callable[[BridgeStatus], None]] = None,
        on_offline: Optional[Callable[[], None]] = None,
    ):
        self._sequence = 0
        self._start_time = time.time()
        self._last_send = 0.0
        self._latencies: List[float] = []
        self._lock = threading.Lock()
        
        self._status = BridgeStatus.STARTING
        self._consecutive_failures = 0
        self._last_heartbeat: Optional[str] = None
        
        # Callbacks
        self._on_status_change = on_status_change
        self._on_offline = on_offline
        
        # Background monitor
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
    
    def start(self) -> None:
        """Start the heartbeat monitor."""
        self._running = True
        self._start_time = time.time()
        self._set_status(BridgeStatus.ONLINE)
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="heartbeat-monitor",
        )
        self._monitor_thread.start()
        logger.info("Heartbeat protocol started")
    
    def stop(self) -> None:
        """Stop the heartbeat monitor."""
        self._running = False
        self._set_status(BridgeStatus.SHUTTING_DOWN)
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
    
    def _monitor_loop(self) -> None:
        """Background loop to check heartbeat timeout."""
        while self._running:
            time.sleep(5.0)
            
            with self._lock:
                if self._last_send == 0:
                    continue
                
                elapsed = time.time() - self._last_send
                
                if elapsed > self.OFFLINE_TIMEOUT_S:
                    if self._status != BridgeStatus.OFFLINE:
                        self._set_status(BridgeStatus.OFFLINE)
                        if self._on_offline:
                            try:
                                self._on_offline()
                            except Exception as e:
                                logger.error(f"Offline callback failed: {e}")
    
    def send_heartbeat(
        self,
        queue_depth: int = 0,
        active_npcs: int = 0,
        error: str = None,
    ) -> HeartbeatMessage:
        """
        Send a heartbeat message.
        
        Returns the message for optional forwarding to SKSE.
        """
        with self._lock:
            self._sequence += 1
            now = time.time()
            
            # Calculate latency since last beat
            latency_ms = (now - self._last_send) * 1000 if self._last_send else 0
            self._last_send = now
            
            # Track latency
            self._latencies.append(latency_ms)
            if len(self._latencies) > 100:
                self._latencies = self._latencies[-100:]
            
            # Update status based on latency
            avg_latency = sum(self._latencies) / len(self._latencies)
            if error:
                self._consecutive_failures += 1
                if self._consecutive_failures > 3:
                    self._set_status(BridgeStatus.OFFLINE)
            elif avg_latency > self.DEGRADED_LATENCY_MS:
                self._set_status(BridgeStatus.DEGRADED)
                self._consecutive_failures = 0
            else:
                self._set_status(BridgeStatus.ONLINE)
                self._consecutive_failures = 0
            
            self._last_heartbeat = datetime.now().isoformat()
            
            msg = HeartbeatMessage(
                timestamp=self._last_heartbeat,
                status=self._status.value,
                sequence=self._sequence,
                latency_ms=round(latency_ms, 2),
                queue_depth=queue_depth,
                active_npcs=active_npcs,
                error=error,
            )
            
            return msg
    
    def _set_status(self, new_status: BridgeStatus) -> None:
        """Update status and fire callback if changed."""
        if new_status != self._status:
            old = self._status
            self._status = new_status
            logger.info(f"Bridge status: {old.value} → {new_status.value}")
            
            if self._on_status_change:
                try:
                    self._on_status_change(new_status)
                except Exception as e:
                    logger.error(f"Status change callback failed: {e}")
    
    @property
    def health(self) -> BridgeHealth:
        """Get current health status."""
        with self._lock:
            avg_latency = (
                sum(self._latencies) / len(self._latencies)
                if self._latencies else 0.0
            )
            
            return BridgeHealth(
                status=self._status,
                last_heartbeat=self._last_heartbeat,
                consecutive_failures=self._consecutive_failures,
                avg_latency_ms=round(avg_latency, 2),
                uptime_seconds=round(time.time() - self._start_time, 2),
            )
    
    @property
    def is_online(self) -> bool:
        return self._status == BridgeStatus.ONLINE
    
    @property
    def should_fallback(self) -> bool:
        return self._status == BridgeStatus.OFFLINE


# Fallback dialogue for when AI is offline
FALLBACK_DIALOGUES = {
    "default": [
        "I... need a moment to gather my thoughts.",
        "Hmm. Words escape me right now.",
        "Give me a moment, I'm not feeling quite myself.",
        "...",
    ],
    "guard": [
        "Patrol duty calls. Move along.",
        "Nothing to report.",
        "Stay out of trouble.",
    ],
    "merchant": [
        "Come back later, I'm busy.",
        "Shop's having some... difficulties.",
        "Check back in a moment.",
    ],
}


def get_fallback_dialogue(npc_type: str = "default") -> str:
    """Get a fallback dialogue line for offline mode."""
    import random
    lines = FALLBACK_DIALOGUES.get(npc_type, FALLBACK_DIALOGUES["default"])
    return random.choice(lines)


# Global protocol instance
_protocol: Optional[HeartbeatProtocol] = None


def get_heartbeat_protocol() -> HeartbeatProtocol:
    """Get or create global heartbeat protocol."""
    global _protocol
    if _protocol is None:
        _protocol = HeartbeatProtocol()
    return _protocol
