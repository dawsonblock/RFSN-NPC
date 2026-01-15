# RFSN Learning Module - Implementation Summary

## Overview

This implementation adds a **drop-in contextual bandit learning system** to RFSN-NPC that enables NPCs to learn from outcomes while maintaining:
- ✅ Deterministic replay
- ✅ Bounded state and memory
- ✅ Reducer authority
- ✅ Explainability
- ✅ Safety (disabled by default)

## What Was Changed

### New Files Created

#### Core Learning Components (`rfsn_hybrid/learning/`)
1. **`learning_config.py`** (151 lines)
   - `LearningConfig` dataclass with bounded parameters
   - `LearningPresets` for safe configurations
   - All parameters clamped to safe ranges
   - Default: learning disabled

2. **`feature_encoder.py`** (240 lines)
   - `FeatureEncoder` class for state → features
   - `FeatureVector` dataclass
   - Schema versioning (`FEATURE_SCHEMA_VERSION = 1`)
   - Fixed-size, bounded, interpretable features

3. **`bandit.py`** (262 lines)
   - `LinUCBBandit` contextual bandit learner
   - `BanditArm` dataclass for arm statistics
   - Diagonal covariance approximation for efficiency
   - Deterministic with seeded PRNG
   - Bounded updates (theta clamped to [-2, 2])

4. **`persistence_hooks.py`** (236 lines)
   - `LearningPersistence` class
   - Atomic writes (temp file + rename)
   - Version compatibility checking
   - `restore_learning_components()` helper
   - Graceful degradation on load failure

5. **`__init__.py`** - Updated (89 lines)
   - Added `PolicyBias` frozen dataclass
   - Exports all learning components
   - `PolicyBias.neutral()` for no-effect bias

#### Environment Adapters (`rfsn_hybrid/environment/`)
6. **`event_schema.py`** (363 lines)
   - `EnvironmentEvent` dataclass
   - `EnvironmentEventType` enum (20+ event types)
   - Event builder helpers (dialogue, combat, quest, etc.)
   - JSON serialization/deserialization
   - Event validation

7. **`adapters/__init__.py`** (7 lines)
   - Exports `UnityAdapter` and `SkyrimAdapter`

8. **`adapters/unity_adapter.py`** (141 lines)
   - `UnityAdapter` class
   - C# integration example
   - Documentation for Unity developers
   - Hook point recommendations

9. **`adapters/skyrim_adapter.py`** (177 lines)
   - `SkyrimAdapter` class
   - File-drop polling support
   - HTTP POST support (with SKSE)
   - Papyrus code examples
   - Event mapping documentation

#### Tests (`tests/`)
10. **`test_learning_enhanced.py`** (388 lines)
    - 23 new comprehensive tests
    - Tests for all new components:
      - `TestLearningConfig` (4 tests)
      - `TestFeatureEncoder` (5 tests)
      - `TestLinUCBBandit` (6 tests)
      - `TestLearningPersistence` (3 tests)
      - `TestPolicyBias` (2 tests)
      - `TestLearningIntegration` (3 tests)
    - End-to-end learning cycle test
    - Deterministic replay verification

#### Documentation & Demos
11. **`demo_learning.py`** (374 lines)
    - Interactive demo script
    - 7 demonstration scenarios:
      1. Disabled vs enabled
      2. Feature encoding
      3. Contextual bandit
      4. Outcome evaluation
      5. Policy adjuster
      6. Persistence
      7. Deterministic replay

12. **`LEARNING_GUIDE.md`** (488 lines)
    - Complete usage guide
    - Architecture diagram
    - Component documentation
    - Unity integration guide
    - Skyrim integration guide
    - Testing instructions
    - Tuning guide
    - Troubleshooting
    - Best practices

### Modified Files

#### `rfsn_hybrid/core/state/reducer.py`
**Changes:**
- Added optional `PolicyBias` import (with fallback)
- Added optional `policy_bias` parameter to `reduce_state()`
- Added optional `policy_bias` parameter to `reduce_events()`
- Updated docstrings to explain PolicyBias integration
- **No breaking changes** - parameter is optional

**Lines changed:** ~20 lines

#### `rfsn_hybrid/api.py`
**Changes:**
- Added `logging` import
- Added `HTTPException` import
- Added `EnvironmentEvent` import
- Added `EnvironmentEventRequest` Pydantic model
- Added `/env/event` POST endpoint for game engine events
- Event validation and acknowledgment

**Lines changed:** ~50 lines

#### `rfsn_hybrid/environment/__init__.py`
**Changes:**
- Added imports for new event schema components
- Added imports for Unity/Skyrim adapters
- Expanded `__all__` to export new components

**Lines changed:** ~30 lines

### File Tree

```
rfsn_hybrid/
├── learning/
│   ├── __init__.py             ← Updated (PolicyBias added)
│   ├── learning_config.py      ← New
│   ├── feature_encoder.py      ← New
│   ├── bandit.py               ← New
│   ├── persistence_hooks.py    ← New
│   ├── learning_state.py       ← Existing
│   ├── outcome_evaluator.py    ← Existing
│   └── policy_adjuster.py      ← Existing
├── environment/
│   ├── __init__.py             ← Updated
│   ├── event_schema.py         ← New
│   ├── adapters/
│   │   ├── __init__.py         ← New
│   │   ├── unity_adapter.py    ← New
│   │   └── skyrim_adapter.py   ← New
│   ├── event_adapter.py        ← Existing
│   ├── signal_normalizer.py    ← Existing
│   └── consequence_mapper.py   ← Existing
├── core/state/
│   └── reducer.py              ← Updated (PolicyBias support)
└── api.py                      ← Updated (/env/event endpoint)

tests/
├── test_learning.py            ← Existing (19 tests)
└── test_learning_enhanced.py   ← New (23 tests)

demo_learning.py                ← New
LEARNING_GUIDE.md               ← New
```

## Testing

### Test Coverage

**Total: 42 tests (all passing)**
- 19 existing learning tests (`test_learning.py`)
- 23 new enhanced tests (`test_learning_enhanced.py`)

### Test Categories

1. **Configuration Tests** (4)
   - Default config disabled
   - Parameter clamping
   - Presets validation
   - Serialization

2. **Feature Encoding Tests** (5)
   - Basic encoding
   - Feature bounds
   - Context key consistency
   - Context key uniqueness
   - Serialization

3. **Bandit Tests** (6)
   - Initialization
   - Action scoring
   - Learning updates
   - Bounded updates
   - Deterministic behavior
   - Serialization

4. **Persistence Tests** (3)
   - Snapshot and restore
   - Nonexistent restore
   - Snapshot counter

5. **PolicyBias Tests** (2)
   - Neutral bias
   - Bias with values

6. **Integration Tests** (3)
   - End-to-end learning cycle
   - Disabled baseline
   - Deterministic replay

7. **Existing Tests** (19)
   - LearningState tests
   - OutcomeEvaluator tests
   - PolicyAdjuster tests

### Running Tests

```bash
# All learning tests
pytest tests/test_learning*.py -v

# Specific component
pytest tests/test_learning_enhanced.py::TestLinUCBBandit -v

# With coverage
pytest tests/test_learning*.py --cov=rfsn_hybrid.learning
```

## Integration Points

### 1. Reducer Integration

```python
# reducer.py accepts optional PolicyBias
new_state, facts, _ = reduce_state(
    state, event, facts, 
    policy_bias=policy_bias  # Optional
)
```

### 2. API Integration

```python
# New endpoint: POST /env/event
{
  "event_type": "dialogue_started",
  "npc_id": "lydia",
  "player_id": "player_1",
  "ts": 1705350000.0,
  "payload": {}
}
```

### 3. Unity Integration

```csharp
// Unity sends events via HTTP
RFSNSender sender = FindObjectOfType<RFSNSender>();
sender.SendDialogueStarted("lydia");
```

### 4. Skyrim Integration

```papyrus
; Skyrim writes events to file
String json = "{\"event_type\":\"dialogue_started\",\"npc_id\":\"lydia\"}"
MiscUtil.WriteToFile("Data/SKSE/Plugins/RFSN/events/event.json", json)
```

## Key Features

### 1. Bounded and Stable
- Maximum entries: 100 (LRU eviction)
- Weight bounds: [0.5, 2.0]
- Theta bounds: [-2.0, 2.0]
- Feature normalization: all values in [0, 1] or [-1, 1]
- Reward clamping: [-1.0, 1.0]

### 2. Deterministic
- Seeded PRNG (configurable)
- Same seed + same events = same results
- Replay-safe
- Snapshot counter for periodic saves

### 3. Safe by Default
- Learning disabled by default
- All parameters clamped to safe ranges
- Graceful fallback on errors
- No breaking changes to existing code

### 4. Explainable
- Feature names are human-readable
- Context keys show affinity/mood buckets
- PolicyBias shows explicit action biases
- Statistics available for monitoring

### 5. Portable
- Schema versioning for compatibility
- Feature schema version: 1
- Persistence version: 1
- Graceful degradation on version mismatch

## Usage Example

```python
from rfsn_hybrid.learning import (
    LearningConfig,
    LearningPresets,
    FeatureEncoder,
    LinUCBBandit,
    OutcomeEvaluator,
    PolicyBias,
)

# 1. Configure
config = LearningPresets.moderate()

# 2. Initialize components
encoder = FeatureEncoder()
bandit = LinUCBBandit(alpha=0.2, prng_seed=42)
evaluator = OutcomeEvaluator()

# 3. Encode state
features = encoder.encode(affinity=0.5, mood="Neutral")

# 4. Score actions
actions = ["friendly", "neutral", "hostile"]
scores = bandit.score_actions(features.features, actions)

# 5. Choose action
chosen = max(scores, key=scores.get)

# 6. Create PolicyBias
bias = PolicyBias(
    action_bias={chosen: scores[chosen]},
    metadata={"chosen_action": chosen}
)

# 7. Apply to reducer
new_state, facts, _ = reduce_state(state, event, facts, bias)

# 8. Evaluate outcome
outcome = evaluator.evaluate_from_affinity_change(
    affinity_delta=0.2, context=features.context_key, action=chosen
)

# 9. Update learning
bandit.update(features.features, chosen, outcome.reward)
```

## Performance

- **Memory**: Bounded to ~100 entries × ~20 features = ~2000 values
- **Computation**: O(n_actions × n_features) for scoring
- **Persistence**: Atomic writes with temp files
- **Test time**: 42 tests in ~0.07s

## Compatibility

- **Python**: 3.9+
- **Dependencies**: No new required dependencies
- **Breaking changes**: None
- **Backward compatible**: Yes (learning disabled by default)

## Next Steps

### Recommended
1. Enable learning for a subset of NPCs as A/B test
2. Monitor statistics and tune parameters
3. Collect outcome data for analysis
4. Iterate on feature engineering

### Optional Enhancements
1. Eligibility traces for delayed rewards
2. Multi-armed contextual bandits
3. Thompson Sampling alternative
4. Feature importance analysis
5. A/B testing framework

## Validation Checklist

✅ **Learning disabled by default**  
✅ **No breaking changes to existing code**  
✅ **All tests passing (42/42)**  
✅ **Deterministic replay verified**  
✅ **Bounded memory and updates**  
✅ **PolicyBias integrated with reducer**  
✅ **Environment adapters for Unity/Skyrim**  
✅ **API endpoint for event ingestion**  
✅ **Comprehensive documentation**  
✅ **Demo script functional**  

## Conclusion

Successfully implemented a **production-ready, drop-in learning module** that:
- Maintains all existing RFSN guarantees (determinism, boundedness, reducer authority)
- Adds contextual bandit learning with LinUCB
- Provides clean game engine integration (Unity, Skyrim)
- Includes comprehensive tests and documentation
- Is safe by default and easy to tune

**Total:** ~2,900 lines of new code, ~100 lines of modifications, 23 new tests, complete documentation.
