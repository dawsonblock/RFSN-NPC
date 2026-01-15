# Unity Integration Guide for RFSN-NPC

This guide explains how to integrate RFSN-NPC with Unity to create dynamic, learning NPCs.

## Quick Start

### 1. Setup RFSN Server

Start the RFSN API server:

```bash
cd RFSN-NPC
uvicorn rfsn_hybrid.api:app --host 0.0.0.0 --port 8000
```

### 2. Add Scripts to Unity Project

1. Copy `RfsnEventPublisher.cs` and `RfsnNpcDriver.cs` to your Unity project's `Assets/Scripts/` folder
2. Create namespace folder: `Assets/Scripts/RFSN/` (recommended)

### 3. Setup Scene

1. Create an empty GameObject named "RFSNEventPublisher"
2. Attach the `RfsnEventPublisher` component
3. Configure API URL (default: `http://localhost:8000`)

### 4. Setup NPCs

For each NPC:
1. Attach `RfsnNpcDriver` component
2. Set `npcId` to match NPC name (e.g., "lydia", "guard_1")
3. Add a Collider component with "Is Trigger" checked
4. Configure detection radius

### 5. Test

1. Enter Play mode
2. Move player near NPC
3. Check Unity Console for `[RFSN]` log messages
4. Check RFSN server logs for received events

## Component Reference

### RfsnEventPublisher

Manages HTTP communication with RFSN API.

**Properties:**
- `apiUrl` (string): RFSN server URL
- `batchSize` (int): Events to batch before sending
- `throttleSeconds` (float): Min time between API calls
- `debugLogging` (bool): Enable console logging

**Methods:**
```csharp
// Publish generic event
PublishEvent(string eventType, string npcId, float magnitude, 
             Dictionary<string, object> payload, bool priority)

// Helper methods
PublishCombatStart(string npcId, string enemyName)
PublishCombatEnd(string npcId, bool victory)
PublishItemReceived(string npcId, string itemName, int itemValue)
PublishQuestCompleted(string npcId, string questName)
PublishPlayerNearby(string npcId)
PublishPlayerLeft(string npcId)
```

### RfsnNpcDriver

Example driver showing common event triggers.

**Properties:**
- `npcId` (string): Unique NPC identifier
- `playerTag` (string): Tag to identify player
- `detectionRadius` (float): Player detection distance
- `combatStartHealthThreshold` (float): HP% to trigger combat

**Methods:**
```csharp
// Call from your game systems
TakeDamage(float damage, GameObject attacker)
EndCombat(bool victory)
ReceiveItem(string itemName, int itemValue)
CompleteQuest(string questName)
PublishCustomEvent(string eventType, float magnitude, Dictionary<string, object> data)
```

## Integration Examples

### Example 1: Player Proximity Detection

Automatically detects when player enters/exits NPC radius using triggers:

```csharp
// RfsnNpcDriver does this automatically via OnTriggerEnter/Exit
// Just ensure:
// 1. NPC has Collider with "Is Trigger" = true
// 2. Player has Rigidbody
// 3. Player is tagged "Player"
```

### Example 2: Combat Integration

Hook into your health system:

```csharp
public class NPCHealth : MonoBehaviour
{
    private RfsnNpcDriver rfsnDriver;
    
    void Start()
    {
        rfsnDriver = GetComponent<RfsnNpcDriver>();
    }
    
    public void TakeDamage(float damage, GameObject attacker)
    {
        currentHealth -= damage;
        
        // Notify RFSN
        rfsnDriver.TakeDamage(damage, attacker);
        
        if (currentHealth <= 0)
        {
            rfsnDriver.EndCombat(false); // NPC defeated
        }
    }
}
```

### Example 3: Gift/Item System

```csharp
public class GiftSystem : MonoBehaviour
{
    public void GiveItemToNPC(GameObject npc, Item item)
    {
        var rfsnDriver = npc.GetComponent<RfsnNpcDriver>();
        if (rfsnDriver != null)
        {
            rfsnDriver.ReceiveItem(item.name, item.value);
        }
        
        // Your item transfer logic...
    }
}
```

### Example 4: Quest System

```csharp
public class QuestManager : MonoBehaviour
{
    public void CompleteQuest(Quest quest)
    {
        // Find NPCs involved in quest
        foreach (var npcId in quest.involvedNPCs)
        {
            var npc = FindNPCById(npcId);
            var rfsnDriver = npc.GetComponent<RfsnNpcDriver>();
            
            if (rfsnDriver != null)
            {
                rfsnDriver.CompleteQuest(quest.name);
            }
        }
        
        // Your quest completion logic...
    }
}
```

### Example 5: Custom Event

```csharp
public class CustomEventExample : MonoBehaviour
{
    private RfsnNpcDriver rfsnDriver;
    
    void Start()
    {
        rfsnDriver = GetComponent<RfsnNpcDriver>();
    }
    
    public void OnPlayerTradeAttempt(int offeredGold)
    {
        var data = new Dictionary<string, object>
        {
            { "gold_offered", offeredGold },
            { "trade_type", "barter" }
        };
        
        // Higher magnitude for larger trades
        float magnitude = Mathf.Clamp01(offeredGold / 1000.0f);
        
        rfsnDriver.PublishCustomEvent("trade_attempt", magnitude, data);
    }
}
```

## Event Types

Common event types recognized by RFSN:

| Event Type | When to Use | Magnitude Guide |
|------------|-------------|-----------------|
| `player_nearby` | Player enters detection range | 0.3 |
| `player_left` | Player exits detection range | 0.2 |
| `combat_start` | Combat begins | 0.7 |
| `combat_end` | Combat ends | 0.5 (loss) - 0.8 (win) |
| `combat_hit_taken` | NPC takes damage | 0.1-1.0 (scaled by damage) |
| `item_received` | Item given to NPC | 0.1-1.0 (scaled by value) |
| `item_stolen` | Item stolen from NPC | 0.3-1.0 (scaled by value) |
| `quest_started` | Quest begins | 0.6 |
| `quest_completed` | Quest finishes | 0.9 |
| `dialogue_start` | Dialogue begins | 0.4 |
| `dialogue_end` | Dialogue ends | 0.3 |

## Performance Optimization

### Batching

Events are automatically batched to reduce HTTP overhead:
- Adjust `batchSize` (default: 5)
- Adjust `throttleSeconds` (default: 1.0)

### Priority Events

Important events bypass batching:
```csharp
// Send immediately
publisher.PublishEvent("combat_start", "npc1", 0.7f, null, priority: true);
```

### Event Queue Management

- Queue size is unbounded (consider adding max if needed)
- Failed requests log errors but don't retry
- No persistence between play sessions

## Troubleshooting

**Problem:** Events not reaching RFSN
- Check RFSN server is running
- Verify `apiUrl` in RfsnEventPublisher
- Check Unity Console for HTTP errors

**Problem:** NPC ID mismatch
- Ensure `npcId` in Unity matches RFSN API
- Check `/npc/{npc_id}/history` endpoint
- IDs are case-sensitive

**Problem:** Trigger not detecting player
- Verify player has Rigidbody component
- Ensure NPC collider "Is Trigger" is checked
- Check player is tagged correctly

**Problem:** Performance issues
- Increase `throttleSeconds` (reduce frequency)
- Increase `batchSize` (batch more events)
- Disable `debugLogging` in production

## Advanced Usage

### Multiple Event Publishers

You can have multiple publishers for different NPC groups:

```csharp
// One publisher per region
RfsnEventPublisher publisherTown = townManager.GetComponent<RfsnEventPublisher>();
RfsnEventPublisher publisherDungeon = dungeonManager.GetComponent<RfsnEventPublisher>();
```

### Custom Event Publisher

Extend RfsnEventPublisher for game-specific needs:

```csharp
public class CustomRfsnPublisher : RfsnEventPublisher
{
    public void PublishMagicCast(string npcId, string spellName, int spellPower)
    {
        var payload = new Dictionary<string, object>
        {
            { "spell", spellName },
            { "power", spellPower }
        };
        
        PublishEvent("spell_cast_on_npc", npcId, 0.6f, payload, priority: true);
    }
}
```

### Coroutine Management

The publisher uses Unity coroutines for async HTTP. Be aware:
- Coroutines stop when GameObject is disabled
- Use `DontDestroyOnLoad()` for persistent publisher

## Testing Without RFSN Server

For development, you can mock the API:

```csharp
// In RfsnEventPublisher.cs, modify SendEvent():
private IEnumerator SendEvent(RfsnEvent rfsnEvent)
{
    // Mock mode for testing
    if (apiUrl.Contains("mock"))
    {
        Debug.Log($"[RFSN Mock] Event: {rfsnEvent.event_type}");
        yield break;
    }
    
    // ... actual HTTP code ...
}
```

## Next Steps

1. Implement event hooks in your game systems
2. Test with a single NPC
3. Monitor RFSN API logs
4. Enable learning mode (see LEARNING_GUIDE.md)
5. Scale to multiple NPCs
6. Fine-tune event magnitudes

## Resources

- RFSN API Documentation: See main repository
- Event Schema: `rfsn_hybrid/environment/event_adapter.py`
- Unity Networking: https://docs.unity3d.com/ScriptReference/Networking.UnityWebRequest.html
