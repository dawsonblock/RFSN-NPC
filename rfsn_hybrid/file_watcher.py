"""
File change detection for hot reload safety.

Detects when Python files, configs, or scripts change
and triggers a controlled response (shutdown or disable).

This prevents undefined behavior from code changes during runtime.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class FileSnapshot:
    """Snapshot of a file's state."""
    path: str
    hash: str
    size: int
    mtime: float
    
    @classmethod
    def from_path(cls, path: str) -> Optional["FileSnapshot"]:
        """Create snapshot from file path."""
        try:
            p = Path(path)
            if not p.exists():
                return None
            
            stat = p.stat()
            
            # Compute hash
            with open(p, "rb") as f:
                content = f.read()
                hash_val = hashlib.sha256(content).hexdigest()
            
            return cls(
                path=str(p.absolute()),
                hash=hash_val,
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
        except Exception as e:
            logger.warning(f"Failed to snapshot {path}: {e}")
            return None


@dataclass
class ChangeEvent:
    """Record of a detected file change."""
    path: str
    change_type: str  # "modified", "added", "removed"
    old_hash: Optional[str]
    new_hash: Optional[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class FileWatcher:
    """
    Watches files for changes and triggers callbacks.
    
    Use to detect script edits and react safely:
    - Log the change
    - Disable features
    - Trigger shutdown
    
    Example:
        >>> watcher = FileWatcher()
        >>> watcher.add_directory("rfsn_hybrid/", patterns=["*.py"])
        >>> watcher.add_file("version.json")
        >>> watcher.start()
        >>> # Changes trigger on_change callback
    """
    
    def __init__(
        self,
        check_interval: float = 2.0,
        on_change: Optional[Callable[[List[ChangeEvent]], None]] = None,
    ):
        """
        Initialize file watcher.
        
        Args:
            check_interval: Seconds between checks
            on_change: Callback for detected changes
        """
        self.check_interval = check_interval
        self.on_change = on_change
        
        self._snapshots: Dict[str, FileSnapshot] = {}
        self._watched_dirs: List[tuple[str, List[str]]] = []  # (dir, patterns)
        self._watched_files: Set[str] = set()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # History
        self._changes: List[ChangeEvent] = []
    
    def add_file(self, path: str) -> None:
        """Add a single file to watch."""
        abs_path = str(Path(path).absolute())
        with self._lock:
            self._watched_files.add(abs_path)
            snapshot = FileSnapshot.from_path(abs_path)
            if snapshot:
                self._snapshots[abs_path] = snapshot
    
    def add_directory(
        self,
        directory: str,
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
    ) -> None:
        """
        Add a directory to watch.
        
        Args:
            directory: Directory path
            patterns: Glob patterns to match (e.g., ["*.py", "*.yaml"])
            recursive: Whether to watch subdirectories
        """
        patterns = patterns or ["*"]
        abs_dir = str(Path(directory).absolute())
        
        with self._lock:
            self._watched_dirs.append((abs_dir, patterns))
            
            # Take initial snapshots
            self._scan_directory(abs_dir, patterns, recursive)
    
    def _scan_directory(
        self,
        directory: str,
        patterns: List[str],
        recursive: bool,
    ) -> None:
        """Scan directory and create snapshots."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return
        
        import fnmatch
        
        for root, dirs, files in os.walk(directory):
            # Skip __pycache__ and hidden directories
            dirs[:] = [d for d in dirs if not d.startswith((".", "__"))]
            
            for filename in files:
                if any(fnmatch.fnmatch(filename, p) for p in patterns):
                    full_path = os.path.join(root, filename)
                    snapshot = FileSnapshot.from_path(full_path)
                    if snapshot:
                        self._snapshots[full_path] = snapshot
            
            if not recursive:
                break
    
    def start(self) -> None:
        """Start watching for changes."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="FileWatcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"FileWatcher started, watching {len(self._snapshots)} files")
    
    def stop(self) -> None:
        """Stop watching."""
        if not self._running:
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._running = False
        logger.info("FileWatcher stopped")
    
    def _watch_loop(self) -> None:
        """Main watch loop."""
        while not self._stop_event.is_set():
            try:
                changes = self._check_for_changes()
                if changes:
                    self._handle_changes(changes)
            except Exception as e:
                logger.error(f"FileWatcher error: {e}")
            
            self._stop_event.wait(self.check_interval)
    
    def _check_for_changes(self) -> List[ChangeEvent]:
        """Check all watched files for changes."""
        changes = []
        
        with self._lock:
            paths_to_check = set(self._snapshots.keys())
            
            # Also check for new files in watched directories
            for dir_path, patterns in self._watched_dirs:
                self._scan_directory(dir_path, patterns, recursive=True)
            
            for path in paths_to_check:
                old_snapshot = self._snapshots.get(path)
                new_snapshot = FileSnapshot.from_path(path)
                
                if old_snapshot and not new_snapshot:
                    # File removed
                    changes.append(ChangeEvent(
                        path=path,
                        change_type="removed",
                        old_hash=old_snapshot.hash,
                        new_hash=None,
                    ))
                    del self._snapshots[path]
                    
                elif old_snapshot and new_snapshot:
                    if old_snapshot.hash != new_snapshot.hash:
                        # File modified
                        changes.append(ChangeEvent(
                            path=path,
                            change_type="modified",
                            old_hash=old_snapshot.hash,
                            new_hash=new_snapshot.hash,
                        ))
                        self._snapshots[path] = new_snapshot
                        
                elif not old_snapshot and new_snapshot:
                    # File added
                    changes.append(ChangeEvent(
                        path=path,
                        change_type="added",
                        old_hash=None,
                        new_hash=new_snapshot.hash,
                    ))
                    self._snapshots[path] = new_snapshot
        
        return changes
    
    def _handle_changes(self, changes: List[ChangeEvent]) -> None:
        """Handle detected changes."""
        for change in changes:
            self._changes.append(change)
            filename = os.path.basename(change.path)
            logger.warning(
                f"FILE CHANGED: {filename} ({change.change_type})"
            )
        
        logger.warning(
            f"HOT RELOAD NOT SUPPORTED: {len(changes)} files changed. "
            "System should be restarted."
        )
        
        if self.on_change:
            try:
                self.on_change(changes)
            except Exception as e:
                logger.error(f"Change callback failed: {e}")
    
    def get_changes(self) -> List[ChangeEvent]:
        """Get history of detected changes."""
        with self._lock:
            return list(self._changes)
    
    def get_watched_files(self) -> List[str]:
        """Get list of watched files."""
        with self._lock:
            return list(self._snapshots.keys())
    
    def get_file_hash(self, path: str) -> Optional[str]:
        """Get current hash for a file."""
        with self._lock:
            snapshot = self._snapshots.get(path)
            return snapshot.hash if snapshot else None


def create_watcher_for_project(
    project_dir: str,
    on_change: Optional[Callable[[List[ChangeEvent]], None]] = None,
) -> FileWatcher:
    """
    Create a file watcher configured for this project.
    
    Watches:
    - Python files
    - Config files (yaml, json)
    - Version file
    """
    watcher = FileWatcher(on_change=on_change)
    
    # Watch Python source
    watcher.add_directory(
        os.path.join(project_dir, "rfsn_hybrid"),
        patterns=["*.py"],
    )
    
    # Watch config files
    watcher.add_file(os.path.join(project_dir, "version.json"))
    watcher.add_directory(
        project_dir,
        patterns=["*.yaml", "*.yml", "*.json"],
        recursive=False,
    )
    
    return watcher
