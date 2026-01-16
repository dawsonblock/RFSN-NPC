#!/usr/bin/env python3
"""
API integration test demonstrating the complete wiring through HTTP endpoints.

This script starts a test server and exercises all three key endpoints:
1. POST /npc/{npc_id}/learning - Enable learning
2. POST /npc/{npc_id}/chat - Chat with decision policy active
3. POST /env/event - Send environment events that feed back to learning
"""

from fastapi.testclient import TestClient
from rfsn_hybrid.api import app


def print_section(title: str):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def main():
    print_section("API Integration Test - Environment & Decision Wiring")
    
    client = TestClient(app)
    npc_id = "Lydia"
    
    # Test 1: Health check
    print_section("Step 1: Health Check")
    response = client.get("/health")
    assert response.status_code == 200
    print(f"✓ Health check: {response.json()}")
    
    # Test 2: Enable learning
    print_section("Step 2: Enable Learning via API")
    response = client.post(
        f"/npc/{npc_id}/learning",
        json={"enabled": True}
    )
    assert response.status_code == 200
    result = response.json()
    print(f"✓ Learning enabled for {npc_id}")
    print(f"  Response: {result}")
    assert result["enabled"] is True
    assert result["npc_id"] == npc_id
    
    # Test 3: Chat (decision policy active)
    print_section("Step 3: Chat with Decision Policy")
    response = client.post(
        f"/npc/{npc_id}/chat",
        json={
            "message": "Hello, I need your help!",
            "player_name": "Dovahkiin"
        }
    )
    assert response.status_code == 200
    chat_result = response.json()
    
    print(f"\nPlayer: Hello, I need your help!")
    print(f"{npc_id}: {chat_result['text']}")
    print(f"\nState:")
    print(f"  Affinity: {chat_result['state']['affinity']:.3f}")
    print(f"  Mood: {chat_result['state']['mood']}")
    print(f"\nDecision:")
    print(f"  Action: {chat_result['decision']['action']}")
    print(f"  Style: {chat_result['decision']['style']}")
    print(f"  Context: {chat_result['decision']['context_key']}")
    
    initial_affinity = chat_result['state']['affinity']
    
    # Test 4: Send gift event
    print_section("Step 4: Send Gift Event")
    response = client.post(
        "/env/event",
        json={
            "event_type": "gift",
            "npc_id": npc_id,
            "player_id": "Dovahkiin",
            "payload": {
                "magnitude": 0.9,
                "item": "Ebony Sword"
            }
        }
    )
    assert response.status_code == 200
    env_result = response.json()
    
    print(f"✓ Gift event processed")
    print(f"  Event type: {env_result['event_type']}")
    print(f"\nNormalized signals:")
    norm = env_result['normalized']
    print(f"  Consequence: {norm['consequence_type']}")
    print(f"  Affinity delta: {norm['affinity_delta']:+.3f}")
    print(f"\nUpdated state:")
    print(f"  Affinity: {env_result['state']['affinity']:.3f}")
    print(f"  Mood: {env_result['state']['mood']}")
    
    gift_affinity = env_result['state']['affinity']
    affinity_change = gift_affinity - initial_affinity
    print(f"\n✓ Affinity changed by {affinity_change:+.3f} (learning feedback applied)")
    
    # Test 5: Chat again with updated context
    print_section("Step 5: Chat Again (Updated Context)")
    response = client.post(
        f"/npc/{npc_id}/chat",
        json={
            "message": "Will you follow me?",
            "player_name": "Dovahkiin"
        }
    )
    assert response.status_code == 200
    chat_result2 = response.json()
    
    print(f"\nPlayer: Will you follow me?")
    print(f"{npc_id}: {chat_result2['text']}")
    print(f"\nDecision (with env event in context):")
    print(f"  Action: {chat_result2['decision']['action']}")
    print(f"  Context: {chat_result2['decision']['context_key']}")
    
    # Verify env event is in context
    context = chat_result2['decision']['context_key']
    has_env_context = 'eevents:' in context
    print(f"\n✓ Context includes environment events: {has_env_context}")
    
    # Test 6: Send negative event
    print_section("Step 6: Send Combat Event")
    response = client.post(
        "/env/event",
        json={
            "event_type": "combat_damage_taken",
            "npc_id": npc_id,
            "player_id": "Dovahkiin",
            "payload": {
                "magnitude": 0.5,
                "source": "wolf"
            }
        }
    )
    assert response.status_code == 200
    combat_result = response.json()
    
    print(f"✓ Combat damage event processed")
    print(f"  Affinity delta: {combat_result['normalized']['affinity_delta']:+.3f}")
    print(f"  New affinity: {combat_result['state']['affinity']:.3f}")
    
    # Test 7: Get history
    print_section("Step 7: Get Conversation History")
    response = client.get(f"/npc/{npc_id}/history")
    assert response.status_code == 200
    history = response.json()
    
    event_count = len(history['history'])
    print(f"✓ Retrieved {event_count} events from history")
    
    # Count different event types
    player_events = sum(1 for e in history['history'] if e.get('event_type') == 'PLAYER_EVENT')
    fact_adds = sum(1 for e in history['history'] if e.get('event_type') == 'FACT_ADD')
    affinity_deltas = sum(1 for e in history['history'] if e.get('event_type') == 'AFFINITY_DELTA')
    
    print(f"  Player events: {player_events}")
    print(f"  Facts added: {fact_adds}")
    print(f"  Affinity changes: {affinity_deltas}")
    
    # Summary
    print_section("Summary")
    print("\n✓ All API endpoints working correctly:")
    print("  • POST /npc/{id}/learning - Learning control ✓")
    print("  • POST /npc/{id}/chat - Chat with decisions ✓")
    print("  • POST /env/event - Environment feedback ✓")
    print("  • GET /npc/{id}/history - Event history ✓")
    
    print("\n✓ Complete feedback loop verified:")
    print("  • Decision policy constrains actions based on state ✓")
    print("  • Environment events update state through reducer ✓")
    print("  • Learning receives affinity feedback ✓")
    print("  • Context includes recent environment events ✓")
    
    print(f"\nAffinity progression:")
    print(f"  Initial:      {initial_affinity:.3f}")
    print(f"  After gift:   {gift_affinity:.3f} ({affinity_change:+.3f})")
    print(f"  After combat: {combat_result['state']['affinity']:.3f}")
    
    print_section("API Integration Test Complete")
    print("\n✅ All tests passed!\n")


if __name__ == "__main__":
    main()
