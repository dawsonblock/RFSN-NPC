"""
Skyrim Event Feeder - Reference Implementation

This is a reference implementation for feeding Skyrim events to the RFSN-NPC system.
It demonstrates how to translate Skyrim game events into the standardized event format
expected by the RFSN API.

IMPORTANT: This is a Python reference implementation. For actual Skyrim integration,
you would need to implement this in Papyrus or SKSE/C++.

Usage:
    1. Adapt this logic to your Skyrim modding environment (Papyrus or SKSE)
    2. Call the corresponding functions when game events occur
    3. Events are batched and throttled to avoid API spam
    4. Configure the RFSN_API_URL to point to your running RFSN server
"""
from typing import Dict, List, Any
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class SkyrimEvent:
    """
    Skyrim game event to be sent to RFSN.
    
    Attributes:
        event_type: Type of event (combat_start, item_received, etc.)
        npc_id: ID of the affected NPC
        player_id: ID of the player
        magnitude: Event intensity (0.0 to 1.0)
        data: Additional event-specific data
        tags: Classification tags
    """
    event_type: str
    npc_id: str
    player_id: str = "Player"
    magnitude: float = 0.5
    data: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_api_payload(self) -> Dict[str, Any]:
        """Convert to RFSN API payload format."""
        return {
            "event_type": self.event_type,
            "npc_id": self.npc_id,
            "player_id": self.player_id,
            "magnitude": max(0.0, min(1.0, self.magnitude)),
            "ts": time.time(),
            "payload": self.data,
            "version": 1,
        }


class SkyrimEventFeeder:
    """
    Manages Skyrim event batching and throttling.
    
    Features:
    - Event batching (accumulates events before sending)
    - Throttling (rate limits API calls)
    - Priority queue (important events sent immediately)
    """
    
    # Magnitude scaling constants (adjust for your game's economy)
    ITEM_VALUE_MIN_MAGNITUDE = 0.1  # Minimum magnitude for any item
    ITEM_VALUE_SCALE_GOLD = 1000.0  # Gold value for max magnitude
    ITEM_VALUE_MAX_MAGNITUDE = 0.9  # Maximum magnitude boost from value
    
    STOLEN_ITEM_BASE_MAGNITUDE = 0.3  # Base magnitude for theft
    CRIME_BOUNTY_SCALE = 1000.0  # Bounty for max magnitude
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        batch_size: int = 5,
        throttle_seconds: float = 1.0,
    ):
        """
        Initialize event feeder.
        
        Args:
            api_url: Base URL of RFSN API server
            batch_size: Max events to batch before sending
            throttle_seconds: Minimum seconds between API calls
        """
        self.api_url = api_url
        self.batch_size = batch_size
        self.throttle_seconds = throttle_seconds
        
        self.event_queue: List[SkyrimEvent] = []
        self.last_send_time = 0.0
    
    def feed_combat_start(
        self,
        npc_id: str,
        enemy_name: str,
        player_involved: bool = True,
    ):
        """Feed a combat start event."""
        event = SkyrimEvent(
            event_type="combat_start",
            npc_id=npc_id,
            magnitude=0.7,  # Combat is significant
            data={
                "enemy": enemy_name,
                "player_involved": player_involved,
            },
            tags=["combat"],
        )
        self._queue_event(event, priority=True)
    
    def feed_combat_end(
        self,
        npc_id: str,
        victory: bool,
        casualties: int = 0,
    ):
        """Feed a combat end event."""
        magnitude = 0.8 if victory else 0.5
        event = SkyrimEvent(
            event_type="combat_end",
            npc_id=npc_id,
            magnitude=magnitude,
            data={
                "victory": victory,
                "casualties": casualties,
            },
            tags=["combat"],
        )
        self._queue_event(event, priority=True)
    
    def feed_item_received(
        self,
        npc_id: str,
        item_name: str,
        item_value: int,
        from_player: bool = True,
    ):
        """Feed an item received event."""
        # Scale magnitude by item value
        # Formula: min_mag + (value / scale) * max_boost
        magnitude = min(
            1.0,
            self.ITEM_VALUE_MIN_MAGNITUDE + 
            (item_value / self.ITEM_VALUE_SCALE_GOLD) * self.ITEM_VALUE_MAX_MAGNITUDE
        )
        
        event = SkyrimEvent(
            event_type="item_received",
            npc_id=npc_id,
            magnitude=magnitude,
            data={
                "item": item_name,
                "value": item_value,
                "from_player": from_player,
            },
            tags=["item", "gift"] if from_player else ["item"],
        )
        self._queue_event(event, priority=from_player)
    
    def feed_item_stolen(
        self,
        npc_id: str,
        item_name: str,
        item_value: int,
    ):
        """Feed an item stolen event."""
        magnitude = min(
            1.0,
            self.STOLEN_ITEM_BASE_MAGNITUDE + 
            (item_value / self.ITEM_VALUE_SCALE_GOLD) * (1.0 - self.STOLEN_ITEM_BASE_MAGNITUDE)
        )
        
        event = SkyrimEvent(
            event_type="item_stolen",
            npc_id=npc_id,
            magnitude=magnitude,
            data={
                "item": item_name,
                "value": item_value,
            },
            tags=["crime", "theft"],
        )
        self._queue_event(event, priority=True)
    
    def feed_crime_witnessed(
        self,
        npc_id: str,
        crime_type: str,
        bounty: int,
    ):
        """Feed a crime witnessed event."""
        # Scale by bounty
        magnitude = min(1.0, bounty / self.CRIME_BOUNTY_SCALE)
        
        event = SkyrimEvent(
            event_type="witnessed_crime",
            npc_id=npc_id,
            magnitude=magnitude,
            data={
                "crime_type": crime_type,
                "bounty": bounty,
            },
            tags=["crime", "social"],
        )
        self._queue_event(event, priority=True)
    
    def feed_quest_started(
        self,
        npc_id: str,
        quest_name: str,
    ):
        """Feed a quest started event."""
        event = SkyrimEvent(
            event_type="quest_started",
            npc_id=npc_id,
            magnitude=0.6,
            data={"quest": quest_name},
            tags=["quest"],
        )
        self._queue_event(event)
    
    def feed_quest_completed(
        self,
        npc_id: str,
        quest_name: str,
        reward_gold: int = 0,
    ):
        """Feed a quest completed event."""
        event = SkyrimEvent(
            event_type="quest_completed",
            npc_id=npc_id,
            magnitude=0.9,
            data={
                "quest": quest_name,
                "reward": reward_gold,
            },
            tags=["quest", "success"],
        )
        self._queue_event(event, priority=True)
    
    def feed_time_passed(
        self,
        npc_id: str,
        hours: float,
    ):
        """Feed a time passage event (for relationship decay, etc.)."""
        event = SkyrimEvent(
            event_type="time_passed",
            npc_id=npc_id,
            magnitude=min(1.0, hours / 24.0),  # Scale by days
            data={"hours": hours},
            tags=["time"],
        )
        self._queue_event(event)
    
    def feed_location_changed(
        self,
        npc_id: str,
        old_location: str,
        new_location: str,
    ):
        """Feed a location change event."""
        event = SkyrimEvent(
            event_type="location_changed",
            npc_id=npc_id,
            magnitude=0.3,
            data={
                "from": old_location,
                "to": new_location,
            },
            tags=["environment"],
        )
        self._queue_event(event)
    
    def _queue_event(self, event: SkyrimEvent, priority: bool = False):
        """
        Queue an event for sending.
        
        Args:
            event: Event to queue
            priority: If True, send immediately
        """
        if priority:
            self._send_events([event])
        else:
            self.event_queue.append(event)
            if len(self.event_queue) >= self.batch_size:
                self._flush()
    
    def _flush(self):
        """Send all queued events."""
        if not self.event_queue:
            return
        
        # Throttle check
        now = time.time()
        if now - self.last_send_time < self.throttle_seconds:
            logger.debug("Throttled: waiting before sending events")
            return
        
        self._send_events(self.event_queue)
        self.event_queue = []
        self.last_send_time = now
    
    def _send_events(self, events: List[SkyrimEvent]):
        """
        Send events to RFSN API.
        
        NOTE: In actual implementation, this would use HTTP POST.
        For Papyrus, you would use ModEvent or SKSE HTTP functions.
        For SKSE C++, you would use libcurl or similar.
        
        Args:
            events: Events to send
        """
        for event in events:
            payload = event.to_api_payload()
            endpoint = f"{self.api_url}/env/event"
            
            logger.info(f"Sending event to {endpoint}: {payload['event_type']}")
            
            # In a real implementation, perform an HTTP POST request to the endpoint with the
            # payload and handle any non-200 responses appropriately, including logging failures.
    
    def update(self):
        """
        Call this periodically (e.g., every game frame or every second).
        
        Handles throttled flushing of queued events.
        """
        now = time.time()
        if (self.event_queue and 
            now - self.last_send_time >= self.throttle_seconds):
            self._flush()


# Example usage (for testing/reference)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create feeder
    feeder = SkyrimEventFeeder(
        api_url="http://localhost:8000",
        batch_size=3,
        throttle_seconds=1.0,
    )
    
    # Simulate some Skyrim events
    feeder.feed_item_received("lydia", "Ebony Sword", 500, from_player=True)
    feeder.feed_combat_start("lydia", "Bandit", player_involved=True)
    feeder.feed_combat_end("lydia", victory=True, casualties=0)
    feeder.feed_quest_completed("lydia", "Retrieve the Dragonstone", reward_gold=100)
    
    # In real Skyrim mod, you would call feeder.update() in your game loop
    feeder.update()
