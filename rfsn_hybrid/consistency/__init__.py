"""
Long-horizon consistency system for RFSN NPCs.

Tracks implicit commitments, unresolved conflicts, and tensions
that bias future behavior WITHOUT planning.

Key principles:
- No autonomous planning
- No goal trees
- Just memory + bias
- Debuggable and explainable
"""

from .promise_tracker import PromiseTracker, Promise, PromiseStatus
from .grievance_log import GrievanceLog, Grievance, GrievanceSeverity
from .unresolved_tension import TensionTracker, Tension, TensionType

__all__ = [
    "PromiseTracker",
    "Promise",
    "PromiseStatus",
    "GrievanceLog",
    "Grievance",
    "GrievanceSeverity",
    "TensionTracker",
    "Tension",
    "TensionType",
]
