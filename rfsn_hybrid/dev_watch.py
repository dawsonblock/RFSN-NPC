from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass
from typing import Dict, List

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

@dataclass
class FileSig:
    mtime_ns: int
    size: int
    sha256: str

class DevWatch:
    """Cheap, dependency-free edit detection for .py files."""

    def __init__(self, roots: List[str], include_regex: str = r".*\.py$"):
        import re
        self._re = re.compile(include_regex)
        self.roots = roots
        self.baseline: Dict[str, FileSig] = self.snapshot()

    def _iter_files(self) -> List[str]:
        out: List[str] = []
        for root in self.roots:
            if not root or not os.path.exists(root):
                continue
            if os.path.isfile(root):
                if self._re.match(root):
                    out.append(root)
                continue
            for d, _, files in os.walk(root):
                for fn in files:
                    p = os.path.join(d, fn)
                    if self._re.match(p):
                        out.append(p)
        return sorted(set(out))

    def snapshot(self) -> Dict[str, FileSig]:
        sigs: Dict[str, FileSig] = {}
        for p in self._iter_files():
            try:
                st = os.stat(p)
                sigs[p] = FileSig(
                    mtime_ns=st.st_mtime_ns,
                    size=st.st_size,
                    sha256=_sha256_file(p),
                )
            except FileNotFoundError:
                continue
        return sigs

    def check(self) -> List[str]:
        current = self.snapshot()
        changed: List[str] = []
        for p, sig in current.items():
            old = self.baseline.get(p)
            if old is None or (old.mtime_ns != sig.mtime_ns) or (old.size != sig.size) or (old.sha256 != sig.sha256):
                changed.append(p)
        for p in self.baseline.keys():
            if p not in current:
                changed.append(p)
        return sorted(set(changed))

    def commit(self) -> None:
        self.baseline = self.snapshot()
