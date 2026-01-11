from __future__ import annotations

import json, os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

@dataclass
class Turn:
    role: Literal["user","assistant"]
    content: str
    time: str

class ConversationMemory:
    def __init__(self, path: str):
        self.path = path
        self.turns: List[Turn] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.turns = [Turn(**t) for t in raw]
        except Exception:
            self.turns = []

    def _save(self) -> None:
        data = [t.__dict__ for t in self.turns]
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add(self, role: Literal["user","assistant"], content: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.turns.append(Turn(role=role, content=content, time=ts))
        self._save()

    def last_n(self, n: int) -> List[Turn]:
        return self.turns[-n:] if n > 0 else []

@dataclass
class Fact:
    text: str
    tags: List[str]
    time: str
    salience: float  # 0..1

class FactsStore:
    def __init__(self, path: str):
        self.path = path
        self.facts: List[Fact] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.facts = [Fact(**x) for x in raw]
        except Exception:
            self.facts = []

    def _save(self) -> None:
        data = [f.__dict__ for f in self.facts]
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def add_fact(self, text: str, tags: List[str], salience: float) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        s = max(0.0, min(1.0, salience))
        self.facts.append(Fact(text=text, tags=tags, time=ts, salience=s))
        self._save()

    def wipe(self) -> None:
        self.facts = []
        if os.path.exists(self.path):
            os.remove(self.path)

def select_facts(store: FactsStore, want_tags: List[str], k: int = 3) -> List[str]:
    if not store or not store.facts:
        return []
    want = set(want_tags or [])

    def score(f: Fact) -> float:
        overlap = len(want.intersection(set(f.tags))) if want else 0
        return (0.65 * f.salience) + (0.35 * min(1.0, overlap / 2.0))

    ranked = sorted(store.facts, key=score, reverse=True)
    out: List[str] = []
    for f in ranked:
        if f.text not in out:
            out.append(f.text)
        if len(out) >= k:
            break
    return out
