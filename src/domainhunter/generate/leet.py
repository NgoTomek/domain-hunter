from __future__ import annotations

import random

from ..models import Candidate

# Letter-only swaps (keep results alpha so they stay clean, registerable labels).
SWAPS = {"i": "y", "s": "z", "c": "k", "x": "ks", "ph": "f"}
VOWELS = set("aeiou")


def _drop_vowels(word: str, rng: random.Random) -> str:
    """Drop most interior vowels (flickr/tumblr style); always keep the first char."""
    chars = list(word)
    out = [chars[0]]
    for ch in chars[1:]:
        if ch in VOWELS and rng.random() < 0.7:
            continue
        out.append(ch)
    return "".join(out)


def generate(
    n: int,
    words_pool: list[str],
    rng: random.Random,
    min_len: int = 3,
    max_len: int = 12,
) -> list[Candidate]:
    out: list[Candidate] = []
    seen: set[str] = set()
    pool = [w for w in words_pool if 4 <= len(w) <= max_len]
    rng.shuffle(pool)

    for w in pool:
        if len(out) >= n:
            break
        variants = {_drop_vowels(w, rng)}
        swapped = w
        for src, dst in SWAPS.items():
            swapped = swapped.replace(src, dst)
        variants.add(swapped)
        for v in variants:
            if v != w and min_len <= len(v) <= max_len and v.isalpha() and v not in seen:
                seen.add(v)
                out.append(Candidate(name=v, strategy="leet"))

    return out[:n]
