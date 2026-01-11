"""
Process supervisor with watchdog, auto-restart, and crash journaling.

Provides:
- Deadlock detection via heartbeat timeout
- Auto-restart with exponential backoff
- Crash journal for debugging
- Graceful shutdown handling
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class CrashEntry:
    """Record of a crash/restart event."""
    timestamp: str
    reason: str
    exit_code: Optional[int] = None
    npc_id: Optional[str] = None
    scene_context: Optional[str] = None
    restart_count: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SupervisorConfig:
    """Supervisor configuration."""
    heartbeat_interval: float = 5.0      # Seconds between heartbeats
    heartbeat_timeout: float = 30.0      # Seconds before declaring dead
    max_restarts: int = 5                # Max restarts before giving up
    restart_backoff_base: float = 1.0    # Initial backoff seconds
    restart_backoff_max: float = 60.0    # Max backoff seconds
    crash_journal_path: str = "./crash_journal.jsonl"
    state_snapshot_path: str = "./state_snapshot.json"


class CrashJournal:
    """Append-only crash log for debugging."""
    
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, entry: CrashEntry) -> None:
        """Append a crash entry to the journal."""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        logger.warning(f"Crash logged: {entry.reason}")
    
    def recent(self, n: int = 10) -> List[CrashEntry]:
        """Read recent crash entries."""
        if not self.path.exists():
            return []
        
        entries = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entries.append(CrashEntry(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        
        return entries[-n:]
    
    def clear(self) -> None:
        """Clear the journal."""
        if self.path.exists():
            self.path.unlink()


class HeartbeatMonitor:
    """Monitors a heartbeat signal for liveness detection."""
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._last_beat = time.time()
        self._lock = threading.Lock()
        self._alive = True
    
    def beat(self) -> None:
        """Record a heartbeat."""
        with self._lock:
            self._last_beat = time.time()
            self._alive = True
    
    def is_alive(self) -> bool:
        """Check if heartbeat is within timeout."""
        with self._lock:
            elapsed = time.time() - self._last_beat
            self._alive = elapsed < self.timeout
            return self._alive
    
    def time_since_beat(self) -> float:
        """Seconds since last heartbeat."""
        with self._lock:
            return time.time() - self._last_beat
    
    def reset(self) -> None:
        """Reset the monitor."""
        with self._lock:
            self._last_beat = time.time()
            self._alive = True


class Supervisor:
    """
    Process supervisor with auto-restart and crash recovery.
    
    Can supervise:
    - A callable (function)
    - A subprocess command
    
    Example:
        >>> supervisor = Supervisor(config)
        >>> supervisor.start(my_worker_function)
        >>> # Runs until max_restarts or clean shutdown
    """
    
    def __init__(self, config: Optional[SupervisorConfig] = None):
        self.config = config or SupervisorConfig()
        self.journal = CrashJournal(self.config.crash_journal_path)
        self.heartbeat = HeartbeatMonitor(self.config.heartbeat_timeout)
        
        self._restart_count = 0
        self._running = False
        self._shutdown_event = threading.Event()
        self._current_context: Dict[str, Any] = {}
        self._worker_thread: Optional[threading.Thread] = None
        
        # Register signal handlers
        self._setup_signals()
    
    def _setup_signals(self) -> None:
        """Set up graceful shutdown on signals."""
        def handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            self.shutdown()
        
        try:
            signal.signal(signal.SIGTERM, handler)
            signal.signal(signal.SIGINT, handler)
        except (ValueError, OSError):
            # Not in main thread or unsupported
            pass
    
    def set_context(self, npc_id: str = None, scene: str = None, **kwargs) -> None:
        """Set current context for crash logging."""
        if npc_id:
            self._current_context["npc_id"] = npc_id
        if scene:
            self._current_context["scene"] = scene
        self._current_context.update(kwargs)
    
    def start(self, worker: Callable[[], None]) -> None:
        """
        Start supervising a worker function.
        
        Blocks until shutdown or max_restarts exceeded.
        """
        self._running = True
        self._restart_count = 0
        
        while self._running and self._restart_count < self.config.max_restarts:
            self.heartbeat.reset()
            
            try:
                logger.info(f"Starting worker (attempt {self._restart_count + 1})")
                
                # Run in thread so we can monitor heartbeat
                self._worker_thread = threading.Thread(target=worker, daemon=True)
                self._worker_thread.start()
                
                # Monitor loop
                while self._worker_thread.is_alive() and not self._shutdown_event.is_set():
                    time.sleep(self.config.heartbeat_interval)
                    
                    if not self.heartbeat.is_alive():
                        raise TimeoutError(
                            f"Heartbeat timeout ({self.heartbeat.time_since_beat():.1f}s)"
                        )
                
                if self._shutdown_event.is_set():
                    logger.info("Shutdown requested, exiting supervisor")
                    break
                
                # Worker exited cleanly
                logger.info("Worker exited normally")
                break
                
            except Exception as e:
                self._handle_crash(str(e))
        
        if self._restart_count >= self.config.max_restarts:
            logger.error(f"Max restarts ({self.config.max_restarts}) exceeded, giving up")
            self.journal.log(CrashEntry(
                timestamp=datetime.now().isoformat(),
                reason="Max restarts exceeded",
                restart_count=self._restart_count,
                npc_id=self._current_context.get("npc_id"),
                scene_context=self._current_context.get("scene"),
            ))
    
    def _handle_crash(self, reason: str, exit_code: int = None) -> None:
        """Handle a crash and decide whether to restart."""
        self._restart_count += 1
        
        # Log to crash journal
        self.journal.log(CrashEntry(
            timestamp=datetime.now().isoformat(),
            reason=reason,
            exit_code=exit_code,
            restart_count=self._restart_count,
            npc_id=self._current_context.get("npc_id"),
            scene_context=self._current_context.get("scene"),
        ))
        
        # Calculate backoff
        backoff = min(
            self.config.restart_backoff_base * (2 ** (self._restart_count - 1)),
            self.config.restart_backoff_max
        )
        
        logger.warning(
            f"Crash #{self._restart_count}: {reason}. "
            f"Restarting in {backoff:.1f}s..."
        )
        
        # Wait with backoff
        if not self._shutdown_event.wait(backoff):
            return  # Continue to restart
        
        # Shutdown requested during backoff
        self._running = False
    
    def shutdown(self) -> None:
        """Request graceful shutdown."""
        self._running = False
        self._shutdown_event.set()
    
    def is_running(self) -> bool:
        """Check if supervisor is running."""
        return self._running
    
    def stats(self) -> Dict:
        """Get supervisor statistics."""
        return {
            "running": self._running,
            "restart_count": self._restart_count,
            "heartbeat_alive": self.heartbeat.is_alive(),
            "time_since_heartbeat": round(self.heartbeat.time_since_beat(), 2),
            "context": self._current_context,
            "recent_crashes": len(self.journal.recent(10)),
        }


# Global supervisor instance
_supervisor: Optional[Supervisor] = None


def get_supervisor() -> Supervisor:
    """Get or create global supervisor."""
    global _supervisor
    if _supervisor is None:
        _supervisor = Supervisor()
    return _supervisor


def heartbeat() -> None:
    """Send heartbeat to supervisor (call from worker)."""
    get_supervisor().heartbeat.beat()


def set_crash_context(**kwargs) -> None:
    """Set context for crash logging."""
    get_supervisor().set_context(**kwargs)
