from __future__ import annotations

from typing import Optional

# How desirable each TLD is, independent of price. This drives ranking so the
# leaderboard reflects NAME + TLD quality — not "whatever is cheapest" (which is
# what made .xyz dominate every result).
TLD_DESIRABILITY = {
    ".com": 1.00,
    ".io": 0.95,
    ".co": 0.90,
    ".ai": 0.90,
    ".app": 0.85,
    ".dev": 0.85,
    ".me": 0.82,
    ".sh": 0.72,
    ".xyz": 0.72,
}


def final_score(
    coolness: float,
    available: bool,
    price: Optional[float],
    premium: bool,
    budget: float,
    tld: str = "",
) -> float:
    """Rank by NAME quality × TLD desirability. Price is a FILTER, not a booster.

    Within budget, a cheaper TLD does not rank higher (that is exactly what made
    .xyz win everything). Registry-premium pricing and over-budget cost sink a
    result hard; unavailable is -1.
    """
    if not available:
        return -1.0
    score = coolness * TLD_DESIRABILITY.get(tld, 0.78)
    if premium:
        score *= 0.05
    if price is not None and budget > 0 and price > budget:
        score *= max(0.05, budget / price)
    return score
