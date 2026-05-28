from domainhunter.rank import final_score


def test_taken_is_negative():
    assert final_score(0.9, False, 10.0, False, 30.0, ".com") == -1.0


def test_premium_sinks_below_normal():
    assert final_score(0.9, True, 10.0, True) < final_score(0.9, True, 10.0, False)


def test_ranks_by_coolness_only():
    # price and TLD are ignored — same coolness ⇒ same score
    assert final_score(0.9, True, 2.0, False, 30.0, ".xyz") == final_score(0.9, True, 28.0, False, 30.0, ".io")
    # a cooler name beats a less-cool one regardless of price
    assert final_score(0.95, True, 99.0, False) > final_score(0.80, True, 2.0, False)
