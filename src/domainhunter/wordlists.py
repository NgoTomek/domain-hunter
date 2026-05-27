from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

from .config import ROOT

WL_DIR = ROOT / "data" / "wordlists"
SYSTEM_DICT = Path("/usr/share/dict/words")


def _read(name: str) -> list[str]:
    p = WL_DIR / name
    if not p.exists():
        return []
    out: list[str] = []
    for w in p.read_text(encoding="utf-8").split():
        w = w.strip().lower()
        if w.isalpha():
            out.append(w)
    # de-dupe, preserve order
    return list(dict.fromkeys(out))


@lru_cache(maxsize=1)
def load_adjectives() -> tuple[str, ...]:
    return tuple(_read("adjectives.txt"))


@lru_cache(maxsize=1)
def load_nouns() -> tuple[str, ...]:
    return tuple(_read("nouns.txt"))


@lru_cache(maxsize=1)
def load_markov_corpus(limit: int = 18000, seed: int = 7) -> tuple[str, ...]:
    """Bundled cool words + a random sample of the system dictionary for breadth."""
    words: set[str] = set(load_adjectives()) | set(load_nouns())
    if SYSTEM_DICT.exists():
        try:
            raw = SYSTEM_DICT.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            raw = []
        pool = [w.strip().lower() for w in raw]
        pool = [w for w in pool if w.isalpha() and 3 <= len(w) <= 9 and w.isascii()]
        rng = random.Random(seed)
        rng.shuffle(pool)
        words.update(pool[:limit])
    return tuple(words)
