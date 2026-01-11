"""
Tests for lifecycle management.

Verify clean startup/shutdown without resource leaks.
"""
import threading
import time

import pytest

from rfsn_hybrid.lifecycle import (
    LifecycleManager,
    LifecycleState,
    get_lifecycle,
)


@pytest.fixture
def lifecycle():
    """Create fresh lifecycle manager."""
    manager = LifecycleManager()
    yield manager
    # Ensure cleanup
    if manager.state != LifecycleState.STOPPED:
        manager.shutdown(timeout=1.0)


class TestLifecycleManager:
    """Test lifecycle management."""
    
    def test_initial_state(self, lifecycle):
        """Should start in NOT_STARTED state."""
        assert lifecycle.state == LifecycleState.NOT_STARTED
    
    def test_startup_transitions_to_running(self, lifecycle):
        """startup() should transition to RUNNING."""
        result = lifecycle.startup()
        
        assert result == True
        assert lifecycle.state == LifecycleState.RUNNING
    
    def test_shutdown_transitions_to_stopped(self, lifecycle):
        """shutdown() should transition to STOPPED."""
        lifecycle.startup()
        result = lifecycle.shutdown()
        
        assert result == True
        assert lifecycle.state == LifecycleState.STOPPED
    
    def test_double_startup_returns_false(self, lifecycle):
        """Second startup should return False."""
        lifecycle.startup()
        result = lifecycle.startup()
        
        assert result == False
    
    def test_shutdown_is_idempotent(self, lifecycle):
        """Multiple shutdown calls should be safe."""
        lifecycle.startup()
        
        lifecycle.shutdown()
        lifecycle.shutdown()
        lifecycle.shutdown()
        
        assert lifecycle.state == LifecycleState.STOPPED
    
    def test_startup_hooks_run(self, lifecycle):
        """Startup hooks should be called."""
        called = []
        
        lifecycle.add_startup_hook(lambda: called.append("hook1"))
        lifecycle.add_startup_hook(lambda: called.append("hook2"))
        
        lifecycle.startup()
        
        assert called == ["hook1", "hook2"]
    
    def test_cleanup_hooks_run_on_shutdown(self, lifecycle):
        """Cleanup hooks should be called in reverse order."""
        called = []
        
        lifecycle.add_cleanup_hook(lambda: called.append("cleanup1"))
        lifecycle.add_cleanup_hook(lambda: called.append("cleanup2"))
        
        lifecycle.startup()
        lifecycle.shutdown()
        
        # Reverse order
        assert called == ["cleanup2", "cleanup1"]
    
    def test_managed_thread_tracking(self, lifecycle):
        """Threads should be tracked."""
        lifecycle.startup()
        
        def worker(stop_event):
            while not stop_event.is_set():
                time.sleep(0.1)
        
        thread = lifecycle.create_thread("test_worker", worker)
        thread.start()
        
        assert "test_worker" in lifecycle.get_thread_names()
        assert lifecycle.get_active_thread_count() == 1
        
        lifecycle.shutdown()
        
        # Thread should be stopped
        assert lifecycle.get_active_thread_count() == 0
    
    def test_shutdown_stops_threads(self, lifecycle):
        """Shutdown should stop all managed threads."""
        lifecycle.startup()
        
        running = threading.Event()
        
        def worker(stop_event):
            running.set()
            while not stop_event.is_set():
                time.sleep(0.01)
        
        thread = lifecycle.create_thread("stopper", worker)
        thread.start()
        
        # Wait for thread to start
        running.wait(timeout=1.0)
        assert thread.is_alive()
        
        # Shutdown
        lifecycle.shutdown(timeout=2.0)
        
        # Thread should be stopped
        time.sleep(0.1)
        assert not thread.is_alive()
    
    def test_shutdown_event_signaled(self, lifecycle):
        """Shutdown event should be set."""
        lifecycle.startup()
        
        assert not lifecycle.shutdown_requested
        
        lifecycle.shutdown()
        
        assert lifecycle.shutdown_requested
    
    def test_stats_returns_info(self, lifecycle):
        """stats() should return useful info."""
        lifecycle.startup()
        
        stats = lifecycle.stats()
        
        assert stats["state"] == "running"
        assert "uptime_seconds" in stats
        assert "threads" in stats


class TestLifecycleDuplicateResources:
    """Test that restart doesn't duplicate resources."""
    
    def test_restart_no_duplicate_threads(self, lifecycle):
        """Restarting should not leave duplicate threads."""
        def worker(stop_event):
            while not stop_event.is_set():
                time.sleep(0.1)
        
        # First run
        lifecycle.startup()
        lifecycle.create_thread("worker", worker).start()
        lifecycle.shutdown()
        
        # Second run should be clean
        lifecycle2 = LifecycleManager()
        lifecycle2.startup()
        
        assert lifecycle2.get_active_thread_count() == 0
        
        lifecycle2.shutdown()
    
    def test_cleanup_hook_failure_continues(self, lifecycle):
        """Cleanup should continue even if a hook fails."""
        calls = []
        
        lifecycle.add_cleanup_hook(lambda: calls.append("first"))
        lifecycle.add_cleanup_hook(lambda: (_ for _ in ()).throw(Exception("fail")))
        lifecycle.add_cleanup_hook(lambda: calls.append("last"))
        
        lifecycle.startup()
        lifecycle.shutdown()
        
        # First and last should still run
        assert "first" in calls
        assert "last" in calls
