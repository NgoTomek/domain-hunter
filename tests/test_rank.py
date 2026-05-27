from domainhunter.rank import final_score


def test_taken_is_negative():
    assert final_score(0.9, False, 10.0, False, 30.0) == -1.0


def test_premium_sinks_below_normal():
    normal = final_score(0.9, True, 10.0, False, 30.0)
    premium = final_score(0.9, True, 10.0, True, 30.0)
    assert premium < normal


def test_cheaper_ranks_higher():
    cheap = final_score(0.9, True, 5.0, False, 30.0)
    pricey = final_score(0.9, True, 25.0, False, 30.0)
    assert cheap > pricey


def test_over_budget_is_penalized():
    within = final_score(0.9, True, 20.0, False, 30.0)
    over = final_score(0.9, True, 300.0, False, 30.0)
    assert over < within
