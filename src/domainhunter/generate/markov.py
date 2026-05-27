from __future__ import annotations

import math
import random
from collections import Counter, defaultdict

ALPHA = "abcdefghijklmnopqrstuvwxyz"
START = "^"
END = "$"
_V = len(ALPHA) + 1  # vocabulary for smoothing (+1 for END token)


def _clean(word: str) -> str:
    return "".join(ch for ch in word.lower() if ch in ALPHA)


class Markov:
    """Character n-gram model used for pronounceability scoring + name generation."""

    def __init__(self, order: int = 3):
        self.order = order
        self.counts: dict[str, Counter] = defaultdict(Counter)
        self._totals: dict[str, int] = {}
        self._mid = 0.0
        self._scale = 1.0

    def train(self, words) -> "Markov":
        clean_words: list[str] = []
        for w in words:
            w = _clean(w)
            if len(w) < 2:
                continue
            clean_words.append(w)
            padded = START * self.order + w + END
            for i in range(len(padded) - self.order):
                ctx = padded[i : i + self.order]
                self.counts[ctx][padded[i + self.order]] += 1
        self._totals = {ctx: sum(c.values()) for ctx, c in self.counts.items()}

        # Calibrate the 0..1 mapping between real words (high) and random
        # letter strings (low), so brandable-but-real names land near the top
        # and consonant soup lands near the bottom.
        good = [self._raw_logprob(w) for w in clean_words] or [-5.0]
        mean_good = sum(good) / len(good)
        rngb = random.Random(123)
        bad = [
            self._raw_logprob("".join(rngb.choice(ALPHA) for _ in range(rngb.randint(4, 8))))
            for _ in range(2000)
        ]
        mean_bad = sum(bad) / len(bad)
        self._mid = (mean_good + mean_bad) / 2
        self._scale = max(1e-6, (mean_good - mean_bad) / 4)
        return self

    def _raw_logprob(self, word: str) -> float:
        word = _clean(word)
        if not word:
            return -20.0
        padded = START * self.order + word + END
        total = 0.0
        n = 0
        for i in range(len(padded) - self.order):
            ctx = padded[i : i + self.order]
            nxt = padded[i + self.order]
            c = self.counts.get(ctx)
            if c:
                p = (c.get(nxt, 0) + 1) / (self._totals[ctx] + _V)
            else:
                p = 1.0 / _V
            total += math.log(p)
            n += 1
        return total / max(n, 1)

    def score01(self, word: str) -> float:
        """Per-char log-prob mapped to 0..1 (real-word-like → 1, random → 0)."""
        z = (self._raw_logprob(word) - self._mid) / self._scale
        if z < -50:
            return 0.0
        if z > 50:
            return 1.0
        return 1.0 / (1.0 + math.exp(-z))

    def generate(self, rng: random.Random, min_len: int = 4, max_len: int = 7, attempts: int = 24) -> str:
        target = (min_len + max_len) // 2
        best = ""
        for _ in range(attempts):
            ctx = START * self.order
            out: list[str] = []
            while True:
                c = self.counts.get(ctx)
                if not c:
                    break
                choices = list(c.keys())
                weights = list(c.values())
                nxt = rng.choices(choices, weights=weights)[0]
                if nxt == END:
                    break
                out.append(nxt)
                if len(out) >= max_len:
                    break
                ctx = (ctx + nxt)[-self.order :]
            word = "".join(out)
            if min_len <= len(word) <= max_len:
                return word
            if not best or abs(len(word) - target) < abs(len(best) - target):
                best = word
        return best
