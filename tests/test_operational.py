"""
Tests for operational hardening modules.
"""
import json
import os
import tempfile
import threading
import time

import pytest

from rfsn_hybrid.supervisor import (
    Supervisor,
    SupervisorConfig,
    CrashJournal,
    CrashEntry,
    HeartbeatMonitor,
    heartbeat,
)
from rfsn_hybrid.heartbeat import (
    HeartbeatProtocol,
    BridgeStatus,
    HeartbeatMessage,
    get_fallback_dialogue,
)
from rfsn_hybrid.persistence import (
    StateSnapshot,
    get_state_snapshot,
)
from rfsn_hybrid.types import RFSNState


class TestCrashJournal:
    """Test crash journal functionality."""
    
    def test_log_and_read(self, tmp_path):
        path = tmp_path / "crash.jsonl"
        journal = CrashJournal(str(path))
        
        entry = CrashEntry(
            timestamp="2024-01-01T00:00:00",
            reason="Test crash",
            npc_id="lydia",
        )
        journal.log(entry)
        
        recent = journal.recent(10)
        assert len(recent) == 1
        assert recent[0].reason == "Test crash"
        assert recent[0].npc_id == "lydia"
    
    def test_clear(self, tmp_path):
        path = tmp_path / "crash.jsonl"
        journal = CrashJournal(str(path))
        
        journal.log(CrashEntry(timestamp="now", reason="test"))
        assert path.exists()
        
        journal.clear()
        assert not path.exists()


class TestHeartbeatMonitor:
    """Test heartbeat monitor."""
    
    def test_initial_alive(self):
        monitor = HeartbeatMonitor(timeout=10.0)
        assert monitor.is_alive()
    
    def test_beat_resets_timeout(self):
        monitor = HeartbeatMonitor(timeout=0.1)
        time.sleep(0.05)
        monitor.beat()
        assert monitor.is_alive()
    
    def test_timeout_declares_dead(self):
        monitor = HeartbeatMonitor(timeout=0.05)
        time.sleep(0.1)
        assert not monitor.is_alive()


class TestSupervisor:
    """Test supervisor functionality."""
    
    def test_runs_worker(self, tmp_path):
        config = SupervisorConfig(
            crash_journal_path=str(tmp_path / "crash.jsonl"),
            heartbeat_timeout=1.0,
        )
        supervisor = Supervisor(config)
        
        counter = [0]
        
        def worker():
            counter[0] += 1
            # Exit quickly
        
        supervisor.start(worker)
        assert counter[0] >= 1
    
    def test_stats(self, tmp_path):
        config = SupervisorConfig(
            crash_journal_path=str(tmp_path / "crash.jsonl"),
        )
        supervisor = Supervisor(config)
        
        stats = supervisor.stats()
        assert "running" in stats
        assert "restart_count" in stats


class TestHeartbeatProtocol:
    """Test heartbeat protocol."""
    
    def test_initial_status(self):
        protocol = HeartbeatProtocol()
        protocol.start()
        
        assert protocol.health.status == BridgeStatus.ONLINE
        protocol.stop()
    
    def test_send_heartbeat(self):
        protocol = HeartbeatProtocol()
        protocol.start()
        
        msg = protocol.send_heartbeat(queue_depth=5, active_npcs=2)
        
        assert msg.status == "online"
        assert msg.queue_depth == 5
        assert msg.active_npcs == 2
        
        protocol.stop()
    
    def test_message_serialization(self):
        msg = HeartbeatMessage(
            timestamp="2024-01-01T00:00:00",
            status="online",
            sequence=1,
            latency_ms=5.5,
        )
        
        json_str = msg.to_json()
        parsed = HeartbeatMessage.from_json(json_str)
        
        assert parsed.timestamp == msg.timestamp
        assert parsed.sequence == 1
    
    def test_fallback_dialogue(self):
        line = get_fallback_dialogue("default")
        assert len(line) > 0
        
        guard_line = get_fallback_dialogue("guard")
        assert len(guard_line) > 0


class TestStateSnapshot:
    """Test state persistence."""
    
    def test_save_and_load(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        state = RFSNState(
            npc_name="Lydia",
            role="Housecarl",
            affinity=0.75,
            mood="Happy",
            player_name="Player",
            player_playstyle="Adventurer",
        )
        
        snapshot.save("lydia", state, immediate=True)
        
        loaded = snapshot.load("lydia")
        assert loaded is not None
        assert loaded["state"]["npc_name"] == "Lydia"
        assert loaded["state"]["affinity"] == 0.75
    
    def test_recover_state(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        state = RFSNState(
            npc_name="Lydia",
            role="Housecarl",
            affinity=0.5,
            mood="Neutral",
            player_name="Player",
            player_playstyle="Adventurer",
        )
        
        snapshot.save("lydia", state, immediate=True)
        
        recovered = snapshot.recover_state("lydia")
        assert recovered is not None
        assert recovered.npc_name == "Lydia"
        assert recovered.affinity == 0.5
    
    def test_list_npcs(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        state = RFSNState(
            npc_name="Test",
            role="Test",
            affinity=0.0,
            mood="Neutral",
            player_name="Player",
            player_playstyle="Explorer",
        )
        
        snapshot.save("lydia", state, immediate=True)
        snapshot.save("guard", state, immediate=True)
        
        npcs = snapshot.list_npcs()
        assert "lydia" in npcs
        assert "guard" in npcs
    
    def test_delete(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        state = RFSNState(
            npc_name="Test",
            role="Test",
            affinity=0.0,
            mood="Neutral",
            player_name="Player",
            player_playstyle="Explorer",
        )
        
        snapshot.save("temp", state, immediate=True)
        assert "temp" in snapshot.list_npcs()
        
        snapshot.delete("temp")
        assert "temp" not in snapshot.list_npcs()
    
    def test_backup_rotation(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        state = RFSNState(
            npc_name="Lydia",
            role="Housecarl",
            affinity=0.0,
            mood="Neutral",
            player_name="Player",
            player_playstyle="Explorer",
        )
        
        # Save multiple times to trigger backup rotation
        for i in range(5):
            state.affinity = i * 0.1
            snapshot.save("lydia", state, immediate=True)
        
        # Should have backups
        backup1 = tmp_path / "lydia.backup1.json"
        assert backup1.exists()
    
    def test_stats(self, tmp_path):
        snapshot = StateSnapshot(str(tmp_path))
        
        stats = snapshot.stats()
        assert "base_path" in stats
        assert "cached_npcs" in stats
        assert "saved_npcs" in stats
