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
from .event_schema import (
    EnvironmentEvent,
    EnvironmentEventType,
    dialogue_started_event,
    dialogue_choice_event,
    player_sentiment_event,
    player_hostility_event,
    combat_result_event,
    quest_update_event,
    proximity_update_event,
    gift_event,
    time_passed_event,
)
from .adapters import UnityAdapter, SkyrimAdapter

__all__ = [
    "EventAdapter",
    "GameEvent",
    "GameEventType",
    "ConsequenceMapper",
    "ConsequenceSignal",
    "ConsequenceType",
    "SignalNormalizer",
    # Common event schema
    "EnvironmentEvent",
    "EnvironmentEventType",
    # Event builders
    "dialogue_started_event",
    "dialogue_choice_event",
    "player_sentiment_event",
    "player_hostility_event",
    "combat_result_event",
    "quest_update_event",
    "proximity_update_event",
    "gift_event",
    "time_passed_event",
    # Game engine adapters
    "UnityAdapter",
    "SkyrimAdapter",
]
