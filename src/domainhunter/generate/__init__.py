from __future__ import annotations

import random
from functools import lru_cache

from ..config import Config
from ..models import Candidate
from ..wordlists import load_adjectives, load_markov_corpus, load_nouns
from . import brandable, leet, seeds as seeds_gen, words as words_gen
from .markov import Markov


@lru_cache(maxsize=1)
def build_markov() -> Markov:
    # Cached: training is ~1-2s, and a loop run calls this once per round.
    m = Markov(order=3)
    m.train(load_markov_corpus())
    return m


def generate_all(
    config: Config,
    markov: Markov | None = None,
    rng: random.Random | None = None,
) -> list[Candidate]:
    rng = rng or random.Random()
    markov = markov or build_markov()
    adjs = list(load_adjectives())
    nouns = list(load_nouns())

    enabled = list(dict.fromkeys(config.strategies))
    # Favor short producers (brandable inventions, leet fragments) — short wins.
    # `words` makes longer compounds, so it gets the smallest share.
    weights = {"brandable": 0.40, "leet": 0.25, "words": 0.20, "seeds": 0.15}
    total_w = sum(weights.get(s, 0.25) for s in enabled) or 1.0

    def share(strategy: str) -> int:
        return max(1, int(config.target_pool * weights.get(strategy, 0.25) / total_w))

    out: list[Candidate] = []
    if "brandable" in enabled:
        out += brandable.generate(share("brandable"), markov, rng, config.min_len, config.max_len)
    if "words" in enabled:
        out += words_gen.generate(share("words"), adjs, nouns, rng, config.min_len, config.max_len)
    if "seeds" in enabled:
        out += seeds_gen.generate(config.seeds, share("seeds"), rng, config.min_len, config.max_len)
    if "leet" in enabled:
        out += leet.generate(share("leet"), adjs + nouns, rng, config.min_len, config.max_len)

    return out
