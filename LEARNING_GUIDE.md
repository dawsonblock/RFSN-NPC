# RFSN Learning Module Guide

## Overview

The RFSN Learning Module is a **drop-in** contextual bandit system that enables NPCs to learn from outcomes without breaking determinism, replay, or boundedness. Learning is **disabled by default** and completely optional.

## Key Principles

1. **Reducer remains the only authority** - Learning cannot directly change state
2. **Bounded and stable** - No deep nets, no unbounded logs, fixed memory budget
3. **Deterministic** - Replay-safe with seeded PRNG
4. **Explainable** - Small numeric biases, clear feature encoding
5. **Drop-in** - Minimal changes to existing code, behind feature flags

## Architecture

```
┌─────────────────┐
│  Game Events    │ (Dialogue, Combat, Quests, etc.)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Event Adapter   │ (Normalize events)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Feature Encoder │ (State → Features)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LinUCB Bandit   │ (Action scoring)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PolicyBias     │ (Action biases)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Reducer      │ (Apply biases to action selection)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Outcome         │ (Evaluate results)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Learning Update │ (Update weights)
└─────────────────┘
```

## Components

### 1. LearningConfig

Configuration with safe defaults:

```python
from rfsn_hybrid.learning import LearningConfig, LearningPresets

# Default: Learning disabled
config = LearningConfig()

# Use presets
config = LearningPresets.conservative()  # Slow, safe
config = LearningPresets.moderate()      # Recommended
config = LearningPresets.aggressive()    # Fast (use with caution)
config = LearningPresets.deterministic_test(seed=42)  # Testing
```

**Key parameters:**
- `enabled`: Master switch (default: `False`)
- `exploration_rate`: ε-greedy exploration (default: `0.05`)
- `learning_rate`: Update speed (default: `0.05`)
- `max_entries`: Maximum (context, action) pairs (default: `100`)
- `prng_seed`: Seed for determinism (default: `None` = random)

### 2. FeatureEncoder

Converts NPC state into fixed-size feature vectors:

```python
from rfsn_hybrid.learning import FeatureEncoder

encoder = FeatureEncoder()

features = encoder.encode(
    affinity=0.5,
    mood="Pleased",
    recent_events=["GIFT", "PRAISE"],
    relationship_state={"duration_normalized": 0.3},
    environment_signals={"tension": 0.2, "hostility": 0.1},
)

print(features.context_key)  # "aff:mid|mood:pleased"
print(features.features)     # Dict of normalized features
```

**Features include:**
- Affinity (raw + bucketed)
- Mood (one-hot encoded)
- Recent event patterns (hashed)
- Relationship metadata
- Environment signals

All features are **bounded** and **versioned** for compatibility.

### 3. LinUCBBandit

Contextual bandit learner with LinUCB algorithm:

```python
from rfsn_hybrid.learning import LinUCBBandit

bandit = LinUCBBandit(alpha=0.2, prng_seed=42)

# Score actions
context = {"affinity_raw": 0.5, "mood_pleased": 1.0}
actions = ["friendly", "neutral", "hostile"]
scores = bandit.score_actions(context, actions)

# Choose best action
chosen = max(scores, key=scores.get)

# Update based on outcome
bandit.update(context, chosen, reward=0.7)
```

**Properties:**
- Balances exploration (via UCB) and exploitation
- Bounded parameters (theta clamped to [-2, 2])
- Deterministic with fixed seed

### 4. OutcomeEvaluator

Converts game events into reward signals:

```python
from rfsn_hybrid.learning import OutcomeEvaluator, OutcomeType

evaluator = OutcomeEvaluator()

# From affinity change
outcome = evaluator.evaluate_from_affinity_change(
    affinity_delta=0.3,
    context="ctx",
    action="friendly_response",
)

# From player event
outcome = evaluator.evaluate_from_player_event(
    player_event_type="GIFT",
    context="ctx",
    action="response",
)

print(outcome.reward)  # -1.0 to 1.0
```

**Reward types:**
- Dialogue success/failure
- Quest completion/failure
- Relationship improvement/damage
- Player reactions
- Combat outcomes

### 5. PolicyBias

Output consumed by reducer:

```python
from rfsn_hybrid.learning import PolicyBias

# Neutral bias (no effect)
bias = PolicyBias.neutral()

# With biases
bias = PolicyBias(
    action_bias={
        "friendly_response": 0.5,   # Boost by 0.5
        "hostile_response": -0.3,   # Reduce by 0.3
    },
    metadata={"confidence": 0.8},
)

# Check if bias has effect
if bias:
    # Apply biases to action scores
    pass
```

### 6. LearningPersistence

Atomic persistence with crash recovery:

```python
from rfsn_hybrid.learning import LearningPersistence

persistence = LearningPersistence("./state/learning")

# Save
persistence.snapshot("npc_id", config, learning_state, bandit)

# Restore
data = persistence.restore("npc_id")
```

## Integration

### With Reducer

```python
from rfsn_hybrid.core.state.reducer import reduce_state
from rfsn_hybrid.learning import PolicyBias

# Create bias
bias = PolicyBias(action_bias={"action_a": 0.5})

# Pass to reducer
new_state, facts, _ = reduce_state(
    state=current_state,
    event=event,
    facts=facts,
    policy_bias=bias,  # Optional
)
```

### With Environment Events

```python
from rfsn_hybrid.environment import (
    dialogue_started_event,
    player_sentiment_event,
    combat_result_event,
)

# Create events
event1 = dialogue_started_event("lydia", "player_1")
event2 = player_sentiment_event("lydia", "player_1", sentiment=0.7)
event3 = combat_result_event("lydia", "player_1", result="win")

# Send to API
import requests
requests.post("http://localhost:8000/env/event", json=event1.to_dict())
```

## Unity Integration

### C# Example

```csharp
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;

public class RFSNSender : MonoBehaviour {
    public string serverUrl = "http://localhost:8000/env/event";
    
    public void SendDialogueStarted(string npcId) {
        StartCoroutine(PostEvent("dialogue_started", npcId));
    }
    
    IEnumerator PostEvent(string eventType, string npcId) {
        string json = $"{{\"event_type\":\"{eventType}\",\"npc_id\":\"{npcId}\",\"player_id\":\"player_1\"}}";
        byte[] data = System.Text.Encoding.UTF8.GetBytes(json);
        
        using (UnityWebRequest req = new UnityWebRequest(serverUrl, "POST")) {
            req.uploadHandler = new UploadHandlerRaw(data);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            yield return req.SendWebRequest();
        }
    }
}
```

### Hook Points

1. **Dialogue System**: `OnDialogueStart()` → `SendEvent("dialogue_started")`
2. **Combat System**: `OnCombatEnd()` → `SendEvent("combat_result")`
3. **Quest System**: `OnQuestComplete()` → `SendEvent("quest_completed")`
4. **Proximity**: `OnTriggerEnter()` → `SendEvent("proximity_entered")`

## Skyrim Integration

### Method 1: File-Drop (Papyrus-only)

```papyrus
; Write JSON to watched directory
String json = "{\"event_type\":\"dialogue_started\",\"npc_id\":\"lydia\"}"
MiscUtil.WriteToFile("Data/SKSE/Plugins/RFSN/events/event_001.json", json, false, false)
```

RFSN polls this directory and processes events.

### Method 2: HTTP (with SKSE plugin)

If you have an SKSE plugin with HTTP support:

```papyrus
; POST to RFSN API
String url = "http://localhost:8000/env/event"
String json = "{\"event_type\":\"dialogue_started\",\"npc_id\":\"lydia\"}"
HttpPost(url, json)
```

## Testing

### Run Tests

```bash
# All learning tests
pytest tests/test_learning.py tests/test_learning_enhanced.py -v

# Specific test class
pytest tests/test_learning_enhanced.py::TestLinUCBBandit -v

# With coverage
pytest tests/test_learning*.py --cov=rfsn_hybrid.learning
```

### Run Demo

```bash
python demo_learning.py
```

## Tuning Guide

### Safe Ranges

| Parameter | Conservative | Moderate | Aggressive |
|-----------|-------------|----------|-----------|
| `learning_rate` | 0.02 | 0.05 | 0.10 |
| `exploration_rate` | 0.10 | 0.05 | 0.15 |
| `clamp_alpha` | 0.1 | 0.2 | 0.3 |

### Monitoring

Check learning statistics:

```python
stats = adjuster.get_statistics()
print(stats["total_entries"])      # How many (context, action) pairs
print(stats["avg_weight"])         # Average weight (should stay near 1.0)
print(stats["avg_success_rate"])   # Average success rate
```

### Debugging

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

View learning state:

```python
weights = learning_state.get_all_weights()
for weight in weights:
    print(f"{weight.action} in {weight.context_key}: {weight.weight:.2f}")
    print(f"  Success rate: {weight.success_rate:.2f}")
```

## Common Issues

### Learning Not Working

**Problem**: Weights stay at 1.0

**Solutions**:
1. Check `config.enabled = True`
2. Verify rewards are non-zero
3. Ensure `learning_rate > 0`
4. Check context keys are consistent

### Unstable Learning

**Problem**: Weights oscillate wildly

**Solutions**:
1. Reduce `learning_rate` (try 0.02)
2. Increase `clamp_alpha` to limit updates
3. Use more conservative `exploration_rate`
4. Check reward signals are normalized

### Memory Growing

**Problem**: Learning state uses too much memory

**Solutions**:
1. Reduce `max_entries` (default: 100)
2. Use coarser context keys (fewer buckets)
3. Enable LRU eviction (automatic)

## Best Practices

1. **Start Conservative**: Use `LearningPresets.conservative()` initially
2. **Monitor Metrics**: Check statistics regularly
3. **Use Fixed Seeds**: For development and testing
4. **Validate Rewards**: Ensure reward signals make sense
5. **Snapshot Often**: Set `snapshot_every_n_events` appropriately
6. **Test Determinism**: Verify replay produces identical results

## API Reference

See inline documentation in:
- `rfsn_hybrid/learning/learning_config.py`
- `rfsn_hybrid/learning/feature_encoder.py`
- `rfsn_hybrid/learning/bandit.py`
- `rfsn_hybrid/learning/outcome_evaluator.py`
- `rfsn_hybrid/learning/policy_adjuster.py`
- `rfsn_hybrid/learning/persistence_hooks.py`

## Future Enhancements

Potential improvements (not yet implemented):
- Eligibility traces for delayed rewards
- Multi-armed contextual bandits
- Thompson Sampling alternative
- Feature importance analysis
- A/B testing framework
