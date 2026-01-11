#!/usr/bin/env python3
"""
Generate build manifest with file hashes.

Creates build_manifest.json containing:
- Version/ABI info
- File paths with SHA256 hashes
- Build timestamp

Run:
    python scripts/generate_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def compute_sha256(path: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_files(
    directory: str,
    patterns: List[str],
    exclude_dirs: Optional[List[str]] = None,
) -> List[str]:
    """Find files matching patterns."""
    import fnmatch
    
    exclude_dirs = exclude_dirs or ["__pycache__", ".git", ".pytest_cache", "venv", ".venv"]
    matches = []
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
        
        for filename in files:
            if any(fnmatch.fnmatch(filename, p) for p in patterns):
                matches.append(os.path.join(root, filename))
    
    return sorted(matches)


def generate_manifest(
    project_dir: str,
    output_path: Optional[str] = None,
) -> Dict:
    """
    Generate build manifest.
    
    Args:
        project_dir: Root directory of the project
        output_path: Where to write manifest (optional)
        
    Returns:
        Manifest dictionary
    """
    project_dir = os.path.abspath(project_dir)
    
    # Load version info
    version_path = os.path.join(project_dir, "version.json")
    version_info = {}
    if os.path.exists(version_path):
        with open(version_path) as f:
            version_info = json.load(f)
    
    # Find and hash files
    python_files = find_files(
        os.path.join(project_dir, "rfsn_hybrid"),
        ["*.py"],
    )
    
    config_files = find_files(
        project_dir,
        ["*.json", "*.yaml", "*.yml", "*.toml"],
        exclude_dirs=["__pycache__", ".git", ".venv", "venv", "tests"],
    )
    
    test_files = find_files(
        os.path.join(project_dir, "tests"),
        ["*.py"],
    )
    
    # Build file manifest
    files = {}
    
    for path in python_files + config_files + test_files:
        rel_path = os.path.relpath(path, project_dir)
        files[rel_path] = {
            "sha256": compute_sha256(path),
            "size": os.path.getsize(path),
        }
    
    manifest = {
        "version": version_info.get("version", "0.0.0"),
        "abi": version_info.get("abi", 0),
        "build_time": datetime.now().isoformat(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "file_count": len(files),
        "files": files,
    }
    
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"Manifest written to {output_path}")
    
    return manifest


def generate_checksums(
    project_dir: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate SHA256SUMS.txt file.
    
    Args:
        project_dir: Root directory
        output_path: Where to write checksums
        
    Returns:
        Checksums as string
    """
    manifest = generate_manifest(project_dir)
    
    lines = []
    for path, info in sorted(manifest["files"].items()):
        lines.append(f"{info['sha256']}  {path}")
    
    content = "\n".join(lines) + "\n"
    
    if output_path:
        with open(output_path, "w") as f:
            f.write(content)
        print(f"Checksums written to {output_path}")
    
    return content


def verify_manifest(
    project_dir: str,
    manifest_path: str,
) -> bool:
    """
    Verify files against manifest.
    
    Args:
        project_dir: Root directory
        manifest_path: Path to manifest file
        
    Returns:
        True if all files match
    """
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    errors = []
    
    for rel_path, expected in manifest["files"].items():
        full_path = os.path.join(project_dir, rel_path)
        
        if not os.path.exists(full_path):
            errors.append(f"MISSING: {rel_path}")
            continue
        
        actual_hash = compute_sha256(full_path)
        if actual_hash != expected["sha256"]:
            errors.append(f"MODIFIED: {rel_path}")
    
    if errors:
        print("VERIFICATION FAILED:")
        for e in errors:
            print(f"  {e}")
        return False
    
    print(f"VERIFIED: {len(manifest['files'])} files match")
    return True


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate build manifest")
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory",
    )
    parser.add_argument(
        "--output",
        default="build_manifest.json",
        help="Output manifest path",
    )
    parser.add_argument(
        "--checksums",
        help="Also generate SHA256SUMS.txt",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify against existing manifest",
    )
    
    args = parser.parse_args()
    
    if args.verify:
        success = verify_manifest(args.project_dir, args.output)
        sys.exit(0 if success else 1)
    
    manifest = generate_manifest(args.project_dir, args.output)
    print(f"Version: {manifest['version']}")
    print(f"Files: {manifest['file_count']}")
    
    if args.checksums:
        generate_checksums(args.project_dir, args.checksums)


if __name__ == "__main__":
    main()
