# Environment & Decision Policy Wiring - Implementation Guide

This document describes the implementation of the "missing wiring" that connects the bounded NPC brain components into a complete feedback loop.

## What Was Wired

The RFSN-NPC system already had all the right pieces:
- Event-sourced state management (StateStore + Reducer)
- Environment feedback stack (event adapters, consequence mapper, signal normalizer)
- Decision policy (bounded action set with affinity gating)
- Learning system (LearningState + PolicyAdjuster)

What was missing: **the wiring between these components**.

## The Complete Feedback Loop

```
┌─────────────┐
│   Player    │
│   Action    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  1. Parse Event                     │
│     (state_machine.parse_event)     │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  2. Update State                    │
│     (StateStore.dispatch)           │
│     - PLAYER_EVENT                  │
│     - FACT_ADD (user message)       │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  3. Build Decision Context          │
│     (build_decision_context_key)    │
│     - Bucket affinity               │
│     - Include mood                  │
│     - Include recent events         │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  4. Choose Bounded Action           │
│     (DecisionPolicy.choose_action)  │
│     - Get allowed actions           │
│     - Apply learned weights         │
│     - Select deterministically      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  5. Generate Response               │
│     (LLM with action directive)     │
│     - System prompt + directive     │
│     - Style hint                    │
│     - Relevant facts                │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  6. Store Last Action               │
│     (for learning feedback)         │
└─────────────────────────────────────┘

       ┌──────────────────┐
       │  Environment     │
       │  Event (gift,    │
       │  combat, etc.)   │
       └────────┬─────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  7. Map to Consequences    │
       │     (ConsequenceMapper)    │
       └────────┬───────────────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  8. Normalize Signals      │
       │     (SignalNormalizer)     │
       └────────┬───────────────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  9. Apply to State         │
       │     (AFFINITY_DELTA,       │
       │      MOOD_SET, FACT_ADD)   │
       └────────┬───────────────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  10. Calculate Δ Affinity  │
       │      (post - pre)          │
       └────────┬───────────────────┘
                │
                ▼
       ┌────────────────────────────┐
       │  11. Update Action Weights │
       │      (PolicyAdjuster)      │
       │      - decision namespace  │
       │      - style namespace     │
       └────────────────────────────┘
```

## API Endpoints

### 1. Enable Learning
```bash
POST /npc/{npc_id}/learning
```

Request:
```json
{
  "enabled": true
}
```

Response:
```json
{
  "npc_id": "Lydia",
  "enabled": true,
  "decision": {
    "enabled": true,
    "total_entries": 0,
    "avg_weight": 1.0,
    "avg_success_rate": 0.5,
    "exploration_rate": 0.1,
    "learning_rate": 0.05
  },
  "style": {
    "enabled": true,
    "total_entries": 0,
    "avg_weight": 1.0,
    "avg_success_rate": 0.5,
    "exploration_rate": 0.1,
    "learning_rate": 0.05
  }
}
```

### 2. Chat (with Decision Policy)
```bash
POST /npc/{npc_id}/chat
```

Request:
```json
{
  "message": "Hello, how are you?",
  "player_name": "Player"
}
```

Response:
```json
{
  "text": "*Lydia smiles warmly* I am well, thank you for asking.",
  "state": {
    "npc_name": "Lydia",
    "affinity": 0.542,
    "mood": "Pleased",
    ...
  },
  "facts_used": ["Player: Hello", "Lydia: Hi there"],
  "decision": {
    "context_key": "aff:1|mood:pleased|pevents:TALK",
    "action": "greet",
    "style": "warm"
  }
}
```

### 3. Environment Event
```bash
POST /env/event
```

Request (Gift):
```json
{
  "event_type": "gift",
  "npc_id": "Lydia",
  "player_id": "Player",
  "payload": {
    "magnitude": 0.8,
    "item": "Steel Sword"
  }
}
```

Request (Combat):
```json
{
  "event_type": "combat_damage_taken",
  "npc_id": "Lydia",
  "player_id": "Player",
  "payload": {
    "magnitude": 0.6,
    "source": "bandit"
  }
}
```

Response:
```json
{
  "ok": true,
  "npc_id": "Lydia",
  "event_type": "gift",
  "normalized": {
    "consequence_type": "bonding",
    "intensity": 0.240,
    "affinity_delta": 0.019,
    "mood_impact": null
  },
  "state": {
    "affinity": 0.561,
    "mood": "Pleased",
    ...
  }
}
```

## Supported Environment Events

| Event Type | Description | Effect |
|-----------|-------------|--------|
| `gift` | Player gives item to NPC | +affinity (bonding) |
| `theft` | Player steals from NPC | -affinity (alienation) |
| `combat_started` | Combat initiated with NPC | -affinity (stress, threat) |
| `combat_ended` | Combat finished | +mood (relief) |
| `combat_damage_taken` | NPC takes damage | -affinity (stress, threat) |
| `combat_damage_dealt` | NPC deals damage | +mood (achievement) |
| `quest_started` | Quest begun with NPC | neutral |
| `quest_completed` | Quest finished successfully | +affinity (achievement, bonding) |
| `quest_failed` | Quest failed | -affinity (failure, alienation) |
| `crime_witnessed` | NPC sees player commit crime | -affinity (injustice, alienation) |
| `assist` | Player helps NPC | +affinity (justice, bonding) |
| `dialogue_started` | Conversation begins | +affinity (bonding) |
| `dialogue_ended` | Conversation ends | neutral |
| `dialogue_choice` | Player makes dialogue choice | depends on choice |
| `player_hostility` | Player acts hostile | -affinity (threat) |
| `time_passed` | Time advances in game | +mood (relief, decay) |
| `location_changed` | NPC moves to new location | neutral |

## Decision Policy - Action Set

The decision policy gates actions based on affinity and mood:

### Hostile Actions (require low affinity < -0.3)
- `threaten` - Make a direct threat
- `call_guard` - Call for guards
- `flee` - Express fear and leave
- `warn` - Issue a warning

### Friendly Actions (require high affinity > 0.2)
- `offer_quest` - Suggest a quest
- `offer_gift` - Give something to player
- `follow` - Offer to accompany
- `express_gratitude` - Thank the player

### Neutral Actions (no requirements)
- `greet` - Greet the player
- `smalltalk` - Make casual conversation
- `ask_question` - Ask player something
- `give_info` - Provide information
- `deflect` - Avoid the topic
- `end_conversation` - End interaction
- `barter` - Discuss trade
- `request_item` - Ask for something
- `wait` - Indicate waiting
- `disengage` - Excuse yourself
- `approach` - Show interest
- `express_concern` - Voice worry
- `apologize` - Offer apology
- `complain` - Express frustration
- `request_help` - Ask for assistance
- `accept_quest` - Agree to help
- `decline` - Refuse politely

## Learning System

### Two Namespaces

1. **Decision Namespace**: Reweights action selection
   - Key: `(context_key, action)` → weight
   - Example: `("aff:1|mood:pleased", "offer_quest")` → 1.2

2. **Style Namespace**: Reweights speech styles
   - Key: `(context_key, style_hint)` → weight
   - Example: `("aff:1|mood:pleased", "warm")` → 1.1

### Learning Parameters

- **Exploration Rate**: 10% (epsilon-greedy)
- **Learning Rate**: 5% (weight update step size)
- **Weight Bounds**: [0.5, 2.0] (prevents complete suppression or runaway)
- **Max Entries**: 100 per namespace per NPC
- **Eviction Policy**: LRU (Least Recently Used)
- **Persistence**: JSON files in `state/learning/{npc_id}.json`

### Feedback Signals

Learning updates occur when:
1. Environment event changes affinity
2. Affinity delta > 1e-9 (not negligible)
3. Last action was recorded for this NPC

Reward calculation:
```python
if affinity_delta > 0.1:
    outcome_type = RELATIONSHIP_IMPROVED
    intensity = abs(affinity_delta) * 5.0
elif affinity_delta < -0.1:
    outcome_type = RELATIONSHIP_DAMAGED
    intensity = abs(affinity_delta) * 5.0
else:
    outcome_type = DIALOGUE_SUCCESS
    intensity = 0.0

reward = base_reward[outcome_type] * intensity
new_weight = clamp(
    old_weight + learning_rate * reward,
    min=0.5,
    max=2.0
)
```

## Context Key Format

Context keys bucket similar situations for learning generalization:

```
aff:{bucket}|mood:{mood}|pevents:{types}|eevents:{types}
```

### Affinity Buckets
- `-2`: Very negative (< -0.6)
- `-1`: Negative (-0.6 to -0.2)
- `0`: Neutral (-0.2 to 0.2)
- `1`: Positive (0.2 to 0.6)
- `2`: Very positive (>= 0.6)

### Examples
```
aff:2|mood:pleased|pevents:GIFT|eevents:quest_completed
aff:-1|mood:angry|pevents:INSULT
aff:0|mood:neutral|pevents:TALK
aff:1|mood:grateful|pevents:HELP|eevents:gift
```

## Bounded State Guarantees

### Affinity Changes
- **Per event**: max ±0.15 (SignalNormalizer.max_affinity_change)
- **After dampening**: multiplied by 0.5 (SignalNormalizer.dampening_factor)
- **After aggregation**: multiplied by 0.8^(n-1) for n simultaneous events
- **Final range**: [0.0, 1.0] (clamped by reducer)

### Mood Changes
- Only triggered if normalized intensity > 0.4
- Mapped from consequence types:
  - `stress` → "Anxious"
  - `relief` → "Calm"
  - `threat` → "Fearful"
  - `bonding` → "Warm"
  - `alienation` → "Distant"
  - `achievement` → "Proud"
  - etc.

### Facts
- Stored as immutable Fact objects with salience [0.0, 1.0]
- Tagged for retrieval: `["chat", "user"]`, `["env", "gift"]`, etc.
- Keyword + recency selection for context (limit=5)

## Testing

Run the complete test suite:
```bash
# Unit tests
pytest tests/test_env_decision_wiring.py -v

# Integration tests
pytest tests/test_integration.py -v

# Decision policy tests
pytest tests/test_decision_policy.py -v

# All tests
pytest tests/ -k "not operational" -q
```

Run verification scripts:
```bash
# Engine-level verification
python verify_wiring.py

# API-level verification
python test_api_integration.py
```

## Example Usage (Python)

```python
from rfsn_hybrid.engine import RFSNHybridEngine
from rfsn_hybrid.environment import EnvironmentEvent

# Initialize engine
engine = RFSNHybridEngine()
npc_id = "Lydia"

# Enable learning
engine.enable_learning(npc_id, enabled=True)

# Chat
response = engine.handle_message(
    npc_id=npc_id,
    text="I brought you a gift!",
    user_name="Player"
)
print(f"NPC: {response['text']}")
print(f"Action: {response['decision']['action']}")
print(f"Affinity: {response['state']['affinity']:.3f}")

# Send environment event
gift_event = EnvironmentEvent(
    event_type="gift",
    npc_id=npc_id,
    player_id="Player",
    payload={"magnitude": 0.8, "item": "Steel Sword"}
)
result = engine.handle_env_event(gift_event)
print(f"Affinity delta: {result['normalized']['affinity_delta']:+.3f}")
print(f"New affinity: {result['state']['affinity']:.3f}")

# Chat again (with updated context and learning)
response2 = engine.handle_message(
    npc_id=npc_id,
    text="Will you follow me?",
    user_name="Player"
)
print(f"NPC: {response2['text']}")
print(f"Context: {response2['decision']['context_key']}")
```

## Example Usage (Unity C#)

```csharp
using UnityEngine;
using System.Collections;
using UnityEngine.Networking;

public class RFSNClient : MonoBehaviour
{
    private string apiUrl = "http://localhost:8000";
    
    // Enable learning
    IEnumerator EnableLearning(string npcId)
    {
        string json = "{\"enabled\": true}";
        var request = new UnityWebRequest($"{apiUrl}/npc/{npcId}/learning", "POST");
        request.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");
        
        yield return request.SendWebRequest();
        
        if (request.result == UnityWebRequest.Result.Success)
        {
            Debug.Log($"Learning enabled: {request.downloadHandler.text}");
        }
    }
    
    // Chat
    IEnumerator Chat(string npcId, string message)
    {
        string json = $"{{\"message\": \"{message}\", \"player_name\": \"Player\"}}";
        var request = new UnityWebRequest($"{apiUrl}/npc/{npcId}/chat", "POST");
        request.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");
        
        yield return request.SendWebRequest();
        
        if (request.result == UnityWebRequest.Result.Success)
        {
            var response = JsonUtility.FromJson<ChatResponse>(request.downloadHandler.text);
            Debug.Log($"NPC: {response.text}");
            Debug.Log($"Action: {response.decision.action}");
        }
    }
    
    // Send environment event
    IEnumerator SendEvent(string npcId, string eventType, float magnitude, string item = null)
    {
        var eventData = new EnvironmentEventData {
            event_type = eventType,
            npc_id = npcId,
            player_id = "Player",
            payload = new EventPayload {
                magnitude = magnitude,
                item = item
            }
        };
        
        string json = JsonUtility.ToJson(eventData);
        var request = new UnityWebRequest($"{apiUrl}/env/event", "POST");
        request.uploadHandler = new UploadHandlerRaw(System.Text.Encoding.UTF8.GetBytes(json));
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");
        
        yield return request.SendWebRequest();
        
        if (request.result == UnityWebRequest.Result.Success)
        {
            Debug.Log($"Event processed: {request.downloadHandler.text}");
        }
    }
}

[System.Serializable]
public class EnvironmentEventData
{
    public string event_type;
    public string npc_id;
    public string player_id;
    public EventPayload payload;
}

[System.Serializable]
public class EventPayload
{
    public float magnitude;
    public string item;
}

[System.Serializable]
public class ChatResponse
{
    public string text;
    public StateData state;
    public DecisionData decision;
}

[System.Serializable]
public class StateData
{
    public float affinity;
    public string mood;
}

[System.Serializable]
public class DecisionData
{
    public string action;
    public string style;
    public string context_key;
}
```

## Files Changed

### Core Engine Changes
- `rfsn_hybrid/engine.py`: Added decision policy, learning, and env event wiring
- `rfsn_hybrid/api.py`: Added learning endpoint and wired env event processing

### Bug Fixes
- `rfsn_hybrid/environment/event_schema.py`: Fixed None timestamp handling

### Tests Added
- `tests/test_env_decision_wiring.py`: 8 focused tests for new wiring
- `test_api_integration.py`: End-to-end API integration test
- `verify_wiring.py`: Manual verification script

### Configuration
- `.gitignore`: Added `state/learning/*.json` to ignore learning artifacts

## Performance Notes

- **Thread Safety**: All state access protected by locks
- **Memory**: Bounded at 100 entries per NPC per namespace
- **Disk I/O**: Learning state persisted on every weight update
- **Determinism**: Same inputs → same outputs (seeded RNG)
- **Latency**: ~1-5ms per chat turn (without LLM), ~50-500ms with LLM

## Next Steps (Not Implemented)

The problem statement mentions potential future upgrades:
1. **Goal stacks**: Track quests, promises, obligations as bounded state
2. **Social dimensions**: Add trust/fear/attraction/resentment to context
3. **Two-stage decisions**: "What" (action) then "How hard" (intensity)
4. **Mode controller**: Add explicit combat/idle/dialogue modes

These are NOT part of this PR but could be added later as surgical drop-ins.
