from __future__ import annotations


def final_score(coolness: float, available: bool, price=None, premium: bool = False,
                budget: float = 0.0, tld: str = "") -> float:
    """Rank purely by the NAME's coolness — price and TLD are ignored (user's choice).

    Registry-premium 'traps' still sink (they're a different, pricey beast);
    unavailable is -1 so it sorts to the bottom.
    """
    if not available:
        return -1.0
    if premium:
        return coolness * 0.05
    return coolness
