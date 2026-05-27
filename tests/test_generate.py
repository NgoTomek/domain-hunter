import random

from domainhunter.generate import brandable, leet, seeds as seeds_gen, words as words_gen


def test_brandable_outputs_valid(markov):
    out = brandable.generate(20, markov, random.Random(1), 3, 8)
    assert len(out) <= 20
    assert all(c.name.isalpha() for c in out)
    assert all(3 <= len(c.name) <= 8 for c in out)
    assert all(c.strategy == "brandable" for c in out)


def test_words_are_alpha_compounds():
    out = words_gen.generate(30, ["lunar", "solar"], ["fox", "byte", "forge"], random.Random(1), 3, 16)
    assert len(out) > 0
    assert all(c.name.isalpha() and c.strategy == "words" for c in out)


def test_seeds_mutate_seeds():
    out = seeds_gen.generate(["nova", "flux"], 30, random.Random(1), 3, 16)
    assert len(out) > 0
    assert all(c.name.isalpha() and c.strategy == "seeds" for c in out)


def test_seeds_empty_input():
    assert seeds_gen.generate([], 10, random.Random(1)) == []


def test_leet_outputs_valid():
    out = leet.generate(20, ["river", "stone", "cloud", "spark"], random.Random(1), 3, 12)
    assert all(c.name.isalpha() and c.strategy == "leet" for c in out)
    assert all(3 <= len(c.name) <= 12 for c in out)
