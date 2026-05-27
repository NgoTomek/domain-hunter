from domainhunter.rank import final_score


def test_taken_is_negative():
    assert final_score(0.9, False, 10.0, False, 30.0, ".com") == -1.0


def test_premium_sinks_below_normal():
    normal = final_score(0.9, True, 10.0, False, 30.0, ".com")
    premium = final_score(0.9, True, 10.0, True, 30.0, ".com")
    assert premium < normal


def test_price_within_budget_does_not_change_rank():
    # The whole point of the rethink: a cheaper TLD must NOT outrank a pricier one
    # just for being cheap (that made .xyz dominate). Same coolness + TLD → equal.
    cheap = final_score(0.9, True, 2.0, False, 30.0, ".xyz")
    pricey = final_score(0.9, True, 25.0, False, 30.0, ".xyz")
    assert cheap == pricey


def test_better_tld_ranks_higher():
    com = final_score(0.9, True, 11.0, False, 30.0, ".com")
    xyz = final_score(0.9, True, 2.0, False, 30.0, ".xyz")
    assert com > xyz  # .com beats cheaper .xyz for the same name


def test_over_budget_is_penalized():
    within = final_score(0.9, True, 20.0, False, 30.0, ".com")
    over = final_score(0.9, True, 300.0, False, 30.0, ".com")
    assert over < within
