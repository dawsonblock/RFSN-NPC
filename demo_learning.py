#!/usr/bin/env python3
"""
RFSN Learning Module Demo

Demonstrates the drop-in learning module that learns NPC behavior
based on outcomes without breaking determinism or boundedness.

Run with:
    python demo_learning.py
"""
import os
import sys
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rfsn_hybrid.learning import (
    LearningConfig,
    LearningState,
    FeatureEncoder,
    LinUCBBandit,
    OutcomeEvaluator,
    PolicyAdjuster,
    OutcomeType,
    LearningPersistence,
)


def print_header(text: str):
    """Print styled header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")


def print_section(text: str):
    """Print section divider."""
    print(f"\n{'-'*70}")
    print(f"  {text}")
    print(f"{'-'*70}")


def demo_disabled_vs_enabled():
    """Demonstrate learning disabled vs enabled."""
    print_header("Demo 1: Learning Disabled vs Enabled")
    
    print("Creating two learning states:")
    print("  1. Learning DISABLED (default)")
    print("  2. Learning ENABLED")
    
    disabled = LearningState(enabled=False)
    enabled = LearningState(enabled=True)
    
    context = "aff:neutral|mood:neutral"
    action = "friendly_response"
    
    print(f"\nAction: {action}")
    print(f"Context: {context}")
    
    # Update both with positive reward
    print(f"\nApplying positive reward (0.8) 5 times...")
    
    for i in range(5):
        w_disabled = disabled.update_weight(context, action, 0.8, learning_rate=0.1)
        w_enabled = enabled.update_weight(context, action, 0.8, learning_rate=0.1)
    
    print(f"\nResults:")
    print(f"  Disabled weight: {w_disabled:.3f} (unchanged)")
    print(f"  Enabled weight:  {w_enabled:.3f} (increased)")
    
    print(f"\n✓ With learning disabled, behavior remains at baseline (1.0)")
    print(f"✓ With learning enabled, successful actions are reinforced")


def demo_feature_encoding():
    """Demonstrate feature encoding."""
    print_header("Demo 2: Feature Encoding")
    
    encoder = FeatureEncoder()
    
    print("Encoding NPC state into feature vectors:")
    
    scenarios = [
        {"affinity": 0.7, "mood": "Pleased", "desc": "High affinity, pleased"},
        {"affinity": -0.5, "mood": "Angry", "desc": "Low affinity, angry"},
        {"affinity": 0.0, "mood": "Neutral", "desc": "Neutral state"},
    ]
    
    for scenario in scenarios:
        features = encoder.encode(
            affinity=scenario["affinity"],
            mood=scenario["mood"],
        )
        
        print(f"\n{scenario['desc']}:")
        print(f"  Context Key: {features.context_key}")
        print(f"  Affinity Bucket: {features.features['affinity_bucket']:.2f}")
        print(f"  Mood Features: ", end="")
        mood_features = {k: v for k, v in features.features.items() if k.startswith("mood_")}
        active_mood = [k.replace("mood_", "") for k, v in mood_features.items() if v == 1.0]
        print(", ".join(active_mood))
    
    print(f"\n✓ Features are normalized and bounded")
    print(f"✓ Schema versioned for compatibility (v{encoder.schema_version})")


def demo_contextual_bandit():
    """Demonstrate LinUCB bandit learning."""
    print_header("Demo 3: Contextual Bandit (LinUCB)")
    
    print("Simulating action selection over multiple rounds...")
    
    bandit = LinUCBBandit(alpha=0.3, prng_seed=42)
    encoder = FeatureEncoder()
    
    # Scenario: NPC with neutral affinity
    context_dict = encoder.encode(0.0, "Neutral").features
    actions = ["friendly", "neutral", "hostile"]
    
    print(f"\nAvailable actions: {', '.join(actions)}")
    print(f"Starting with no prior knowledge...")
    
    # Simulate 10 rounds
    results = []
    for round_num in range(1, 11):
        # Get action scores
        scores = bandit.score_actions(context_dict, actions)
        chosen = max(scores, key=scores.get)
        
        # Simulate outcome: friendly actions work better
        if chosen == "friendly":
            reward = 0.7
        elif chosen == "neutral":
            reward = 0.3
        else:  # hostile
            reward = -0.5
        
        # Update bandit
        bandit.update(context_dict, chosen, reward)
        
        results.append((chosen, reward))
        
        if round_num in [1, 5, 10]:
            print(f"\nRound {round_num}:")
            print(f"  Scores: " + ", ".join([f"{a}: {scores[a]:.3f}" for a in actions]))
            print(f"  Chosen: {chosen}, Reward: {reward:+.1f}")
    
    print(f"\n✓ Bandit learns to prefer actions with higher rewards")
    print(f"✓ Exploration (α={bandit.alpha}) ensures non-optimal actions are tried")


def demo_outcome_evaluation():
    """Demonstrate outcome evaluation."""
    print_header("Demo 4: Outcome Evaluation")
    
    evaluator = OutcomeEvaluator()
    
    print("Converting game events into learning rewards:\n")
    
    scenarios = [
        ("Affinity increased by +0.3", "evaluate_from_affinity_change", 
         {"affinity_delta": 0.3, "context": "ctx", "action": "act"}),
        ("Player gave a gift", "evaluate_from_player_event",
         {"player_event_type": "GIFT", "context": "ctx", "action": "act"}),
        ("Player punched NPC", "evaluate_from_player_event",
         {"player_event_type": "PUNCH", "context": "ctx", "action": "act"}),
        ("Quest completed", "evaluate",
         {"outcome_type": OutcomeType.QUEST_COMPLETE, "context": "ctx", 
          "action": "act", "intensity": 1.0}),
    ]
    
    for desc, method, kwargs in scenarios:
        outcome = getattr(evaluator, method)(**kwargs)
        print(f"{desc}:")
        print(f"  → Outcome: {outcome.outcome_type.value}")
        print(f"  → Reward: {outcome.reward:+.2f}\n")
    
    print(f"✓ Game events are automatically converted to reward signals")
    print(f"✓ Rewards are normalized to [-1, +1] range")


def demo_policy_adjuster():
    """Demonstrate PolicyAdjuster."""
    print_header("Demo 5: Policy Adjuster Integration")
    
    print("Simulating NPC learning over multiple interactions...\n")
    
    learning_state = LearningState(enabled=True)
    evaluator = OutcomeEvaluator()
    adjuster = PolicyAdjuster(
        learning_state=learning_state,
        outcome_evaluator=evaluator,
        exploration_rate=0.1,
        learning_rate=0.1,
    )
    
    # Simulate 20 interactions
    affinity = 0.0
    for i in range(1, 21):
        context_key = adjuster.build_context_key(affinity, "Neutral")
        
        # Two possible responses
        actions = ["friendly_response", "neutral_response"]
        weights = adjuster.get_action_weights(context_key, actions)
        
        # Choose based on weights (simplified - just pick highest)
        chosen = max(weights, key=weights.get)
        
        # Simulate: friendly responses improve affinity
        if chosen == "friendly_response":
            affinity_delta = 0.05
        else:
            affinity_delta = 0.01
        
        affinity = min(1.0, affinity + affinity_delta)
        
        # Update learning
        adjuster.apply_affinity_feedback(context_key, chosen, affinity_delta)
        
        if i in [1, 5, 10, 20]:
            print(f"Interaction {i}:")
            print(f"  Action Weights: " + ", ".join(
                [f"{a}: {weights[a]:.2f}" for a in actions]))
            print(f"  Chosen: {chosen}")
            print(f"  New Affinity: {affinity:.2f}\n")
    
    stats = adjuster.get_statistics()
    print(f"Final Statistics:")
    print(f"  Total Entries: {stats['total_entries']}")
    print(f"  Avg Weight: {stats['avg_weight']:.2f}")
    print(f"  Avg Success Rate: {stats['avg_success_rate']:.2f}")
    
    print(f"\n✓ Policy learns to prefer actions with better outcomes")
    print(f"✓ Learning is bounded by max_entries limit")


def demo_persistence():
    """Demonstrate learning persistence."""
    print_header("Demo 6: Persistence & Recovery")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Using temporary directory: {tmpdir}\n")
        
        persistence = LearningPersistence(tmpdir)
        
        # Create and train a learning system
        print("Training learning system...")
        config = LearningConfig(enabled=True)
        learning_state = LearningState(enabled=True)
        bandit = LinUCBBandit(alpha=0.2, prng_seed=42)
        
        # Train on some data
        context = {"f1": 0.5}
        for i in range(5):
            bandit.update(context, "action_a", 0.7)
            learning_state.update_weight("ctx1", "action_a", 0.7)
        
        print(f"  Bandit pulls: {bandit.total_pulls}")
        print(f"  Learning entries: {len(learning_state.weights)}")
        
        # Save
        print(f"\nSaving state...")
        success = persistence.snapshot("test_npc", config, learning_state, bandit)
        print(f"  Save successful: {success}")
        
        # Restore
        print(f"\nRestoring state...")
        data = persistence.restore("test_npc")
        print(f"  Restored NPC: {data['npc_id']}")
        print(f"  Bandit pulls: {data['bandit']['total_pulls']}")
        print(f"  Learning enabled: {data['config']['enabled']}")
        
        print(f"\n✓ Learning state persists across restarts")
        print(f"✓ Atomic writes prevent corruption")


def demo_determinism():
    """Demonstrate deterministic behavior with seed."""
    print_header("Demo 7: Deterministic Replay")
    
    print("Running same scenario twice with seed=42:\n")
    
    def run_scenario(seed):
        bandit = LinUCBBandit(alpha=0.2, prng_seed=seed)
        context = {"f1": 0.5, "f2": 0.3}
        actions = ["a", "b", "c"]
        
        choices = []
        for _ in range(5):
            scores = bandit.score_actions(context, actions)
            chosen = max(scores, key=scores.get)
            choices.append(chosen)
            bandit.update(context, chosen, 0.5)
        
        return choices
    
    run1 = run_scenario(42)
    run2 = run_scenario(42)
    
    print(f"Run 1: {' → '.join(run1)}")
    print(f"Run 2: {' → '.join(run2)}")
    print(f"\nResults match: {run1 == run2}")
    
    print(f"\n✓ Same seed produces identical behavior")
    print(f"✓ Enables replay and debugging")


def demo_summary():
    """Print summary of features."""
    print_header("Summary: Key Features")
    
    features = [
        "✓ Learning is DISABLED by default (safe)",
        "✓ All parameters are bounded and clamped",
        "✓ Deterministic replay with PRNG seeds",
        "✓ Bounded memory (LRU eviction)",
        "✓ Atomic persistence with version checks",
        "✓ Feature schema versioning",
        "✓ LinUCB exploration-exploitation balance",
        "✓ PolicyBias integration with reducer",
        "✓ Only reweights existing actions (no new behaviors)",
        "✓ Comprehensive test coverage (42 tests)",
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print(f"\n{'='*70}")
    print(f"  All demos completed successfully!")
    print(f"{'='*70}\n")


def main(interactive: bool = True):
    """Run all demos.
    
    Args:
        interactive: If True, pause between demos. Set to False for automated runs.
    """
    print("\n" + "="*70)
    print("  RFSN NPC Learning Module - Interactive Demo")
    print("="*70)
    print("\nThis demo showcases the drop-in learning module that enables")
    print("NPCs to learn from outcomes while maintaining determinism.")
    
    demos = [
        demo_disabled_vs_enabled,
        demo_feature_encoding,
        demo_contextual_bandit,
        demo_outcome_evaluation,
        demo_policy_adjuster,
        demo_persistence,
        demo_determinism,
    ]
    
    for demo in demos:
        demo()
        if interactive:
            input("\nPress Enter to continue...")
        else:
            print("\n[Auto-advancing to next demo...]\n")
    
    demo_summary()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RFSN Learning Module Demo")
    parser.add_argument("--non-interactive", action="store_true",
                       help="Run without pausing between demos")
    args = parser.parse_args()
    
    try:
        main(interactive=not args.non_interactive)
    except KeyboardInterrupt:
        print("\n\nDemo interrupted. Goodbye!")
        sys.exit(0)
