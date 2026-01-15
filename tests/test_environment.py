"""
Tests for environment feedback layer.

Validates that:
- Events are properly adapted
- Consequences are correctly mapped
- Signals are normalized and bounded
- System can be disabled
"""
import pytest

from rfsn_hybrid.environment import (
    EventAdapter,
    GameEvent,
    GameEventType,
    ConsequenceMapper,
    ConsequenceSignal,
    ConsequenceType,
    SignalNormalizer,
)


class TestEventAdapter:
    """Tests for EventAdapter."""
    
    def test_disabled_returns_none(self):
        """When disabled, should return None."""
        adapter = EventAdapter(enabled=False)
        
        event = adapter.adapt(
            GameEventType.COMBAT_START,
            npc_id="npc1",
        )
        
        assert event is None
    
    def test_creates_valid_event(self):
        """Should create valid GameEvent."""
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(
            event_type=GameEventType.COMBAT_START,
            npc_id="npc1",
            player_id="player1",
            magnitude=0.7,
        )
        
        assert event is not None
        assert event.event_type == GameEventType.COMBAT_START
        assert event.npc_id == "npc1"
        assert event.player_id == "player1"
        assert event.magnitude == 0.7
    
    def test_clamps_magnitude(self):
        """Should clamp magnitude to [0, 1]."""
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(
            GameEventType.COMBAT_HIT_TAKEN,
            npc_id="npc1",
            magnitude=5.0,  # Too high
        )
        
        assert event.magnitude == 1.0
        
        event = adapter.adapt(
            GameEventType.COMBAT_HIT_TAKEN,
            npc_id="npc1",
            magnitude=-0.5,  # Too low
        )
        
        assert event.magnitude == 0.0
    
    def test_tracks_statistics(self):
        """Should track event statistics."""
        adapter = EventAdapter(enabled=True)
        
        adapter.adapt(GameEventType.COMBAT_START, "npc1")
        adapter.adapt(GameEventType.COMBAT_START, "npc1")
        adapter.adapt(GameEventType.DIALOGUE_START, "npc1")
        
        stats = adapter.get_statistics()
        assert stats["total_events"] == 3
        assert stats["events_by_type"]["combat_start"] == 2
        assert stats["events_by_type"]["dialogue_start"] == 1
    
    def test_combat_convenience_method(self):
        """Should provide convenient combat event creation."""
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt_combat_event(
            npc_id="npc1",
            event_subtype="hit_taken",
            damage=0.5,
            attacker="enemy1",
        )
        
        assert event.event_type == GameEventType.COMBAT_HIT_TAKEN
        assert event.magnitude == 0.5
        assert event.data["attacker"] == "enemy1"
    
    def test_dialogue_convenience_method(self):
        """Should provide convenient dialogue event creation."""
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt_dialogue_event(
            npc_id="npc1",
            player_id="player1",
            event_subtype="persuasion_success",
            branch_id="branch_5",
        )
        
        assert event.event_type == GameEventType.DIALOGUE_PERSUASION_SUCCESS
        assert event.player_id == "player1"
        assert event.data["branch_id"] == "branch_5"
    
    def test_time_convenience_method(self):
        """Should provide convenient time event creation."""
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt_time_event(
            npc_id="npc1",
            hours_passed=12.0,
        )
        
        assert event.event_type == GameEventType.TIME_PASSED
        assert 0.0 < event.magnitude <= 1.0
        assert event.data["hours"] == 12.0


class TestConsequenceMapper:
    """Tests for ConsequenceMapper."""
    
    def test_disabled_returns_empty(self):
        """When disabled, should return empty list."""
        mapper = ConsequenceMapper(enabled=False)
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(GameEventType.COMBAT_START, "npc1")
        signals = mapper.map_event(event)
        
        assert signals == []
    
    def test_maps_combat_start(self):
        """Should map combat start to appropriate signals."""
        mapper = ConsequenceMapper(enabled=True)
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(
            GameEventType.COMBAT_START,
            npc_id="npc1",
            magnitude=0.8,
        )
        
        signals = mapper.map_event(event)
        
        # Should produce STRESS and THREAT signals
        assert len(signals) >= 1
        types = [s.consequence_type for s in signals]
        assert ConsequenceType.STRESS in types or ConsequenceType.THREAT in types
    
    def test_scales_by_magnitude(self):
        """Signal intensity should scale with event magnitude."""
        mapper = ConsequenceMapper(enabled=True)
        adapter = EventAdapter(enabled=True)
        
        event_weak = adapter.adapt(
            GameEventType.COMBAT_HIT_TAKEN,
            npc_id="npc1",
            magnitude=0.2,
        )
        
        event_strong = adapter.adapt(
            GameEventType.COMBAT_HIT_TAKEN,
            npc_id="npc1",
            magnitude=0.9,
        )
        
        signals_weak = mapper.map_event(event_weak)
        signals_strong = mapper.map_event(event_strong)
        
        # Strong event should have higher intensity
        if signals_weak and signals_strong:
            assert signals_strong[0].intensity > signals_weak[0].intensity
    
    def test_positive_events(self):
        """Positive events should generate positive consequences."""
        mapper = ConsequenceMapper(enabled=True)
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(
            GameEventType.QUEST_COMPLETED,
            npc_id="npc1",
        )
        
        signals = mapper.map_event(event)
        
        # Should include positive consequences
        types = [s.consequence_type for s in signals]
        assert ConsequenceType.ACHIEVEMENT in types or ConsequenceType.BONDING in types
    
    def test_negative_events(self):
        """Negative events should generate negative consequences."""
        mapper = ConsequenceMapper(enabled=True)
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(
            GameEventType.ITEM_STOLEN,
            npc_id="npc1",
        )
        
        signals = mapper.map_event(event)
        
        # Should include negative consequences
        types = [s.consequence_type for s in signals]
        assert ConsequenceType.INJUSTICE in types or ConsequenceType.ALIENATION in types
    
    def test_batch_mapping(self):
        """Should map multiple events efficiently."""
        mapper = ConsequenceMapper(enabled=True)
        adapter = EventAdapter(enabled=True)
        
        events = [
            adapter.adapt(GameEventType.COMBAT_START, "npc1"),
            adapter.adapt(GameEventType.DIALOGUE_START, "npc1"),
            adapter.adapt(GameEventType.TIME_PASSED, "npc1"),
        ]
        
        signals = mapper.map_batch(events)
        
        # Should have signals from all events
        assert len(signals) > 0
    
    def test_custom_mapping(self):
        """Should allow custom event mappings."""
        custom = {
            GameEventType.COMBAT_START: [
                (ConsequenceType.ACHIEVEMENT, 0.9, ["mood"], 0.1)
            ]
        }
        
        mapper = ConsequenceMapper(custom_mappings=custom, enabled=True)
        adapter = EventAdapter(enabled=True)
        
        event = adapter.adapt(GameEventType.COMBAT_START, "npc1")
        signals = mapper.map_event(event)
        
        # Should use custom mapping
        assert any(s.consequence_type == ConsequenceType.ACHIEVEMENT for s in signals)


class TestSignalNormalizer:
    """Tests for SignalNormalizer."""
    
    def test_disabled_returns_zero_intensity(self):
        """When disabled, should return zero intensity signals."""
        normalizer = SignalNormalizer(enabled=False)
        
        signal = ConsequenceSignal(
            consequence_type=ConsequenceType.STRESS,
            intensity=0.8,
            source_event=GameEventType.COMBAT_START,
        )
        
        normalized = normalizer.normalize(signal)
        assert normalized.intensity == 0.0
    
    def test_applies_dampening(self):
        """Should dampen signal intensities."""
        normalizer = SignalNormalizer(
            dampening_factor=0.5,
            enabled=True,
        )
        
        signal = ConsequenceSignal(
            consequence_type=ConsequenceType.STRESS,
            intensity=1.0,
            source_event=GameEventType.COMBAT_START,
        )
        
        normalized = normalizer.normalize(signal)
        assert normalized.intensity < signal.intensity
    
    def test_affinity_impact(self):
        """Should calculate affinity deltas."""
        normalizer = SignalNormalizer(enabled=True)
        
        # Bonding should increase affinity
        signal = ConsequenceSignal(
            consequence_type=ConsequenceType.BONDING,
            intensity=0.8,
            source_event=GameEventType.DIALOGUE_START,
        )
        
        normalized = normalizer.normalize(signal)
        assert normalized.affinity_delta > 0
        
        # Alienation should decrease affinity
        signal = ConsequenceSignal(
            consequence_type=ConsequenceType.ALIENATION,
            intensity=0.8,
            source_event=GameEventType.ITEM_STOLEN,
        )
        
        normalized = normalizer.normalize(signal)
        assert normalized.affinity_delta < 0
    
    def test_clamps_affinity_change(self):
        """Should clamp affinity changes to max."""
        normalizer = SignalNormalizer(
            enabled=True,
            dampening_factor=1.0,
            max_affinity_change=0.1,
        )
        
        # Very strong signal
        signal = ConsequenceSignal(
            consequence_type=ConsequenceType.BONDING,
            intensity=1.0,
            source_event=GameEventType.QUEST_COMPLETED,
        )
        
        normalized = normalizer.normalize(signal)
        assert abs(normalized.affinity_delta) <= 0.1
    
    def test_mood_threshold(self):
        """Should only set mood for strong signals."""
        normalizer = SignalNormalizer(enabled=True, dampening_factor=1.0)
        
        # Weak signal - no mood change
        weak = ConsequenceSignal(
            consequence_type=ConsequenceType.STRESS,
            intensity=0.2,
            source_event=GameEventType.COMBAT_START,
        )
        
        normalized_weak = normalizer.normalize(weak)
        assert normalized_weak.mood_impact is None
        
        # Strong signal - mood change
        strong = ConsequenceSignal(
            consequence_type=ConsequenceType.STRESS,
            intensity=0.8,
            source_event=GameEventType.COMBAT_START,
        )
        
        normalized_strong = normalizer.normalize(strong)
        assert normalized_strong.mood_impact is not None
    
    def test_batch_normalization(self):
        """Should normalize multiple signals."""
        normalizer = SignalNormalizer(enabled=True)
        
        signals = [
            ConsequenceSignal(
                ConsequenceType.STRESS,
                0.5,
                GameEventType.COMBAT_START,
            ),
            ConsequenceSignal(
                ConsequenceType.BONDING,
                0.6,
                GameEventType.DIALOGUE_START,
            ),
        ]
        
        normalized = normalizer.normalize_batch(signals)
        assert len(normalized) == 2
    
    def test_signal_aggregation(self):
        """Should aggregate multiple signals into one."""
        normalizer = SignalNormalizer(enabled=True)
        
        signals = [
            ConsequenceSignal(
                ConsequenceType.BONDING,
                0.5,
                GameEventType.DIALOGUE_START,
            ),
            ConsequenceSignal(
                ConsequenceType.BONDING,
                0.6,
                GameEventType.QUEST_COMPLETED,
            ),
        ]
        
        aggregated = normalizer.aggregate(signals)
        
        # Should have combined affinity impact
        assert aggregated.affinity_delta > 0
        assert aggregated.intensity > 0
    
    def test_signal_filtering(self):
        """Should filter signals by intensity and target."""
        normalizer = SignalNormalizer(enabled=True)
        
        signals = [
            ConsequenceSignal(
                ConsequenceType.STRESS,
                0.05,  # Weak
                GameEventType.TIME_PASSED,
                affects=["mood"],
            ),
            ConsequenceSignal(
                ConsequenceType.BONDING,
                0.8,  # Strong
                GameEventType.QUEST_COMPLETED,
                affects=["relationship"],
            ),
        ]
        
        # Filter by intensity
        filtered = normalizer.filter_by_intensity(signals, min_intensity=0.1)
        assert len(filtered) == 1
        assert filtered[0].consequence_type == ConsequenceType.BONDING
        
        # Filter by affects
        mood_signals = normalizer.filter_by_affects(signals, "mood")
        assert len(mood_signals) == 1
        assert mood_signals[0].consequence_type == ConsequenceType.STRESS


class TestEnvironmentIntegration:
    """Integration tests for environment feedback."""
    
    def test_end_to_end_pipeline(self):
        """Test complete event -> signal -> normalized pipeline."""
        adapter = EventAdapter(enabled=True)
        mapper = ConsequenceMapper(enabled=True)
        normalizer = SignalNormalizer(enabled=True)
        
        # 1. Adapt event
        event = adapter.adapt_combat_event(
            npc_id="npc1",
            event_subtype="hit_taken",
            damage=0.7,
        )
        
        # 2. Map to consequences
        signals = mapper.map_event(event)
        assert len(signals) > 0
        
        # 3. Normalize
        normalized = normalizer.normalize_batch(signals)
        assert len(normalized) > 0
        
        # 4. Verify bounded
        for sig in normalized:
            assert 0.0 <= sig.intensity <= 1.0
            assert abs(sig.affinity_delta) <= 0.15
    
    def test_multiple_events_aggregation(self):
        """Test handling multiple concurrent events."""
        adapter = EventAdapter(enabled=True)
        mapper = ConsequenceMapper(enabled=True)
        normalizer = SignalNormalizer(enabled=True)
        
        # Multiple events happen
        events = [
            adapter.adapt(GameEventType.COMBAT_HIT_TAKEN, "npc1", magnitude=0.6),
            adapter.adapt(GameEventType.DIALOGUE_PERSUASION_SUCCESS, "npc1"),
            adapter.adapt(GameEventType.TIME_PASSED, "npc1", magnitude=0.1),
        ]
        
        # Map all events
        all_signals = mapper.map_batch(events)
        
        # Aggregate into single normalized signal
        aggregated = normalizer.aggregate(all_signals)
        
        # Should be bounded
        assert abs(aggregated.affinity_delta) <= 0.15
        assert 0.0 <= aggregated.intensity <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
