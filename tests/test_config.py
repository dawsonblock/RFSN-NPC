"""
Tests for the NPC configuration system.
"""
import os
import json
import tempfile

import pytest

from rfsn_hybrid.config import (
    NPCConfig,
    ConfigManager,
    get_preset,
    list_presets,
    PRESETS,
)


class TestNPCConfig:
    """Test NPCConfig dataclass."""
    
    def test_default_values(self):
        """Should have sensible defaults."""
        config = NPCConfig(name="Test", role="Tester")
        
        assert config.name == "Test"
        assert config.role == "Tester"
        assert config.initial_affinity == 0.5
        assert config.initial_mood == "Neutral"
        assert config.personality_traits == []
    
    def test_to_dict_roundtrip(self):
        """Should serialize and deserialize correctly."""
        original = NPCConfig(
            name="Lydia",
            role="Housecarl",
            initial_affinity=0.75,
            personality_traits=["loyal", "stoic"],
            likes=["combat"],
        )
        
        data = original.to_dict()
        restored = NPCConfig.from_dict(data)
        
        assert restored.name == original.name
        assert restored.initial_affinity == original.initial_affinity
        assert restored.personality_traits == original.personality_traits
    
    def test_save_and_load(self):
        """Should persist to file correctly."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_config.json")
            
            original = NPCConfig(
                name="TestNPC",
                role="Warrior",
                initial_affinity=0.8,
                backstory="A test character",
            )
            original.save(path)
            
            loaded = NPCConfig.load(path)
            
            assert loaded is not None
            assert loaded.name == "TestNPC"
            assert loaded.backstory == "A test character"
    
    def test_load_missing_file(self):
        """Loading non-existent file should return None."""
        result = NPCConfig.load("/nonexistent/path.json")
        assert result is None
    
    def test_from_dict_ignores_extra_fields(self):
        """Should ignore unknown fields in dict."""
        data = {
            "name": "Test",
            "role": "Tester",
            "unknown_field": "ignored",
            "another_unknown": 123,
        }
        
        config = NPCConfig.from_dict(data)
        
        assert config.name == "Test"
        assert not hasattr(config, "unknown_field")


class TestPresets:
    """Test built-in NPC presets."""
    
    def test_lydia_preset_exists(self):
        """Lydia preset should be available."""
        config = get_preset("lydia")
        
        assert config is not None
        assert config.name == "Lydia"
        assert config.role == "Housecarl"
        assert "loyal" in config.personality_traits
    
    def test_all_presets_have_required_fields(self):
        """All presets should have name and role."""
        for name in list_presets():
            config = get_preset(name)
            assert config is not None
            assert config.name
            assert config.role
    
    def test_list_presets_returns_names(self):
        """list_presets should return all preset names."""
        names = list_presets()
        
        assert "lydia" in names
        assert "merchant" in names
        assert "guard" in names
        assert len(names) == len(PRESETS)
    
    def test_get_preset_case_insensitive(self):
        """Preset lookup should be case-insensitive."""
        assert get_preset("LYDIA") is not None
        assert get_preset("Lydia") is not None
        assert get_preset("lydia") is not None


class TestConfigManager:
    """Test ConfigManager class."""
    
    def test_get_preset(self):
        """Should find built-in presets."""
        with tempfile.TemporaryDirectory() as d:
            manager = ConfigManager(d)
            config = manager.get("lydia")
            
            assert config is not None
            assert config.name == "Lydia"
    
    def test_get_custom_file(self):
        """Should load custom config files."""
        with tempfile.TemporaryDirectory() as d:
            # Create custom config
            custom = NPCConfig(name="CustomNPC", role="Hero")
            custom_path = os.path.join(d, "custom_npc.json")
            custom.save(custom_path)
            
            manager = ConfigManager(d)
            config = manager.get("custom_npc")
            
            assert config is not None
            assert config.name == "CustomNPC"
    
    def test_save_creates_file(self):
        """save() should create config file."""
        with tempfile.TemporaryDirectory() as d:
            manager = ConfigManager(d)
            
            config = NPCConfig(name="NewNPC", role="Mage")
            path = manager.save(config)
            
            assert os.path.exists(path)
            
            # Should be loadable
            loaded = manager.get("newnpc")
            assert loaded is not None
    
    def test_list_available_includes_all(self):
        """list_available should include presets and custom files."""
        with tempfile.TemporaryDirectory() as d:
            # Create custom config
            custom = NPCConfig(name="Custom", role="Test")
            custom.save(os.path.join(d, "custom.json"))
            
            manager = ConfigManager(d)
            available = manager.list_available()
            
            # Should include preset
            assert "lydia" in available
            # Should include custom
            assert "custom" in available
    
    def test_caching(self):
        """Config should be cached after first load."""
        with tempfile.TemporaryDirectory() as d:
            manager = ConfigManager(d)
            
            # First load
            config1 = manager.get("lydia")
            # Second load (should hit cache)
            config2 = manager.get("lydia")
            
            assert config1 is config2  # Same object
