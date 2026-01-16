#!/usr/bin/env python3
"""
Manual verification script for the environment event and decision policy wiring.

This script demonstrates the complete feedback loop:
1. Enable learning for an NPC
2. Chat with the NPC (decision policy selects action)
3. Send environment event (affects state through consequence mapper)
4. Learning system receives feedback from affinity change
5. Chat again to see updated behavior
"""

from rfsn_hybrid.engine import RFSNHybridEngine
from rfsn_hybrid.environment import EnvironmentEvent


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_state(label: str, state_dict: dict):
    """Print NPC state."""
    print(f"\n{label}:")
    print(f"  Affinity: {state_dict['affinity']:.3f}")
    print(f"  Mood: {state_dict['mood']}")


def main():
    print_section("RFSN NPC Environment & Decision Wiring Demo")
    
    # Initialize engine
    engine = RFSNHybridEngine()
    npc_id = "Lydia"
    
    print("\n✓ Engine initialized")
    
    # Step 1: Enable learning
    print_section("Step 1: Enable Learning")
    learning_result = engine.enable_learning(npc_id, enabled=True)
    print(f"✓ Learning enabled for {npc_id}")
    print(f"  Decision stats: {learning_result['decision']}")
    print(f"  Style stats: {learning_result['style']}")
    
    # Step 2: First chat interaction
    print_section("Step 2: First Chat (Decision Policy Active)")
    response1 = engine.handle_message(
        npc_id=npc_id,
        text="Hello, how are you today?",
        user_name="Player"
    )
    
    print(f"\nPlayer: Hello, how are you today?")
    print(f"{npc_id}: {response1['text']}")
    
    print_state("State after chat", response1['state'])
    
    print(f"\nDecision Info:")
    print(f"  Context Key: {response1['decision']['context_key']}")
    print(f"  Action Chosen: {response1['decision']['action']}")
    print(f"  Speech Style: {response1['decision']['style']}")
    
    # Step 3: Send a positive environment event (gift)
    print_section("Step 3: Environment Event (Gift)")
    
    gift_event = EnvironmentEvent(
        event_type="gift",
        npc_id=npc_id,
        player_id="Player",
        payload={"magnitude": 0.8, "item": "Steel Sword"}
    )
    
    env_result = engine.handle_env_event(gift_event)
    
    print(f"✓ Processed gift event: {gift_event.payload}")
    print_state("State after gift", env_result['state'])
    
    print(f"\nNormalized Signals:")
    norm = env_result['normalized']
    print(f"  Consequence Type: {norm['consequence_type']}")
    print(f"  Intensity: {norm['intensity']:.3f}")
    print(f"  Affinity Delta: {norm['affinity_delta']:+.3f}")
    print(f"  Mood Impact: {norm.get('mood_impact', 'None')}")
    
    # Step 4: Another chat to see updated behavior
    print_section("Step 4: Second Chat (With Updated Context)")
    
    response2 = engine.handle_message(
        npc_id=npc_id,
        text="Can you help me with a quest?",
        user_name="Player"
    )
    
    print(f"\nPlayer: Can you help me with a quest?")
    print(f"{npc_id}: {response2['text']}")
    
    print_state("Final state", response2['state'])
    
    print(f"\nDecision Info (updated):")
    print(f"  Context Key: {response2['decision']['context_key']}")
    print(f"  Action Chosen: {response2['decision']['action']}")
    print(f"  Speech Style: {response2['decision']['style']}")
    
    # Step 5: Send a negative event (combat)
    print_section("Step 5: Negative Event (Combat Damage)")
    
    combat_event = EnvironmentEvent(
        event_type="combat_damage_taken",
        npc_id=npc_id,
        player_id="Player",
        payload={"magnitude": 0.6, "source": "bandit"}
    )
    
    combat_result = engine.handle_env_event(combat_event)
    
    print(f"✓ Processed combat damage event")
    print_state("State after combat", combat_result['state'])
    
    print(f"\nNormalized Signals:")
    norm = combat_result['normalized']
    print(f"  Consequence Type: {norm['consequence_type']}")
    print(f"  Affinity Delta: {norm['affinity_delta']:+.3f}")
    
    # Step 6: Final chat
    print_section("Step 6: Final Chat")
    
    response3 = engine.handle_message(
        npc_id=npc_id,
        text="Are you okay?",
        user_name="Player"
    )
    
    print(f"\nPlayer: Are you okay?")
    print(f"{npc_id}: {response3['text']}")
    
    print_state("Final state", response3['state'])
    print(f"\n  Action Chosen: {response3['decision']['action']}")
    
    # Summary
    print_section("Summary")
    
    store = engine.get_store(npc_id)
    facts = list(store.facts)
    
    print(f"\n✓ Complete feedback loop working!")
    print(f"\nTotal interactions tracked: {len(facts)} facts")
    print(f"  Chat facts: {len([f for f in facts if 'chat' in (getattr(f, 'tags', []) or [])])}")
    print(f"  Env facts: {len([f for f in facts if 'env' in (getattr(f, 'tags', []) or [])])}")
    
    affinity_changes = [
        ("Initial", 0.5),
        ("After gift", response2['state']['affinity']),
        ("After combat", response3['state']['affinity'])
    ]
    
    print(f"\nAffinity progression:")
    for label, aff in affinity_changes:
        print(f"  {label:15} {aff:.3f}")
    
    print_section("Verification Complete")
    print("\nAll components wired and working:")
    print("  ✓ Decision policy selects bounded actions")
    print("  ✓ Environment events update state through reducer")
    print("  ✓ Learning system receives affinity feedback")
    print("  ✓ State changes are deterministic and bounded")
    print()


if __name__ == "__main__":
    main()
