"""
Tests for validation module.
"""
import pytest

from rfsn_hybrid.validation import (
    validate_npc_name,
    validate_affinity,
    validate_mood,
    validate_user_input,
    validate_config,
    sanitize_text,
    clamp_affinity,
)


class TestValidateNpcName:
    """Test NPC name validation."""
    
    def test_valid_name(self):
        result = validate_npc_name("Lydia")
        assert result.is_valid
    
    def test_empty_name_invalid(self):
        result = validate_npc_name("")
        assert not result.is_valid
        assert "empty" in result.errors[0].message.lower()
    
    def test_long_name_invalid(self):
        result = validate_npc_name("A" * 100)
        assert not result.is_valid
        assert "too long" in result.errors[0].message.lower()
    
    def test_name_with_apostrophe_valid(self):
        result = validate_npc_name("J'zargo")
        assert result.is_valid
    
    def test_name_with_hyphen_valid(self):
        result = validate_npc_name("Dar-Ma")
        assert result.is_valid


class TestValidateAffinity:
    """Test affinity validation."""
    
    def test_valid_affinity(self):
        assert validate_affinity(0.5).is_valid
        assert validate_affinity(-0.5).is_valid
        assert validate_affinity(0.0).is_valid
    
    def test_boundary_values_valid(self):
        assert validate_affinity(-1.0).is_valid
        assert validate_affinity(1.0).is_valid
    
    def test_out_of_range_invalid(self):
        assert not validate_affinity(1.5).is_valid
        assert not validate_affinity(-1.5).is_valid


class TestValidateMood:
    """Test mood validation."""
    
    def test_standard_moods_valid(self):
        assert validate_mood("Neutral").is_valid
        assert validate_mood("Angry").is_valid
        assert validate_mood("Happy").is_valid
    
    def test_empty_mood_invalid(self):
        result = validate_mood("")
        assert not result.is_valid


class TestValidateUserInput:
    """Test user input validation."""
    
    def test_valid_input(self):
        result = validate_user_input("Hello, how are you?")
        assert result.is_valid
    
    def test_empty_input_invalid(self):
        result = validate_user_input("")
        assert not result.is_valid
    
    def test_long_input_invalid(self):
        result = validate_user_input("A" * 3000)
        assert not result.is_valid
    
    def test_script_injection_detected(self):
        result = validate_user_input("<script>alert('xss')</script>")
        assert not result.is_valid
        assert "suspicious" in result.errors[0].message.lower()


class TestValidateConfig:
    """Test config validation."""
    
    def test_valid_config(self):
        config = {
            "npc_name": "Lydia",
            "role": "Housecarl",
            "affinity": 0.5,
            "mood": "Neutral",
        }
        result = validate_config(config)
        assert result.is_valid
    
    def test_missing_required_fields(self):
        result = validate_config({})
        assert not result.is_valid
        assert len(result.errors) >= 2  # npc_name and role


class TestSanitizeText:
    """Test text sanitization."""
    
    def test_removes_null_bytes(self):
        text = sanitize_text("hello\x00world")
        assert "\x00" not in text
        assert text == "helloworld"
    
    def test_normalizes_whitespace(self):
        text = sanitize_text("hello   world")
        assert text == "hello world"
    
    def test_strips_edges(self):
        text = sanitize_text("  hello  ")
        assert text == "hello"


class TestClampAffinity:
    """Test affinity clamping."""
    
    def test_clamps_high(self):
        assert clamp_affinity(2.0) == 1.0
    
    def test_clamps_low(self):
        assert clamp_affinity(-2.0) == -1.0
    
    def test_passthrough_valid(self):
        assert clamp_affinity(0.5) == 0.5
