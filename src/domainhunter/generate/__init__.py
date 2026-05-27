from __future__ import annotations

import random

from ..config import Config
from ..models import Candidate
from ..wordlists import load_adjectives, load_markov_corpus, load_nouns
from . import brandable, leet, seeds as seeds_gen, words as words_gen
from .markov import Markov


def build_markov() -> Markov:
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
    share = max(1, config.target_pool // max(1, len(enabled)))
    out: list[Candidate] = []

    if "brandable" in enabled:
        out += brandable.generate(share, markov, rng, config.min_len, config.max_len)
    if "words" in enabled:
        out += words_gen.generate(share, adjs, nouns, rng, config.min_len, config.max_len)
    if "seeds" in enabled:
        out += seeds_gen.generate(config.seeds, share, rng, config.min_len, config.max_len)
    if "leet" in enabled:
        out += leet.generate(share, adjs + nouns, rng, config.min_len, config.max_len)

    return out
