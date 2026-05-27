from domainhunter.score import score_name


def test_scores_are_bounded(markov):
    for name in ["velk", "mira", "xqzzt", "a", "supercalifragilistic"]:
        value, _ = score_name(name, markov)
        assert 0.0 <= value <= 1.0


def test_real_word_beats_consonant_soup(markov):
    good, _ = score_name("mira", markov)
    bad, _ = score_name("xqzzt", markov)
    assert good > bad


def test_digits_penalize_clean_signal(markov):
    _, clean = score_name("nova", markov)
    _, dirty = score_name("nov4", markov)
    assert clean["clean"] == 1.0
    assert dirty["clean"] < 1.0


def test_no_vowels_zeroes_vowel_balance(markov):
    _, b = score_name("bcdfg", markov)
    assert b["vowel_balance"] == 0.0


def test_known_words_lift_score(markov):
    # Same name, only the known-word set differs → meaning bonus must raise the score.
    with_known, b = score_name("starfox", markov, frozenset({"star", "fox"}))
    without, _ = score_name("starfox", markov, None)
    assert b["meaning"] == 1.0
    assert with_known > without


def test_short_beats_long(markov):
    short, _ = score_name("velk", markov)
    long_, _ = score_name("heatherflame", markov)
    assert short > long_
