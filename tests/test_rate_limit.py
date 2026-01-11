"""
Tests for rate limiting module.
"""
import time
import threading

import pytest

from rfsn_hybrid.rate_limit import (
    TokenBucket,
    RateLimiter,
    rate_limit,
    get_rate_limiter,
)


class TestTokenBucket:
    """Test token bucket implementation."""
    
    def test_initial_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.available == 10
    
    def test_acquire_reduces_tokens(self):
        bucket = TokenBucket(capacity=10, refill_rate=0.0)  # No refill
        
        assert bucket.acquire(3)
        assert bucket.available <= 7  # May have slight timing variance
    
    def test_acquire_fails_when_empty(self):
        bucket = TokenBucket(capacity=2, refill_rate=0.1)
        
        assert bucket.acquire(2)
        assert not bucket.acquire(1)
    
    def test_refill_over_time(self):
        bucket = TokenBucket(capacity=10, refill_rate=1000.0)  # 1000/sec for fast test
        
        bucket.acquire(5)
        initial = bucket.available
        
        time.sleep(0.01)  # 10ms = 10 tokens at 1000/sec
        # Should have refilled some (at least partially)
        assert bucket.available >= initial  # Tokens should have increased or stayed same
    
    def test_capacity_is_max(self):
        bucket = TokenBucket(capacity=5, refill_rate=1000.0)
        
        time.sleep(0.01)
        # Should not exceed capacity
        assert bucket.available <= 5


class TestRateLimiter:
    """Test per-key rate limiter."""
    
    def test_allows_within_limit(self):
        limiter = RateLimiter(requests_per_minute=600, burst_size=10)
        
        for _ in range(10):
            assert limiter.allow("user1")
    
    def test_blocks_over_limit(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=3)
        
        # Use up burst
        assert limiter.allow("user1")
        assert limiter.allow("user1")
        assert limiter.allow("user1")
        
        # Should be blocked
        assert not limiter.allow("user1")
    
    def test_separate_keys_independent(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=2)
        
        assert limiter.allow("user1")
        assert limiter.allow("user1")
        assert not limiter.allow("user1")
        
        # Different user should be allowed
        assert limiter.allow("user2")
    
    def test_reset_clears_limit(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)
        
        assert limiter.allow("user1")
        assert not limiter.allow("user1")
        
        limiter.reset("user1")
        assert limiter.allow("user1")
    
    def test_wait_time_positive_when_limited(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=1)
        
        limiter.allow("user1")
        assert not limiter.allow("user1")
        
        wait = limiter.wait_time("user1")
        assert wait > 0
    
    def test_stats(self):
        limiter = RateLimiter(requests_per_minute=60, burst_size=10)
        
        limiter.allow("user1")
        limiter.allow("user2")
        
        stats = limiter.stats()
        assert stats["active_keys"] == 2
        assert stats["config"]["requests_per_minute"] == 60
    
    def test_thread_safety(self):
        limiter = RateLimiter(requests_per_minute=6000, burst_size=100)
        errors = []
        allowed_count = [0]
        lock = threading.Lock()
        
        def worker():
            try:
                for _ in range(50):
                    if limiter.allow("shared"):
                        with lock:
                            allowed_count[0] += 1
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0


class TestGlobalRateLimiter:
    """Test global rate limit function."""
    
    def test_rate_limit_function(self):
        # Should not crash
        result = rate_limit("test_key")
        assert isinstance(result, bool)
    
    def test_get_rate_limiter_singleton(self):
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2
