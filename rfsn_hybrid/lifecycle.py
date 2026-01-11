"""
Lifecycle management for system startup/shutdown.

Prevents:
- Orphan threads
- Stuck audio
- Resource leaks
- Duplicate initialization
"""
from __future__ import annotations

import atexit
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class LifecycleState(str, Enum):
    """System lifecycle states."""
    NOT_STARTED = "not_started"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ManagedThread:
    """Thread tracked by lifecycle manager."""
    name: str
    thread: threading.Thread
    stop_event: threading.Event
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LifecycleManager:
    """
    Manages system lifecycle and resource cleanup.
    
    Features:
    - Thread tracking with graceful shutdown
    - Cancellation tokens
    - Cleanup hooks
    - Idempotent shutdown
    
    Example:
        >>> manager = LifecycleManager()
        >>> manager.startup()
        >>> worker = manager.create_thread("worker", my_func)
        >>> worker.start()
        >>> # ... later ...
        >>> manager.shutdown()  # Stops all threads
    """
    
    _instance: Optional["LifecycleManager"] = None
    
    @classmethod
    def get_instance(cls) -> "LifecycleManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._state = LifecycleState.NOT_STARTED
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        
        # Managed resources
        self._threads: Dict[str, ManagedThread] = {}
        self._cleanup_hooks: List[Callable[[], None]] = []
        self._startup_hooks: List[Callable[[], None]] = []
        
        # Stats
        self._start_time: Optional[datetime] = None
        self._stop_time: Optional[datetime] = None
        
        # Register atexit handler
        atexit.register(self._atexit_handler)
    
    @property
    def state(self) -> LifecycleState:
        """Current lifecycle state."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Check if system is running."""
        return self._state == LifecycleState.RUNNING
    
    @property
    def shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._shutdown_event.is_set()
    
    def get_shutdown_event(self) -> threading.Event:
        """Get the shutdown event for threads to monitor."""
        return self._shutdown_event
    
    def add_startup_hook(self, hook: Callable[[], None]) -> None:
        """Add a function to call during startup."""
        with self._lock:
            self._startup_hooks.append(hook)
    
    def add_cleanup_hook(self, hook: Callable[[], None]) -> None:
        """Add a function to call during shutdown."""
        with self._lock:
            self._cleanup_hooks.append(hook)
    
    def startup(self) -> bool:
        """
        Start the system.
        
        Returns:
            True if started, False if already running
        """
        with self._lock:
            if self._state in (LifecycleState.RUNNING, LifecycleState.STARTING):
                logger.warning("System already started")
                return False
            
            logger.info("System starting...")
            self._state = LifecycleState.STARTING
            self._shutdown_event.clear()
            self._start_time = datetime.now()
            
            # Run startup hooks
            for hook in self._startup_hooks:
                try:
                    hook()
                except Exception as e:
                    logger.error(f"Startup hook failed: {e}")
                    self._state = LifecycleState.ERROR
                    return False
            
            self._state = LifecycleState.RUNNING
            logger.info("System started")
            return True
    
    def shutdown(self, timeout: float = 5.0) -> bool:
        """
        Shutdown the system gracefully.
        
        Args:
            timeout: Max seconds to wait for threads to stop
            
        Returns:
            True if clean shutdown, False if forced
        """
        with self._lock:
            if self._state in (LifecycleState.STOPPED, LifecycleState.STOPPING):
                logger.debug("System already stopped")
                return True
            
            if self._state == LifecycleState.NOT_STARTED:
                self._state = LifecycleState.STOPPED
                return True
            
            logger.info("System shutting down...")
            self._state = LifecycleState.STOPPING
            self._stop_time = datetime.now()
        
        # Signal all threads to stop
        self._shutdown_event.set()
        
        # Stop managed threads
        clean = True
        for managed in list(self._threads.values()):
            managed.stop_event.set()
        
        # Wait for threads
        for name, managed in list(self._threads.items()):
            if managed.thread.is_alive():
                logger.debug(f"Waiting for thread {name}...")
                managed.thread.join(timeout=timeout)
                
                if managed.thread.is_alive():
                    logger.warning(f"Thread {name} did not stop in time")
                    clean = False
        
        # Run cleanup hooks (in reverse order)
        for hook in reversed(self._cleanup_hooks):
            try:
                hook()
            except Exception as e:
                logger.error(f"Cleanup hook failed: {e}")
                clean = False
        
        self._threads.clear()
        
        with self._lock:
            self._state = LifecycleState.STOPPED
        
        if clean:
            logger.info("System stopped cleanly")
        else:
            logger.warning("System stopped with warnings")
        
        return clean
    
    def create_thread(
        self,
        name: str,
        target: Callable,
        args: tuple = (),
        daemon: bool = True,
    ) -> threading.Thread:
        """
        Create a managed thread.
        
        The thread will be tracked and stopped during shutdown.
        
        Args:
            name: Thread name
            target: Function to run
            args: Arguments for target
            daemon: Whether thread is daemon
            
        Returns:
            The created thread (not started)
        """
        stop_event = threading.Event()
        
        def wrapper():
            try:
                target(*args, stop_event)
            except Exception as e:
                logger.error(f"Thread {name} crashed: {e}")
        
        thread = threading.Thread(
            target=wrapper,
            name=name,
            daemon=daemon,
        )
        
        with self._lock:
            self._threads[name] = ManagedThread(
                name=name,
                thread=thread,
                stop_event=stop_event,
            )
        
        return thread
    
    def remove_thread(self, name: str) -> None:
        """Remove a thread from tracking."""
        with self._lock:
            self._threads.pop(name, None)
    
    def get_thread_names(self) -> List[str]:
        """Get names of all managed threads."""
        with self._lock:
            return list(self._threads.keys())
    
    def get_active_thread_count(self) -> int:
        """Get count of alive threads."""
        with self._lock:
            return sum(
                1 for m in self._threads.values() 
                if m.thread.is_alive()
            )
    
    def on_game_load(self) -> None:
        """Called when game loads a save."""
        logger.info("Game load detected")
        # Could trigger state reload, etc.
    
    def on_game_exit(self) -> None:
        """Called when game is exiting."""
        logger.info("Game exit detected")
        self.shutdown()
    
    def _atexit_handler(self) -> None:
        """Handler for process exit."""
        if self._state == LifecycleState.RUNNING:
            logger.info("Process exiting, triggering shutdown")
            self.shutdown(timeout=2.0)
    
    def stats(self) -> dict:
        """Get lifecycle statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "uptime_seconds": (
                    (datetime.now() - self._start_time).total_seconds()
                    if self._start_time else 0
                ),
                "threads": {
                    name: {
                        "alive": m.thread.is_alive(),
                        "started_at": m.started_at,
                    }
                    for name, m in self._threads.items()
                },
                "cleanup_hooks": len(self._cleanup_hooks),
            }


# Convenience function
def get_lifecycle() -> LifecycleManager:
    """Get the global lifecycle manager."""
    return LifecycleManager.get_instance()
