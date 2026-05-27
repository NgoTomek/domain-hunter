from __future__ import annotations

from typing import Optional


def final_score(
    coolness: float,
    available: bool,
    price: Optional[float],
    premium: bool,
    budget: float,
) -> float:
    """Combine coolness with price/availability into a single ranking number.

    Coolness dominates; cheapness nudges; premium + over-budget sink hard.
    """
    if not available:
        return -1.0
    score = coolness
    if premium:
        score *= 0.05
    if price is not None and budget > 0:
        if price <= budget:
            # Under budget: small bonus for being cheaper.
            score *= 1.0 + (budget - price) / budget * 0.25
        else:
            # Over budget: heavy, proportional penalty.
            score *= max(0.05, budget / price)
    return score
