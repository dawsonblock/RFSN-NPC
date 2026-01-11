"""
Performance benchmarks for RFSN engine.

Run with: python -m pytest benchmarks/ -v --benchmark-only
Or standalone: python benchmarks/benchmark_reducer.py
"""
import copy
import time
import statistics
from typing import List, Tuple

# Allow running as standalone script
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rfsn_hybrid.types import RFSNState
from rfsn_hybrid.core.state.event_types import (
    affinity_delta_event,
    mood_set_event,
    player_event,
)
from rfsn_hybrid.core.state.reducer import reduce_state, reduce_events
from rfsn_hybrid.core.state.store import StateStore


def create_state() -> RFSNState:
    """Create a test state."""
    return RFSNState(
        npc_name="Lydia",
        role="Housecarl",
        affinity=0.5,
        mood="Neutral",
        player_name="Player",
        player_playstyle="Adventurer",
    )


def benchmark(fn, iterations: int = 1000) -> Tuple[float, float, float]:
    """
    Benchmark a function.
    
    Returns:
        (mean_ms, min_ms, max_ms)
    """
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
    
    return (
        statistics.mean(times),
        min(times),
        max(times),
    )


def benchmark_reduce_single_event():
    """Benchmark single event reduction."""
    state = create_state()
    event = affinity_delta_event("lydia", 0.1)
    
    def run():
        reduce_state(state, event)
    
    mean, min_t, max_t = benchmark(run, iterations=10000)
    print(f"reduce_state (single event):")
    print(f"  Mean: {mean:.4f}ms  Min: {min_t:.4f}ms  Max: {max_t:.4f}ms")
    return mean


def benchmark_reduce_event_sequence():
    """Benchmark sequence of events."""
    state = create_state()
    events = [
        affinity_delta_event("lydia", 0.1),
        mood_set_event("lydia", "Happy"),
        player_event("lydia", "GIFT", 0.5, ["positive"]),
        affinity_delta_event("lydia", -0.05),
        mood_set_event("lydia", "Neutral"),
    ] * 10  # 50 events
    
    def run():
        reduce_events(state, events)
    
    mean, min_t, max_t = benchmark(run, iterations=1000)
    print(f"reduce_events (50 events):")
    print(f"  Mean: {mean:.4f}ms  Min: {min_t:.4f}ms  Max: {max_t:.4f}ms")
    print(f"  Per event: {mean/50:.4f}ms")
    return mean


def benchmark_state_store_dispatch():
    """Benchmark StateStore dispatch."""
    state = create_state()
    store = StateStore(state)
    event = affinity_delta_event("lydia", 0.01)
    
    def run():
        store.dispatch(event)
    
    mean, min_t, max_t = benchmark(run, iterations=10000)
    print(f"StateStore.dispatch:")
    print(f"  Mean: {mean:.4f}ms  Min: {min_t:.4f}ms  Max: {max_t:.4f}ms")
    return mean


def benchmark_snapshot_caching():
    """Benchmark snapshot with caching."""
    state = create_state()
    store = StateStore(state)
    
    # Warm up cache
    store.get_snapshot()
    
    def run_cached():
        store.get_snapshot()
    
    mean_cached, _, _ = benchmark(run_cached, iterations=10000)
    
    # With mutation between reads
    event = affinity_delta_event("lydia", 0.001)
    
    def run_with_mutation():
        store.dispatch(event)
        store.get_snapshot()
    
    mean_mutation, _, _ = benchmark(run_with_mutation, iterations=1000)
    
    print(f"StateStore.get_snapshot:")
    print(f"  Cached (no change): {mean_cached:.4f}ms")
    print(f"  After mutation: {mean_mutation:.4f}ms")
    return mean_cached


def benchmark_deep_copy():
    """Benchmark deep copy vs shallow copy."""
    state = create_state()
    
    def deep():
        copy.deepcopy(state)
    
    def shallow():
        copy.copy(state)
    
    mean_deep, _, _ = benchmark(deep, iterations=10000)
    mean_shallow, _, _ = benchmark(shallow, iterations=10000)
    
    print(f"Copy comparison:")
    print(f"  Deep copy: {mean_deep:.4f}ms")
    print(f"  Shallow copy: {mean_shallow:.4f}ms")
    print(f"  Speedup: {mean_deep/mean_shallow:.1f}x")
    return mean_deep, mean_shallow


def run_all_benchmarks():
    """Run all benchmarks."""
    print("=" * 60)
    print("RFSN Performance Benchmarks")
    print("=" * 60)
    print()
    
    results = {}
    
    results["reduce_single"] = benchmark_reduce_single_event()
    print()
    
    results["reduce_sequence"] = benchmark_reduce_event_sequence()
    print()
    
    results["store_dispatch"] = benchmark_state_store_dispatch()
    print()
    
    results["snapshot_cached"] = benchmark_snapshot_caching()
    print()
    
    deep, shallow = benchmark_deep_copy()
    results["deep_copy"] = deep
    results["shallow_copy"] = shallow
    
    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Events/sec: {1000 / results['reduce_single']:.0f}")
    print(f"  Dispatches/sec: {1000 / results['store_dispatch']:.0f}")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    run_all_benchmarks()
