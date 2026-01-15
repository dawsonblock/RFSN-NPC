"""
Environment feedback layer for RFSN NPC system.

This module ingests environmental events and converts them into
normalized signals that feed into the reducer and learning systems.

Key principles:
- NPCs "feel" the world without reasoning about it
- Events are converted to simple signal vectors
- Signals are normalized and bounded
- All processing goes through the reducer

Design:
- Event adapter: ingests raw game events
- Consequence mapper: maps events to NPC-relevant signals
- Signal normalizer: ensures consistency and bounds
"""

from .event_adapter import EventAdapter, GameEvent, GameEventType
from .consequence_mapper import ConsequenceMapper, ConsequenceSignal, ConsequenceType
from .signal_normalizer import SignalNormalizer

__all__ = [
    "EventAdapter",
    "GameEvent",
    "GameEventType",
    "ConsequenceMapper",
    "ConsequenceSignal",
    "ConsequenceType",
    "SignalNormalizer",
]
