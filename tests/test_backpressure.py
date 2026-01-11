"""
Tests for backpressure handling.

Flooding input should not grow memory unboundedly.
"""
import threading
import time

import pytest

from rfsn_hybrid.core.queues import BoundedQueue, DropPolicy, Pipeline


class TestBoundedQueue:
    """Test bounded queue behavior."""
    
    def test_respects_maxsize(self):
        """Queue should not exceed maxsize."""
        q = BoundedQueue[int](maxsize=3, stage="test")
        
        for i in range(10):
            q.put(i)
        
        assert q.size() <= 3
    
    def test_drop_oldest_policy(self):
        """Drop oldest policy should remove oldest items."""
        q = BoundedQueue[int](
            maxsize=3,
            drop_policy=DropPolicy.OLDEST,
            stage="test",
        )
        
        # Fill queue
        q.put(1)
        q.put(2)
        q.put(3)
        
        # Adding more should drop oldest
        q.put(4)
        q.put(5)
        
        # Should have 3, 4, 5 (oldest 1, 2 dropped)
        items = []
        while not q.is_empty():
            items.append(q.get_nowait())
        
        assert items == [3, 4, 5]
    
    def test_drop_newest_policy(self):
        """Drop newest policy should reject new items."""
        q = BoundedQueue[int](
            maxsize=3,
            drop_policy=DropPolicy.NEWEST,
            stage="test",
        )
        
        # Fill queue
        assert q.put(1) == True
        assert q.put(2) == True
        assert q.put(3) == True
        
        # Adding more should fail
        assert q.put(4) == False
        assert q.put(5) == False
        
        # Should still have 1, 2, 3
        items = []
        while not q.is_empty():
            items.append(q.get_nowait())
        
        assert items == [1, 2, 3]
    
    def test_drop_counter_increments(self):
        """Drop counter should track drops."""
        q = BoundedQueue[int](maxsize=2, stage="test")
        
        q.put(1)
        q.put(2)
        q.put(3)  # Drop 1
        q.put(4)  # Drop 2
        
        stats = q.stats()
        assert stats["drop_count"] == 2
    
    def test_drop_events_logged(self):
        """Drop events should be recorded."""
        q = BoundedQueue[str](maxsize=1, stage="test_stage")
        
        q.put("a")
        q.put("b")  # Drops "a"
        
        drops = q.get_drops()
        assert len(drops) == 1
        assert drops[0].stage == "test_stage"
    
    def test_clear_empties_queue(self):
        """Clear should remove all items."""
        q = BoundedQueue[int](maxsize=5, stage="test")
        
        for i in range(5):
            q.put(i)
        
        cleared = q.clear()
        
        assert cleared == 5
        assert q.is_empty()
    
    def test_thread_safety(self):
        """Queue should handle concurrent access."""
        q = BoundedQueue[int](maxsize=10, stage="test")
        errors = []
        
        def producer():
            try:
                for i in range(100):
                    q.put(i)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        def consumer():
            try:
                count = 0
                while count < 50:
                    item = q.get(timeout=0.1)
                    if item is not None:
                        count += 1
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=producer),
            threading.Thread(target=consumer),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        
        assert len(errors) == 0


class TestPipeline:
    """Test pipeline of queues."""
    
    def test_multi_stage_pipeline(self):
        """Pipeline should manage multiple stages."""
        pipeline = Pipeline(default_maxsize=3)
        
        pipeline.add_stage("tokens")
        pipeline.add_stage("sentences")
        pipeline.add_stage("audio")
        
        stats = pipeline.stats()
        
        assert "tokens" in stats
        assert "sentences" in stats
        assert "audio" in stats
    
    def test_pipeline_total_drops(self):
        """Should track total drops across stages."""
        pipeline = Pipeline(default_maxsize=2)
        
        tokens = pipeline.add_stage("tokens")
        sentences = pipeline.add_stage("sentences")
        
        # Overflow both
        for i in range(5):
            tokens.put(f"token_{i}")
        for i in range(5):
            sentences.put(f"sentence_{i}")
        
        # Each should have dropped 3 (5 - maxsize 2)
        assert pipeline.total_drops() == 6
    
    def test_clear_all_stages(self):
        """Clear all should empty all queues."""
        pipeline = Pipeline()
        
        q1 = pipeline.add_stage("stage1")
        q2 = pipeline.add_stage("stage2")
        
        q1.put("a")
        q2.put("b")
        
        pipeline.clear_all()
        
        assert q1.is_empty()
        assert q2.is_empty()


class TestBackpressureFlood:
    """Test behavior under flood conditions."""
    
    def test_flood_does_not_grow_memory(self):
        """Flooding should not cause unbounded growth."""
        q = BoundedQueue[bytes](maxsize=3, stage="flood_test")
        
        # Simulate flooding with large items
        large_item = b"x" * 1000  # 1KB
        
        # Push 1000 items (would be 1MB if not bounded)
        for _ in range(1000):
            q.put(large_item)
        
        # Queue should only have 3 items
        assert q.size() == 3
        
        # Stats should show drops
        stats = q.stats()
        assert stats["drop_count"] == 997
    
    def test_latency_stabilizes_under_load(self):
        """Latency should not drift upward indefinitely."""
        q = BoundedQueue[float](maxsize=5, stage="latency_test")
        
        latencies = []
        
        for i in range(100):
            start = time.perf_counter()
            q.put(i)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
        
        # First half vs second half shouldn't show drift
        first_half_avg = sum(latencies[:50]) / 50
        second_half_avg = sum(latencies[50:]) / 50
        
        # Second half shouldn't be much worse than first
        # Allow 5x tolerance for test stability
        assert second_half_avg < first_half_avg * 5
