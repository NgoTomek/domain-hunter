from __future__ import annotations

import random

from ..models import Candidate

PREFIXES = ["get", "try", "use", "go", "my", "neo", "meta", "join", "with", "hey"]
SUFFIXES = ["ly", "ify", "io", "hub", "labs", "ai", "app", "ist", "ster", "kit",
            "base", "able", "r", "ful", "wise", "loop", "flow", "ado", "ora", "yx"]
VOWELS = set("aeiou")


def _blend(a: str, b: str) -> str:
    """Portmanteau: first part of a up to its last vowel + tail of b from its first vowel."""
    cut_a = max((i for i, ch in enumerate(a) if ch in VOWELS), default=len(a) // 2)
    cut_b = next((i for i, ch in enumerate(b) if ch in VOWELS), len(b) // 2)
    return a[: cut_a + 1] + b[cut_b:]


def generate(
    seeds: list[str],
    n: int,
    rng: random.Random,
    min_len: int = 3,
    max_len: int = 14,
) -> list[Candidate]:
    seeds = [s.lower() for s in seeds if s.isalpha()]
    if not seeds:
        return []

    out: list[Candidate] = []
    seen: set[str] = set()

    def add(w: str) -> None:
        w = w.lower()
        if min_len <= len(w) <= max_len and w not in seen and w.isalpha():
            seen.add(w)
            out.append(Candidate(name=w, strategy="seeds"))

    # Deterministic affix attachments first.
    for s in seeds:
        for suf in SUFFIXES:
            add(s + suf)
        for pre in PREFIXES:
            add(pre + s)

    # Then random blends between seeds.
    guard = 0
    while len(out) < n and guard < n * 40:
        guard += 1
        a, b = rng.choice(seeds), rng.choice(seeds)
        if a != b:
            add(_blend(a, b))
        else:
            add(a + rng.choice(SUFFIXES))

    return out[:n]
