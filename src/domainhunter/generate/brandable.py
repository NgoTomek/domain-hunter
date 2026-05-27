from __future__ import annotations

import random

from ..models import Candidate
from .markov import Markov

# Consonants/vowels weighted by repetition so common, smooth letters dominate.
CONS = "tttnnnsssrrrlllcccdddmmmpppbbggffvkhwz"
VOWELS = "aaaeeeiiioou"
PATTERNS = ["CVCV", "CVCVC", "CVCCV", "CCVCV", "VCVC", "CVVC", "CVCVCV", "CVC", "CVCVCVC"]


def _fill(pattern: str, rng: random.Random) -> str:
    return "".join(rng.choice(VOWELS if ch == "V" else CONS) for ch in pattern)


def generate(
    n: int,
    markov: Markov,
    rng: random.Random,
    min_len: int = 3,
    max_len: int = 8,
) -> list[Candidate]:
    """Over-generate invented words two ways, then keep the most pronounceable n."""
    upper = min(max_len, 9)
    pool: set[str] = set()
    target = n * 8

    # Source 1: phonotactic pattern fills.
    guard = 0
    while len(pool) < target and guard < target * 25:
        guard += 1
        w = _fill(rng.choice(PATTERNS), rng)
        if min_len <= len(w) <= upper:
            pool.add(w)

    # Source 2: sampled straight from the Markov model (more natural-sounding).
    for _ in range(target):
        w = markov.generate(rng, max(4, min_len), upper)
        if w and min_len <= len(w) <= upper:
            pool.add(w)

    ranked = sorted(pool, key=markov.score01, reverse=True)
    return [Candidate(name=w, strategy="brandable") for w in ranked[:n]]
