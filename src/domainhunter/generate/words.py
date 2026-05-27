from __future__ import annotations

import random

from ..models import Candidate


def generate(
    n: int,
    adjectives: list[str],
    nouns: list[str],
    rng: random.Random,
    min_len: int = 3,
    max_len: int = 14,
) -> list[Candidate]:
    """Brandable adjective+noun / noun+noun combos (sampled, not the full cross).

    Deliberately NO standalone dictionary words: single real words are essentially
    all registered, so they'd only waste the availability-check budget. Compounds
    read as brands and actually have a shot at being unregistered.
    """
    out: list[Candidate] = []
    seen: set[str] = set()

    def add(w: str) -> None:
        w = w.lower()
        if min_len <= len(w) <= max_len and w not in seen and w.isalpha():
            seen.add(w)
            out.append(Candidate(name=w, strategy="words"))

    left = adjectives + nouns
    guard = 0
    while len(out) < n and guard < n * 40:
        guard += 1
        a = rng.choice(left)
        b = rng.choice(nouns)
        if a != b:
            add(a + b)

    return out[:n]
