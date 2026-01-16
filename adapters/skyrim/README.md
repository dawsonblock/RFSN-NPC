# Skyrim Integration Guide for RFSN-NPC

This guide explains how to integrate RFSN-NPC with Skyrim to create dynamic, learning NPCs that respond to the player's actions and the game world.

## Overview

The Skyrim adapter translates game events (combat, items, quests, crimes) into the standardized RFSN event format. These events update NPC state (affinity, mood) and enable learning over time.

## Architecture

```
Skyrim Game Event → Event Feeder → RFSN API (/env/event) → State Reducer → NPC State
```

## Implementation Options

### Option 1: Papyrus Script (Simplest)

Use Skyrim's native scripting language. Requires SKSE for HTTP support.

**Pros:**
- Native Skyrim integration
- Easy to install as mod
- Access to all game events

**Cons:**
- Papyrus is slow
- Requires SKSE HTTP plugin
- Limited to Skyrim's event system

### Option 2: SKSE Plugin (Best Performance)

Implement as C++ SKSE plugin.

**Pros:**
- Fast
- Direct access to game engine
- Can hook any event

**Cons:**
- Requires C++ development
- More complex to build/distribute
- SKSE version specific

## Step-by-Step Integration

### 1. Setup RFSN Server

Start the RFSN API server on your local machine or a networked server:

```bash
cd RFSN-NPC
uvicorn rfsn_hybrid.api:app --host 0.0.0.0 --port 8000
```

### 2. Implement Event Hooks

The `skyrim_event_feeder.py` file provides a Python reference implementation. You need to adapt this logic to Papyrus or C++.

#### Key Events to Hook:

**Combat Events:**
- `OnCombatStateChanged` → `feed_combat_start()` / `feed_combat_end()`
- `OnHit` → Track damage for magnitude

**Item Events:**
- `OnItemAdded` → `feed_item_received()`
- `OnItemRemoved` (if stolen) → `feed_item_stolen()`

**Quest Events:**
- `OnQuestStarted` → `feed_quest_started()`
- `OnQuestCompleted` → `feed_quest_completed()`

**Social Events:**
- `OnCrimeGold` → `feed_crime_witnessed()`
- `OnLocationChanged` → `feed_location_changed()`

**Time Events:**
- Track game hours → `feed_time_passed()` (for relationship decay)

### 3. API Call Format

All events use the same endpoint: `POST /env/event`

**Request Body:**
```json
{
  "event_type": "combat_start",
  "npc_id": "lydia",
  "player_id": "Player",
  "magnitude": 0.7,
  "ts": 1234567890.123,
  "payload": {
    "enemy": "Bandit",
    "player_involved": true
  },
  "version": 1
}
```

**Response:**
```json
{
  "ok": true,
  "npc_state": {
    "affinity": 0.52,
    "mood": "Concerned"
  }
}
```

### 4. Papyrus Example (Pseudocode)

```papyrus
Scriptname RFSNEventAdapter extends Quest

String Property RFSN_API_URL = "http://localhost:8000" Auto

Function OnCombatStart(Actor npc, Actor target)
    String npcId = npc.GetName()
    String enemyName = target.GetName()
    
    String payload = "{"
    payload += "\"event_type\": \"combat_start\","
    payload += "\"npc_id\": \"" + npcId + "\","
    payload += "\"player_id\": \"Player\","
    payload += "\"magnitude\": 0.7,"
    payload += "\"payload\": {\"enemy\": \"" + enemyName + "\"}"
    payload += "}"
    
    ; Requires SKSE HTTP plugin
    SKSE.HttpPost(RFSN_API_URL + "/env/event", payload)
EndFunction

Function OnItemReceived(Actor npc, Form item, int count)
    String npcId = npc.GetName()
    String itemName = item.GetName()
    int itemValue = item.GetGoldValue()
    
    String payload = "{"
    payload += "\"event_type\": \"item_received\","
    payload += "\"npc_id\": \"" + npcId + "\","
    payload += "\"magnitude\": " + (itemValue / 1000.0) + ","
    payload += "\"payload\": {\"item\": \"" + itemName + "\", \"value\": " + itemValue + "}"
    payload += "}"
    
    SKSE.HttpPost(RFSN_API_URL + "/env/event", payload)
EndFunction
```

### 5. Event Throttling

To avoid API spam:
- Batch events (send every 1-2 seconds)
- Priority events (combat, crimes) send immediately
- Low-priority events (time, location) batch

See `SkyrimEventFeeder._queue_event()` in the reference implementation.

### 6. Testing

1. Start RFSN server
2. Load Skyrim with your adapter mod
3. Interact with NPCs
4. Monitor API logs: `/npc/{npc_id}/history`

## Event Type Reference

| Event Type | Magnitude | Triggers |
|------------|-----------|----------|
| `combat_start` | 0.7 | Combat begins |
| `combat_end` | 0.5-0.8 | Combat ends (victory=0.8) |
| `item_received` | 0.1-1.0 | Item given (scaled by value) |
| `item_stolen` | 0.3-1.0 | Item stolen (scaled by value) |
| `witnessed_crime` | 0.0-1.0 | NPC sees crime (scaled by bounty) |
| `quest_started` | 0.6 | Quest begins |
| `quest_completed` | 0.9 | Quest finishes |
| `time_passed` | 0.0-1.0 | Hours pass (for decay) |
| `location_changed` | 0.3 | NPC moves locations |

## Troubleshooting

**Problem:** Events not reaching API
- Check RFSN server is running
- Verify network connectivity
- Check Papyrus logs for HTTP errors

**Problem:** NPCs not responding to events
- Verify NPC ID matches between game and API
- Check `/npc/{npc_id}/history` to see received events
- Ensure events have correct magnitude and format

**Problem:** Performance issues
- Increase throttle time (fewer API calls)
- Increase batch size (more events per call)
- Use priority queue (only important events immediate)

## Advanced: Custom Events

You can create custom event types for mod-specific behaviors:

```python
feeder.feed_custom_event(
    npc_id="custom_npc",
    event_type="mod_specific_event",
    magnitude=0.5,
    data={"custom_field": "value"},
    tags=["custom"],
)
```

The RFSN system will normalize and process any event type.

## Next Steps

1. Implement adapter in your preferred language
2. Test with a single NPC
3. Expand to multiple NPCs
4. Enable learning mode (see LEARNING_GUIDE.md)
5. Fine-tune event magnitudes based on gameplay

## Resources

- RFSN API Documentation: See `api.py`
- Event Schema: `rfsn_hybrid/environment/event_adapter.py`
- Example Implementation: `skyrim_event_feeder.py`
