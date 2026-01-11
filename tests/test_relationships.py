"""
Tests for multi-NPC relationships.
"""
import os
import tempfile

import pytest

from rfsn_hybrid.relationships import (
    NPCOpinion,
    NPCRelationshipProfile,
    RelationshipNetwork,
    get_relevant_npcs_for_topic,
)


@pytest.fixture
def temp_network(tmp_path):
    """Create a temporary relationship network."""
    path = str(tmp_path / "relationships.json")
    return RelationshipNetwork(path)


class TestNPCOpinion:
    """Test NPCOpinion dataclass."""
    
    def test_default_values(self):
        """Should have neutral defaults."""
        opinion = NPCOpinion(target_npc="Test")
        
        assert opinion.affinity == 0.0
        assert opinion.trust == 0.5
        assert opinion.respect == 0.5
    
    def test_roundtrip(self):
        """Should serialize and deserialize."""
        opinion = NPCOpinion(
            target_npc="Belethor",
            affinity=-0.5,
            trust=0.3,
        )
        
        data = opinion.to_dict()
        restored = NPCOpinion.from_dict(data)
        
        assert restored.target_npc == "Belethor"
        assert restored.affinity == -0.5


class TestNPCRelationshipProfile:
    """Test NPCRelationshipProfile."""
    
    def test_set_ally(self):
        """Setting ally should update lists."""
        profile = NPCRelationshipProfile(npc_name="Lydia")
        profile.set_ally("Faendal")
        
        assert "Faendal" in profile.allies
        assert "Faendal" not in profile.rivals
    
    def test_set_rival(self):
        """Setting rival should update lists."""
        profile = NPCRelationshipProfile(npc_name="Lydia")
        profile.set_rival("Belethor")
        
        assert "Belethor" in profile.rivals
        assert "Belethor" not in profile.allies
    
    def test_ally_to_rival(self):
        """Converting ally to rival should move between lists."""
        profile = NPCRelationshipProfile(npc_name="Lydia")
        profile.set_ally("Faendal")
        profile.set_rival("Faendal")
        
        assert "Faendal" in profile.rivals
        assert "Faendal" not in profile.allies


class TestRelationshipNetwork:
    """Test RelationshipNetwork."""
    
    def test_persistence(self, tmp_path):
        """Network should persist to disk."""
        path = str(tmp_path / "relationships.json")
        
        network1 = RelationshipNetwork(path)
        network1.update_relationship("Lydia", "Belethor", affinity_delta=0.5)
        
        network2 = RelationshipNetwork(path)
        opinion = network2.get_opinion("Lydia", "Belethor")
        
        assert opinion.affinity == 0.5
    
    def test_update_relationship(self, temp_network):
        """Should update relationship values."""
        opinion = temp_network.update_relationship(
            "Lydia", "Guard",
            affinity_delta=0.3,
            trust_delta=0.2,
        )
        
        assert opinion.affinity == 0.3
        assert opinion.trust == 0.7
    
    def test_affinity_bounds(self, temp_network):
        """Affinity should stay in [-1, 1]."""
        temp_network.update_relationship("A", "B", affinity_delta=2.0)
        opinion = temp_network.get_opinion("A", "B")
        assert opinion.affinity == 1.0
        
        temp_network.update_relationship("A", "B", affinity_delta=-5.0)
        assert temp_network.get_opinion("A", "B").affinity == -1.0
    
    def test_auto_ally_classification(self, temp_network):
        """High affinity should auto-classify as ally."""
        temp_network.update_relationship("Lydia", "Faendal", affinity_delta=0.7)
        
        assert "Faendal" in temp_network.get_allies("Lydia")
    
    def test_auto_rival_classification(self, temp_network):
        """Low affinity should auto-classify as rival."""
        temp_network.update_relationship("Lydia", "Thief", affinity_delta=-0.6)
        
        assert "Thief" in temp_network.get_rivals("Lydia")
    
    def test_shared_experience(self, temp_network):
        """Shared experiences should create bonds."""
        temp_network.add_shared_experience(
            ["Lydia", "Faendal", "Player"],
            "Fought the dragon at Whiterun"
        )
        
        profile = temp_network.get_profile("Lydia")
        assert "Fought the dragon at Whiterun" in profile.shared_experiences
        
        # Should increase affinity between participants
        opinion = temp_network.get_opinion("Lydia", "Faendal")
        assert opinion.affinity > 0
    
    def test_add_note(self, temp_network):
        """Should store notes about NPCs."""
        temp_network.add_note("Lydia", "Belethor", "He tried to sell me a sword")
        
        opinion = temp_network.get_opinion("Lydia", "Belethor")
        assert "He tried to sell me a sword" in opinion.notes
    
    def test_relationship_summary(self, temp_network):
        """Should generate readable summary."""
        profile = temp_network.get_profile("Lydia")
        profile.set_ally("Faendal")
        profile.set_rival("Thief")
        
        summary = temp_network.get_relationship_summary("Lydia")
        
        assert "Lydia" in summary
        assert "Faendal" in summary or "Allies" in summary


class TestReputationPropagation:
    """Test reputation spreading through network."""
    
    def test_ally_influence(self, temp_network):
        """Allies should adopt positive sentiment."""
        # Set up Lydia with an ally
        temp_network.get_profile("Lydia").set_ally("Faendal")
        
        # Player does something good to Lydia
        changes = temp_network.propagate_player_reputation(
            "Lydia", "gift", affinity_change=0.4
        )
        
        # Faendal should also gain affinity
        assert "Faendal" in changes
        assert changes["Faendal"] > 0
    
    def test_rival_contrarian(self, temp_network):
        """Rivals should react oppositely."""
        # Set up Lydia with a rival
        temp_network.get_profile("Lydia").set_rival("Belethor")
        
        # Player does something good to Lydia
        changes = temp_network.propagate_player_reputation(
            "Lydia", "gift", affinity_change=0.4
        )
        
        # Belethor should lose affinity (contrarian)
        assert "Belethor" in changes
        assert changes["Belethor"] < 0
    
    def test_wipe(self, temp_network):
        """Wipe should clear all data."""
        temp_network.update_relationship("A", "B", affinity_delta=0.5)
        temp_network.wipe()
        
        assert len(temp_network.profiles) == 0


class TestRelevantNPCs:
    """Test finding relevant NPCs for topics."""
    
    def test_finds_npc_from_notes(self, temp_network):
        """Should find NPCs mentioned in notes."""
        temp_network.add_note("Lydia", "Belethor", "He sells weapons and armor")
        
        relevant = get_relevant_npcs_for_topic(temp_network, "Lydia", "weapons")
        
        assert "Belethor" in relevant
    
    def test_finds_shared_experience_participants(self, temp_network):
        """Should find NPCs from shared experiences."""
        temp_network.add_shared_experience(
            ["Lydia", "Faendal"],
            "Fought bandits together"
        )
        
        relevant = get_relevant_npcs_for_topic(temp_network, "Lydia", "bandits")
        
        assert "Faendal" in relevant
