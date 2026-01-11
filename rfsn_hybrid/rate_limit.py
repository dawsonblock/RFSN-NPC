"""
Rate limiting for API endpoints.

Uses token bucket algorithm for smooth rate limiting.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    burst_size: int = 10
    
    @property
    def refill_rate(self) -> float:
        """Tokens per second."""
        return self.requests_per_minute / 60.0


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float
    tokens: float = field(init=False)
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def __post_init__(self):
        self.tokens = self.capacity
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens.
        
        Returns:
            True if acquired, False if rate limited
        """
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_time(self) -> float:
        """Seconds until a token is available."""
        with self.lock:
            self._refill()
            if self.tokens >= 1:
                return 0.0
            return (1 - self.tokens) / self.refill_rate
    
    @property
    def available(self) -> float:
        """Current available tokens."""
        with self.lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """
    Per-key rate limiter using token buckets.
    
    Example:
        >>> limiter = RateLimiter(requests_per_minute=60)
        >>> if limiter.allow("user_123"):
        ...     process_request()
        ... else:
        ...     return "Rate limited"
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        key_ttl: float = 300.0,  # Clean up keys after 5 min inactivity
    ):
        self.config = RateLimitConfig(requests_per_minute, burst_size)
        self.key_ttl = key_ttl
        self._buckets: Dict[str, TokenBucket] = {}
        self._last_access: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 60.0
        self._last_cleanup = time.time()
    
    def _get_bucket(self, key: str) -> TokenBucket:
        """Get or create bucket for key."""
        with self._lock:
            self._maybe_cleanup()
            
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(
                    capacity=self.config.burst_size,
                    refill_rate=self.config.refill_rate,
                )
            
            self._last_access[key] = time.time()
            return self._buckets[key]
    
    def _maybe_cleanup(self) -> None:
        """Clean up expired buckets."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        expired = [
            key for key, last in self._last_access.items()
            if now - last > self.key_ttl
        ]
        
        for key in expired:
            self._buckets.pop(key, None)
            self._last_access.pop(key, None)
        
        self._last_cleanup = now
    
    def allow(self, key: str, tokens: int = 1) -> bool:
        """
        Check if request is allowed for key.
        
        Args:
            key: Rate limit key (e.g., IP address, user ID)
            tokens: Number of tokens to consume
            
        Returns:
            True if allowed, False if rate limited
        """
        bucket = self._get_bucket(key)
        return bucket.acquire(tokens)
    
    def wait_time(self, key: str) -> float:
        """Get seconds until key can make a request."""
        bucket = self._get_bucket(key)
        return bucket.wait_time()
    
    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        with self._lock:
            self._buckets.pop(key, None)
            self._last_access.pop(key, None)
    
    def stats(self) -> Dict:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                "active_keys": len(self._buckets),
                "config": {
                    "requests_per_minute": self.config.requests_per_minute,
                    "burst_size": self.config.burst_size,
                },
            }


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get shared rate limiter."""
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter()
    return _global_limiter


def rate_limit(key: str) -> bool:
    """Check if request is allowed. Convenience function."""
    return get_rate_limiter().allow(key)


# FastAPI middleware helper
def create_rate_limit_middleware(
    requests_per_minute: int = 60,
    burst_size: int = 10,
    key_func: Optional[Callable] = None,
):
    """
    Create rate limiting middleware for FastAPI.
    
    Usage:
        app = FastAPI()
        app.middleware("http")(create_rate_limit_middleware())
    """
    limiter = RateLimiter(requests_per_minute, burst_size)
    
    async def middleware(request, call_next):
        # Get client key
        if key_func:
            key = key_func(request)
        else:
            key = request.client.host if request.client else "unknown"
        
        if not limiter.allow(key):
            from fastapi.responses import JSONResponse
            wait = limiter.wait_time(key)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": round(wait, 2),
                },
                headers={"Retry-After": str(int(wait + 1))},
            )
        
        return await call_next(request)
    
    return middleware
