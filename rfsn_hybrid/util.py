from __future__ import annotations

def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x
