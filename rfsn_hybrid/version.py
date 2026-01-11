"""
Version management and compatibility checking.

Ensures all system components are compatible before running.
Prevents "mixed parts" installs that cause undefined behavior.
"""
from __future__ import annotations

import os
import sys
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Find version.json relative to this file or repo root
_THIS_DIR = Path(__file__).parent
_VERSION_FILE_CANDIDATES = [
    _THIS_DIR.parent / "version.json",  # repo root
    _THIS_DIR / "version.json",          # in package
    Path("version.json"),                 # cwd
]


@dataclass
class VersionInfo:
    """Version and compatibility information."""
    version: str
    abi: int
    min_python: str
    components: Dict[str, str]
    
    @classmethod
    def load(cls, path: Optional[str] = None) -> Optional["VersionInfo"]:
        """Load version info from JSON file."""
        if path:
            candidates = [Path(path)]
        else:
            candidates = _VERSION_FILE_CANDIDATES
        
        for candidate in candidates:
            if candidate.exists():
                try:
                    with open(candidate, "r") as f:
                        data = json.load(f)
                    return cls(
                        version=data.get("version", "0.0.0"),
                        abi=data.get("abi", 0),
                        min_python=data.get("min_python", "3.9"),
                        components=data.get("components", {}),
                    )
                except Exception as e:
                    logger.warning(f"Failed to load version from {candidate}: {e}")
        
        return None


class VersionMismatchError(Exception):
    """Raised when component versions are incompatible."""
    pass


def get_version() -> str:
    """Get the current version string."""
    info = VersionInfo.load()
    return info.version if info else "0.0.0"


def get_abi() -> int:
    """Get the current ABI version."""
    info = VersionInfo.load()
    return info.abi if info else 0


def check_python_version() -> Tuple[bool, str]:
    """
    Check if Python version meets minimum requirements.
    
    Returns:
        (is_compatible, message)
    """
    info = VersionInfo.load()
    if not info:
        return True, "No version info found, skipping Python check"
    
    min_parts = [int(x) for x in info.min_python.split(".")]
    current_parts = [sys.version_info.major, sys.version_info.minor]
    
    if current_parts < min_parts:
        return False, (
            f"Python {info.min_python}+ required, "
            f"but running {sys.version_info.major}.{sys.version_info.minor}"
        )
    
    return True, f"Python {sys.version_info.major}.{sys.version_info.minor} OK"


def check_component_version(
    component: str,
    reported_version: str,
) -> Tuple[bool, str]:
    """
    Check if a component's reported version matches expected.
    
    Args:
        component: Component name (e.g., "engine", "state_machine")
        reported_version: Version reported by the component
        
    Returns:
        (is_compatible, message)
    """
    info = VersionInfo.load()
    if not info:
        return True, "No version info, skipping check"
    
    expected = info.components.get(component)
    if not expected:
        return True, f"No version constraint for {component}"
    
    if reported_version != expected:
        return False, (
            f"Component {component} version mismatch: "
            f"expected {expected}, got {reported_version}"
        )
    
    return True, f"Component {component} v{reported_version} OK"


def check_abi_compatibility(reported_abi: int) -> Tuple[bool, str]:
    """
    Check if ABI versions match.
    
    Args:
        reported_abi: ABI version from external component
        
    Returns:
        (is_compatible, message)
    """
    info = VersionInfo.load()
    if not info:
        return True, "No version info, skipping ABI check"
    
    if reported_abi != info.abi:
        return False, (
            f"ABI mismatch: expected {info.abi}, got {reported_abi}. "
            f"Components are incompatible."
        )
    
    return True, f"ABI {reported_abi} OK"


def enforce_version_compatibility(
    check_python: bool = True,
    external_abi: Optional[int] = None,
    components: Optional[Dict[str, str]] = None,
) -> None:
    """
    Enforce version compatibility or raise error.
    
    This is the main entry point for version checking.
    Call at system startup to prevent mixed-version runs.
    
    Args:
        check_python: Whether to verify Python version
        external_abi: ABI reported by external component (e.g., SKSE plugin)
        components: Dict of component_name -> reported_version
        
    Raises:
        VersionMismatchError: If any version check fails
    """
    errors = []
    
    # Check Python version
    if check_python:
        ok, msg = check_python_version()
        if not ok:
            errors.append(msg)
        else:
            logger.debug(msg)
    
    # Check ABI
    if external_abi is not None:
        ok, msg = check_abi_compatibility(external_abi)
        if not ok:
            errors.append(msg)
        else:
            logger.debug(msg)
    
    # Check components
    if components:
        for name, version in components.items():
            ok, msg = check_component_version(name, version)
            if not ok:
                errors.append(msg)
            else:
                logger.debug(msg)
    
    if errors:
        error_msg = "VERSION MISMATCH - System disabled:\n" + "\n".join(f"  • {e}" for e in errors)
        logger.error(error_msg)
        raise VersionMismatchError(error_msg)
    
    info = VersionInfo.load()
    if info:
        logger.info(f"Version check passed: v{info.version} (ABI {info.abi})")


# Expose version at module level for easy access
__version__ = get_version()
