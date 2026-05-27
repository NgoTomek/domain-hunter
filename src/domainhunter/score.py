from __future__ import annotations

import re

_CONS_RUN = re.compile(r"[^aeiou]+")
_VOWELS = set("aeiou")


def score_name(name: str, markov, min_len: int = 3, max_len: int = 12) -> tuple[float, dict]:
    """Cheap, deterministic 0..1 'coolness' with a per-signal breakdown.

    Two halves combined by a (pronounceability-leaning) weighted geometric mean,
    so a name that is structurally fine but unpronounceable — or pronounceable
    but malformed — still scores low. Consonant soup tanks; short real-ish
    brandables float to the top.
    """
    w = name.lower()
    L = len(w) or 1

    # --- structure: is this a well-formed short token? (additive) ---
    if L <= 2:
        length = 0.30
    elif L <= 7:
        length = 1.0 - abs(L - 5) * 0.06
    elif L <= 10:
        length = 0.70 - (L - 7) * 0.10
    else:
        length = max(0.10, 0.40 - (L - 10) * 0.05)

    run = max((len(r) for r in _CONS_RUN.findall(w)), default=0)
    cluster = 1.0 if run <= 2 else (0.55 if run == 3 else 0.20)

    clean = 1.0
    if any(ch.isdigit() for ch in w):
        clean -= 0.40
    if "-" in w:
        clean -= 0.30
    clean = max(0.0, clean)

    n_vowels = sum(1 for ch in w if ch in _VOWELS)
    ratio = n_vowels / L
    if n_vowels == 0:
        vowel = 0.0
    elif 0.25 <= ratio <= 0.60:
        vowel = 1.0
    elif 0.15 <= ratio < 0.25 or 0.60 < ratio <= 0.75:
        vowel = 0.55
    else:
        vowel = 0.25

    structure = 0.30 * length + 0.25 * cluster + 0.20 * clean + 0.25 * vowel
    structure = max(0.0, min(1.0, structure))

    # --- pronounceability: does this look like a real word? ---
    pron = markov.score01(w)

    coolness = (pron ** 0.55) * (structure ** 0.45)
    breakdown = {
        "length": round(length, 3),
        "pronounceable": round(pron, 3),
        "clusters": round(cluster, 3),
        "clean": round(clean, 3),
        "vowel_balance": round(vowel, 3),
        "structure": round(structure, 3),
    }
    return max(0.0, min(1.0, coolness)), breakdown
