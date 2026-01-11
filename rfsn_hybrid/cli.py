from __future__ import annotations

import argparse
import os
import re
import importlib
import sys
import logging

from .engine import RFSNHybridEngine
from .types import RFSNState
from .state_machine import parse_event, transition
from .storage import ConversationMemory, FactsStore
from .dev_watch import DevWatch


def slug(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "npc"


def _package_root() -> str:
    return os.path.dirname(__file__)


def _reload_rfsn_package():
    """Hot-reload all rfsn_hybrid modules."""
    importlib.invalidate_caches()
    mods = [m for m in list(sys.modules.keys()) if m.startswith("rfsn_hybrid")]
    mods.sort(key=lambda x: x.count("."), reverse=True)
    for name in mods:
        m = sys.modules.get(name)
        if m is None:
            continue
        importlib.reload(m)


def _try_load_semantic_store(path: str):
    """Try to load semantic memory, returns None if not available."""
    try:
        from .semantic_memory import SemanticFactStore, is_semantic_available
        if is_semantic_available():
            return SemanticFactStore(path, lazy_load=True)
    except ImportError:
        pass
    return None


def _try_load_intent_classifier(llm, use_llm: bool):
    """Try to load the intent classifier."""
    try:
        from .intent_classifier import IntentClassifier
        return IntentClassifier(llm=llm, use_llm=use_llm)
    except ImportError:
        return None


def main():
    ap = argparse.ArgumentParser(
        description="RFSN Hybrid Engine - NPC dialogue with state machine + local LLM"
    )
    
    # Model configuration
    ap.add_argument("--model", required=True, help="Path to GGUF model file")
    ap.add_argument("--ctx", type=int, default=2048, help="Context window size")
    ap.add_argument("--threads", type=int, default=6, help="CPU threads")
    ap.add_argument("--gpu-layers", type=int, default=-1, help="GPU layers (-1=all)")
    
    # NPC configuration
    ap.add_argument("--npc", default="Lydia", help="NPC name")
    ap.add_argument("--role", default="Housecarl", help="NPC role")
    ap.add_argument("--player", default="Dragonborn", help="Player name")
    ap.add_argument("--playstyle", default="Combatant", 
                    help="Player style (Combatant/Thief/Mage/Explorer)")
    
    # Generation parameters
    ap.add_argument("--history", type=int, default=8, help="Conversation history turns")
    ap.add_argument("--max-tokens", type=int, default=80, help="Max response tokens")
    ap.add_argument("--temp", type=float, default=0.7, help="Sampling temperature")
    
    # v0.4 features
    ap.add_argument("--semantic", action="store_true",
                    help="Enable semantic memory (requires: pip install .[semantic])")
    ap.add_argument("--smart-classify", action="store_true",
                    help="Use LLM for intent classification (slower but more accurate)")
    ap.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = ap.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="[%(name)s] %(message)s")
    
    # Setup data directory
    root = os.path.join(os.getcwd(), ".rfsn")
    os.makedirs(root, exist_ok=True)

    npc_id = slug(args.npc)
    convo_path = os.path.join(root, f"{npc_id}_conversation.json")
    facts_path = os.path.join(root, f"{npc_id}_facts.json")
    state_path = os.path.join(root, f"{npc_id}_state.json")
    semantic_path = os.path.join(root, f"{npc_id}_semantic_facts.json")

    # Initialize stores
    memory = ConversationMemory(convo_path)
    facts = FactsStore(facts_path)
    
    # Try to initialize semantic memory
    semantic_facts = None
    if args.semantic:
        semantic_facts = _try_load_semantic_store(semantic_path)
        if semantic_facts:
            print(f"[Semantic memory enabled: {len(semantic_facts)} facts loaded]")
        else:
            print("[Warning: Semantic memory requested but dependencies not installed]")
            print("  Install with: pip install rfsn_hybrid_engine[semantic]")

    # Load existing state or create new
    state = RFSNState.load(state_path)
    if state is None:
        state = RFSNState(
            npc_name=args.npc,
            role=args.role,
            affinity=0.6,
            mood="Loyal",
            player_name=args.player,
            player_playstyle=args.playstyle,
            recent_memory="We returned from a hard road.",
        )
        state.save(state_path)
        print(f"[Created new NPC state: {args.npc}]")
    else:
        print(f"[Loaded existing state: {args.npc} (affinity: {state.affinity:.2f}, mood: {state.mood})]")

    # Initialize engine
    engine = RFSNHybridEngine(
        model_path=args.model,
        n_ctx=args.ctx,
        n_threads=args.threads,
        n_gpu_layers=args.gpu_layers,
        verbose=args.verbose,
    )
    
    # Initialize intent classifier
    classifier = None
    if args.smart_classify:
        classifier = _try_load_intent_classifier(engine.llm, use_llm=True)
        if classifier:
            print("[Smart intent classification enabled]")
        else:
            print("[Warning: Smart classification requested but failed to initialize]")

    watcher = DevWatch(roots=[_package_root(), __file__])

    print("\nCommands: quit | forget | reload | status | gift | punch | quest | steal\n")

    while True:
        # Check for code changes
        changed = watcher.check()
        if changed:
            print("[DevWatch] Code change detected:")
            for p in changed[:10]:
                print(f"  - {p}")
            if len(changed) > 10:
                print(f"  ... +{len(changed)-10} more")
            print("Type `reload` to hot-reload modules, or restart the process.")
            watcher.commit()

        try:
            user_in = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Goodbye]")
            break
            
        if not user_in:
            continue

        cmd = user_in.lower()
        
        # Handle commands
        if cmd == "quit":
            break
            
        if cmd == "status":
            print(f"\n[NPC Status]")
            print(f"  Name: {state.npc_name} ({state.role})")
            print(f"  Affinity: {state.affinity:.2f} ({state.attitude()})")
            print(f"  Mood: {state.mood}")
            print(f"  Facts: {len(facts.facts)} stored")
            if semantic_facts:
                print(f"  Semantic facts: {len(semantic_facts)} stored")
            if classifier:
                stats = classifier.stats
                print(f"  Intent classification: LLM success rate {stats['llm_rate']:.1%}")
            print()
            continue
            
        if cmd == "forget":
            # Remove all stored data
            for path in [convo_path, facts_path, state_path, semantic_path]:
                if os.path.exists(path):
                    os.remove(path)
            memory.turns = []
            facts.wipe()
            if semantic_facts:
                semantic_facts.wipe()
            
            # Reset to default state
            state = RFSNState(
                npc_name=args.npc,
                role=args.role,
                affinity=0.6,
                mood="Loyal",
                player_name=args.player,
                player_playstyle=args.playstyle,
                recent_memory="We returned from a hard road.",
            )
            state.save(state_path)
            print("[Wiped conversation + facts + state]")
            continue

        if cmd == "reload":
            try:
                _reload_rfsn_package()
                from rfsn_hybrid.engine import RFSNHybridEngine as Engine2
                engine = Engine2(
                    model_path=args.model,
                    n_ctx=args.ctx,
                    n_threads=args.threads,
                    n_gpu_layers=args.gpu_layers,
                    verbose=args.verbose,
                )
                print("[DevWatch] Reloaded modules and recreated engine.")
            except Exception as e:
                print(f"[DevWatch] Reload failed: {e}")
                print("Restart recommended.")
            continue

        # Parse event (using classifier if available)
        if classifier:
            event = classifier.classify(user_in)
        else:
            event = parse_event(user_in)
        
        # Apply state transition
        state, new_facts = transition(state, event)

        # Store new facts
        tags = (event.tags or []) + [event.type.lower()]
        salience = min(1.0, max(0.4, event.strength / 2.0))
        
        for f in new_facts:
            facts.add_fact(text=f, tags=tags, salience=salience)
            # Also add to semantic store if available
            if semantic_facts:
                try:
                    semantic_facts.add_fact(text=f, tags=tags, salience=salience)
                except Exception as e:
                    logging.warning(f"Failed to add semantic fact: {e}")

        # Generate response
        res = engine.generate(
            user_text=user_in,
            state=state,
            memory=memory,
            facts=facts,
            semantic_facts=semantic_facts,
            fact_tags=event.tags or [],
            history_limit_turns=args.history,
            max_tokens=args.max_tokens,
            temperature=args.temp,
        )
        
        # Save state after each interaction
        state.save(state_path)
        
        # Display response
        retrieval_type = "semantic" if res.get("semantic_retrieval") else "tag-based"
        print(f"{state.npc_name}: {res['text']}  ({res['latency_ms']:.0f}ms, {retrieval_type})\n")


if __name__ == "__main__":
    main()

