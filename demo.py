#!/usr/bin/env python3
"""
RFSN Hybrid Engine v0.4 Demo Script

This script demonstrates the new v0.4 features:
1. Semantic Memory - FAISS-based vector search for facts
2. State Machine - Affinity and mood transitions
3. Persistence - State survives restarts

Run with:
    python demo.py

No GGUF model required - uses mock responses for demonstration.
"""
import os
import tempfile
import time
from typing import List, Tuple

# Check for semantic dependencies
try:
    from rfsn_hybrid.semantic_memory import SemanticFactStore, is_semantic_available
    SEMANTIC_OK = is_semantic_available()
except ImportError:
    SEMANTIC_OK = False

from rfsn_hybrid.types import RFSNState
from rfsn_hybrid.state_machine import parse_event, transition
from rfsn_hybrid.storage import ConversationMemory, FactsStore


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_state(state: RFSNState):
    """Pretty-print NPC state."""
    print(f"  📊 Affinity: {state.affinity:+.2f} ({state.attitude()})")
    print(f"  😊 Mood: {state.mood}")
    print(f"  💭 Recent Memory: {state.recent_memory or 'None'}")


def demo_state_machine():
    """Demonstrate the state machine transitions."""
    print_header("Demo 1: State Machine Transitions")
    
    state = RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=0.0,
        mood="Neutral",
        player_name="Dragonborn",
        player_playstyle="Combatant",
    )
    
    print(f"🎭 NPC: {state.npc_name} the {state.role}")
    print_state(state)
    
    events = [
        ("gift", "Player gives Lydia a sword"),
        ("gift", "Player gives Lydia armor"),
        ("Thank you for everything", "Player thanks Lydia"),
        ("You're pathetic", "Player insults Lydia"),
        ("punch", "Player attacks Lydia"),
    ]
    
    for user_input, description in events:
        print(f"\n▶ Action: {description}")
        print(f"  Input: \"{user_input}\"")
        
        event = parse_event(user_input)
        state, new_facts = transition(state, event)
        
        print(f"  Event: {event.type} (strength: {event.strength:.1f})")
        print_state(state)
        if new_facts:
            print(f"  📝 New Fact: {new_facts[0]}")
        
        time.sleep(0.5)


def demo_semantic_memory():
    """Demonstrate semantic memory with FAISS."""
    print_header("Demo 2: Semantic Memory (FAISS)")
    
    if not SEMANTIC_OK:
        print("❌ Semantic dependencies not installed.")
        print("   Install with: pip install rfsn_hybrid_engine[semantic]")
        return
    
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "semantic_facts.json")
        store = SemanticFactStore(path)
        
        # Add facts about adventures
        facts_to_add = [
            ("Player saved the village from a dragon attack", ["quest", "heroic"], 0.9),
            ("Player gave Lydia an enchanted sword", ["gift"], 0.8),
            ("Player helped the blacksmith repair his forge", ["assist"], 0.6),
            ("Player stole gold from the merchant", ["theft"], 0.4),
            ("Player defeated the bandit leader at Bleak Falls", ["quest", "combat"], 0.85),
            ("Lydia was injured protecting the player", ["loyal"], 0.7),
        ]
        
        print("📚 Adding facts to semantic store...")
        for text, tags, salience in facts_to_add:
            store.add_fact(text, tags, salience)
            print(f"   + {text[:50]}...")
        
        print(f"\n✅ Added {len(store)} facts with embeddings\n")
        
        # Demonstrate semantic search
        queries = [
            "What heroic deeds have been done?",
            "Has anyone given me weapons?",
            "What bad things happened?",
        ]
        
        for query in queries:
            print(f"🔍 Query: \"{query}\"")
            results = store.search(query, k=2)
            for text, score in results:
                print(f"   [{score:.3f}] {text}")
            print()
            time.sleep(0.3)
        
        # Demonstrate hybrid search
        print("🔀 Hybrid Search: \"village\" + quest tag")
        hybrid = store.hybrid_search("village", want_tags=["quest"], k=2)
        for text in hybrid:
            print(f"   • {text}")


def demo_persistence():
    """Demonstrate state persistence."""
    print_header("Demo 3: State Persistence")
    
    with tempfile.TemporaryDirectory() as d:
        state_path = os.path.join(d, "lydia_state.json")
        
        # Create initial state
        print("1️⃣ Creating initial state...")
        state1 = RFSNState(
            npc_name="Lydia",
            role="Housecarl",
            affinity=0.75,
            mood="Happy",
            player_name="Hero",
            player_playstyle="Mage",
            recent_memory="We defeated the dragon together",
        )
        state1.save(state_path)
        print_state(state1)
        
        # Simulate restart
        print("\n2️⃣ Simulating CLI restart...")
        time.sleep(0.5)
        
        # Load persisted state
        print("3️⃣ Loading persisted state...")
        state2 = RFSNState.load(state_path)
        
        if state2:
            print_state(state2)
            print(f"\n✅ State successfully restored!")
            print(f"   Affinity: {state1.affinity} → {state2.affinity}")
            print(f"   Mood: {state1.mood} → {state2.mood}")
        else:
            print("❌ Failed to load state")


def demo_intent_classification():
    """Demonstrate intent classification."""
    print_header("Demo 4: Intent Classification")
    
    test_inputs = [
        "Here, take this gold",
        "Thank you for your loyalty",
        "You worthless fool",
        "I will end you if you betray me",
        "Can you help me carry this?",
        "I stole from the temple",
        "The weather is nice today",
    ]
    
    print("🎯 Classifying player intents:\n")
    
    for text in test_inputs:
        event = parse_event(text)
        emoji = {
            "GIFT": "🎁",
            "PRAISE": "👏",
            "INSULT": "😤",
            "THREATEN": "⚔️",
            "HELP": "🤝",
            "THEFT": "💰",
            "TALK": "💬",
            "PUNCH": "👊",
        }.get(event.type, "❓")
        
        print(f"   {emoji} {event.type:10} ← \"{text}\"")
        time.sleep(0.2)


def main():
    """Run all demos."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                 RFSN Hybrid Engine v0.4 Demo                   ║
║         Semantic Memory • State Machine • Persistence          ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    demo_state_machine()
    demo_semantic_memory()
    demo_persistence()
    demo_intent_classification()
    
    print_header("Demo Complete!")
    print("To run the full CLI with a model:")
    print("  python -m rfsn_hybrid.cli --model /path/to/model.gguf")
    print("\nWith all v0.4 features:")
    print("  python -m rfsn_hybrid.cli --model /path/to/model.gguf --semantic --smart-classify")
    print()


if __name__ == "__main__":
    main()
