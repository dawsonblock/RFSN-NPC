"""
Input validation and sanitization for RFSN engine.

Validates:
- NPC configuration
- User input
- State values
- File paths
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ValidationError:
    """A validation error."""
    field: str
    message: str
    value: str = ""


class ValidationResult:
    """Result of validation check."""
    
    def __init__(self):
        self.errors: List[ValidationError] = []
    
    def add_error(self, field: str, message: str, value: str = "") -> None:
        self.errors.append(ValidationError(field, message, value))
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0
    
    def raise_if_invalid(self, context: str = "Validation") -> None:
        if not self.is_valid:
            msgs = [f"{e.field}: {e.message}" for e in self.errors]
            raise ValueError(f"{context} failed:\n" + "\n".join(msgs))


def validate_npc_name(name: str) -> ValidationResult:
    """Validate NPC name."""
    result = ValidationResult()
    
    if not name:
        result.add_error("npc_name", "Name cannot be empty")
    elif len(name) > 64:
        result.add_error("npc_name", "Name too long (max 64 chars)", name[:20])
    elif not re.match(r'^[\w\s\'-]+$', name):
        result.add_error("npc_name", "Name has invalid characters", name)
    
    return result


def validate_affinity(value: float) -> ValidationResult:
    """Validate affinity is in range."""
    result = ValidationResult()
    
    if not isinstance(value, (int, float)):
        result.add_error("affinity", "Must be a number", str(value))
    elif value < -1.0 or value > 1.0:
        result.add_error("affinity", "Must be between -1.0 and 1.0", str(value))
    
    return result


def validate_mood(mood: str) -> ValidationResult:
    """Validate mood value."""
    result = ValidationResult()
    
    VALID_MOODS = {
        "Neutral", "Happy", "Pleased", "Warm", "Grateful",
        "Angry", "Offended", "Hostile", "Suspicious", "Sad",
        "Fearful", "Curious", "Bored", "Tired",
    }
    
    if not mood:
        result.add_error("mood", "Mood cannot be empty")
    elif mood not in VALID_MOODS:
        # Allow custom moods but warn
        pass
    
    return result


def validate_user_input(text: str, max_length: int = 2048) -> ValidationResult:
    """Validate and sanitize user input."""
    result = ValidationResult()
    
    if not text:
        result.add_error("input", "Input cannot be empty")
        return result
    
    if len(text) > max_length:
        result.add_error("input", f"Input too long (max {max_length})", text[:50])
    
    # Check for potential injection patterns
    dangerous = ["<script", "javascript:", "onerror=", "onload="]
    for pattern in dangerous:
        if pattern.lower() in text.lower():
            result.add_error("input", f"Suspicious pattern detected", pattern)
    
    return result


def validate_model_path(path: str) -> ValidationResult:
    """Validate model path exists and is a GGUF file."""
    result = ValidationResult()
    
    if not path:
        result.add_error("model_path", "Path cannot be empty")
        return result
    
    if not os.path.exists(path):
        result.add_error("model_path", "File does not exist", path)
    elif not path.endswith(".gguf"):
        result.add_error("model_path", "File must be a .gguf model", path)
    elif not os.path.isfile(path):
        result.add_error("model_path", "Path is not a file", path)
    
    return result


def validate_config(config: dict) -> ValidationResult:
    """Validate NPC configuration dictionary."""
    result = ValidationResult()
    
    required = ["npc_name", "role"]
    for field in required:
        if field not in config:
            result.add_error(field, f"Missing required field: {field}")
    
    if "npc_name" in config:
        sub = validate_npc_name(config["npc_name"])
        result.errors.extend(sub.errors)
    
    if "affinity" in config:
        sub = validate_affinity(config["affinity"])
        result.errors.extend(sub.errors)
    
    if "mood" in config:
        sub = validate_mood(config["mood"])
        result.errors.extend(sub.errors)
    
    return result


def sanitize_text(text: str) -> str:
    """Sanitize text input for safe processing."""
    if not text:
        return ""
    
    # Remove null bytes
    text = text.replace("\x00", "")
    
    # Normalize whitespace
    text = " ".join(text.split())
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text


def clamp_affinity(value: float) -> float:
    """Clamp affinity to valid range."""
    return max(-1.0, min(1.0, float(value)))
