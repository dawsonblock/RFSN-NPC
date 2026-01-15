"""
Promise tracker for NPC consistency.

Tracks implicit commitments NPCs make during conversations.
Biases future decisions toward fulfilling commitments.

Does NOT create goals or autonomous planning - just memory + bias.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class PromiseStatus(str, Enum):
    """Status of a promise."""
    PENDING = "pending"
    FULFILLED = "fulfilled"
    BROKEN = "broken"
    EXPIRED = "expired"


@dataclass
class Promise:
    """
    An implicit commitment made by the NPC.
    
    This is NOT a goal or plan. It's just a memory of something
    the NPC said they would do, which biases future reducer decisions.
    
    Attributes:
        id: Unique promise identifier
        text: What was promised ("I'll help you with the quest")
        to_whom: Who the promise was made to
        context: Situation in which promise was made
        timestamp: When promise was made
        status: Current promise status
        salience: How important this promise is (0.0 to 1.0)
        expiry_hours: Hours until promise expires (None = never)
    """
    id: str
    text: str
    to_whom: str
    context: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: PromiseStatus = PromiseStatus.PENDING
    salience: float = 0.7
    expiry_hours: Optional[float] = None
    
    def is_active(self) -> bool:
        """Check if promise is still active (pending)."""
        return self.status == PromiseStatus.PENDING
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "text": self.text,
            "to_whom": self.to_whom,
            "context": self.context,
            "timestamp": self.timestamp,
            "status": self.status.value,
            "salience": self.salience,
            "expiry_hours": self.expiry_hours,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> Promise:
        return cls(
            id=data["id"],
            text=data["text"],
            to_whom=data["to_whom"],
            context=data.get("context", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            status=PromiseStatus(data.get("status", "pending")),
            salience=data.get("salience", 0.7),
            expiry_hours=data.get("expiry_hours"),
        )


class PromiseTracker:
    """
    Tracks NPC promises for consistency.
    
    This is NOT a planner. It just:
    - Remembers commitments
    - Provides bias signals to reducer
    - Tracks fulfillment/breakage
    """
    
    def __init__(
        self,
        path: Optional[str] = None,
        max_promises: int = 50,
        enabled: bool = True,
    ):
        """
        Initialize promise tracker.
        
        Args:
            path: Path for persistence
            max_promises: Maximum promises to track
            enabled: Whether tracking is enabled
        """
        self.path = path
        self.max_promises = max_promises
        self.enabled = enabled
        self.promises: Dict[str, Promise] = {}
        
        if path and os.path.exists(path):
            self._load()
    
    def add_promise(
        self,
        promise_id: str,
        text: str,
        to_whom: str,
        context: str = "",
        salience: float = 0.7,
        expiry_hours: Optional[float] = None,
    ) -> Promise:
        """
        Record a new promise.
        
        Args:
            promise_id: Unique identifier
            text: Promise text
            to_whom: Who it's promised to
            context: Situational context
            salience: Importance (0-1)
            expiry_hours: Hours until expiry
            
        Returns:
            Created promise
        """
        if not self.enabled:
            return None
        
        # Enforce max promises (evict oldest fulfilled/broken)
        if len(self.promises) >= self.max_promises:
            self._evict_old_promises()
        
        promise = Promise(
            id=promise_id,
            text=text,
            to_whom=to_whom,
            context=context,
            salience=salience,
            expiry_hours=expiry_hours,
        )
        
        self.promises[promise_id] = promise
        
        if self.path:
            self._save()
        
        return promise
    
    def fulfill_promise(self, promise_id: str) -> bool:
        """
        Mark promise as fulfilled.
        
        Args:
            promise_id: Promise to fulfill
            
        Returns:
            True if promise was found and fulfilled
        """
        if promise_id in self.promises:
            self.promises[promise_id].status = PromiseStatus.FULFILLED
            if self.path:
                self._save()
            return True
        return False
    
    def break_promise(self, promise_id: str) -> bool:
        """
        Mark promise as broken.
        
        Args:
            promise_id: Promise that was broken
            
        Returns:
            True if promise was found
        """
        if promise_id in self.promises:
            self.promises[promise_id].status = PromiseStatus.BROKEN
            if self.path:
                self._save()
            return True
        return False
    
    def get_active_promises(self, to_whom: Optional[str] = None) -> List[Promise]:
        """
        Get all active (pending) promises.
        
        Args:
            to_whom: Optional filter by recipient
            
        Returns:
            List of active promises
        """
        active = [p for p in self.promises.values() if p.is_active()]
        
        if to_whom:
            active = [p for p in active if p.to_whom == to_whom]
        
        # Sort by salience (most important first)
        active.sort(key=lambda p: p.salience, reverse=True)
        
        return active
    
    def get_broken_promises(self, to_whom: Optional[str] = None) -> List[Promise]:
        """
        Get all broken promises.
        
        Args:
            to_whom: Optional filter by recipient
            
        Returns:
            List of broken promises
        """
        broken = [p for p in self.promises.values() if p.status == PromiseStatus.BROKEN]
        
        if to_whom:
            broken = [p for p in broken if p.to_whom == to_whom]
        
        return broken
    
    def check_expiry(self, hours_passed: float) -> List[str]:
        """
        Check for expired promises and mark them.
        
        Args:
            hours_passed: Hours elapsed since last check
            
        Returns:
            List of expired promise IDs
        """
        expired = []
        
        for promise_id, promise in self.promises.items():
            if promise.is_active() and promise.expiry_hours is not None:
                promise.expiry_hours -= hours_passed
                if promise.expiry_hours <= 0:
                    promise.status = PromiseStatus.EXPIRED
                    expired.append(promise_id)
        
        if expired and self.path:
            self._save()
        
        return expired
    
    def get_consistency_bias(self, context: str, to_whom: str) -> float:
        """
        Get bias strength for consistency with promises.
        
        Returns a value that should amplify actions aligned with
        active promises in this context.
        
        Args:
            context: Current context
            to_whom: Who we're interacting with
            
        Returns:
            Bias multiplier (1.0 = neutral, >1.0 = amplify)
        """
        if not self.enabled:
            return 1.0
        
        active = self.get_active_promises(to_whom=to_whom)
        
        if not active:
            return 1.0
        
        # Sum salience of relevant promises
        total_salience = sum(p.salience for p in active if context.lower() in p.context.lower())
        
        # Convert to bias (capped at 1.5x)
        bias = 1.0 + min(0.5, total_salience * 0.3)
        
        return bias
    
    def _evict_old_promises(self) -> None:
        """Remove oldest non-active promises to make room."""
        non_active = [
            (pid, p) for pid, p in self.promises.items()
            if not p.is_active()
        ]
        
        if non_active:
            # Remove oldest
            oldest_id = min(non_active, key=lambda x: x[1].timestamp)[0]
            del self.promises[oldest_id]
    
    def _save(self) -> None:
        """Persist to disk."""
        if not self.path:
            return
        
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        
        data = {
            "promises": [p.to_dict() for p in self.promises.values()],
            "enabled": self.enabled,
        }
        
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    
    def _load(self) -> None:
        """Load from disk."""
        if not self.path or not os.path.exists(self.path):
            return
        
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.enabled = data.get("enabled", True)
            
            for p_data in data.get("promises", []):
                promise = Promise.from_dict(p_data)
                self.promises[promise.id] = promise
        except Exception:
            # Fail gracefully
            pass
    
    def to_dict(self) -> Dict:
        """Serialize for debugging."""
        return {
            "enabled": self.enabled,
            "promise_count": len(self.promises),
            "active_count": len(self.get_active_promises()),
            "broken_count": len(self.get_broken_promises()),
            "promises": [p.to_dict() for p in self.promises.values()],
        }
