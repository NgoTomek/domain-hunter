from __future__ import annotations

import re

_CONS_RUN = re.compile(r"[^aeiou]+")
_VOWELS = set("aeiou")


def _meaning(name: str, known) -> float:
    """1.0 = real word / clean compound, 0.75 = contains a real word, 0.5 = neither."""
    if not known:
        return 0.5
    if name in known:
        return 1.0
    n = len(name)
    for i in range(3, n - 2):
        if name[:i] in known and name[i:] in known:
            return 1.0
    for k in range(4, n):
        if name[:k] in known or name[n - k:] in known:
            return 0.75
    return 0.5


def score_name(name: str, markov, known=None, min_len: int = 3, max_len: int = 12) -> tuple[float, dict]:
    """0..1 'coolness' — SHORT is the dominant signal (short names read best).

    A pronounceability gate keeps consonant-soup out; well-formedness and a small
    real-word bonus break ties. Long compounds sink; short fragments/inventions win.
    """
    w = name.lower()
    L = len(w) or 1

    # --- shortness: the dominant driver ---
    if L <= 5:
        short = 1.00
    elif L == 6:
        short = 0.90
    elif L == 7:
        short = 0.76
    elif L == 8:
        short = 0.60
    elif L == 9:
        short = 0.46
    elif L == 10:
        short = 0.34
    else:
        short = max(0.08, 0.34 - (L - 10) * 0.05)

    # --- well-formedness: keep junk out (harsh clusters, no vowels, digits/hyphens) ---
    run = max((len(r) for r in _CONS_RUN.findall(w)), default=0)
    cluster = 1.0 if run <= 2 else (0.5 if run == 3 else 0.2)
    clean = 1.0 - (0.4 if any(c.isdigit() for c in w) else 0.0) - (0.3 if "-" in w else 0.0)
    clean = max(0.0, clean)
    n_vowels = sum(1 for ch in w if ch in _VOWELS)
    ratio = n_vowels / L
    if n_vowels == 0:
        vowel = 0.0
    elif 0.25 <= ratio <= 0.60:
        vowel = 1.0
    elif 0.15 <= ratio < 0.25 or 0.60 < ratio <= 0.75:
        vowel = 0.60
    else:
        vowel = 0.30
    wellformed = 0.4 * cluster + 0.3 * clean + 0.3 * vowel

    # --- pronounceability gate (consonant soup → heavy discount) ---
    pron = markov.score01(w)
    gate = 0.35 + 0.65 * pron

    meaning = _meaning(w, known)

    coolness = (0.62 * short + 0.23 * wellformed + 0.15 * meaning) * gate
    breakdown = {
        "short": round(short, 3),
        "pronounceable": round(pron, 3),
        "clusters": round(cluster, 3),
        "clean": round(clean, 3),
        "vowel_balance": round(vowel, 3),
        "wellformed": round(wellformed, 3),
        "meaning": round(meaning, 3),
    }
    return max(0.0, min(1.0, coolness)), breakdown
