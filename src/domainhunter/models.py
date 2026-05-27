from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Candidate:
    """A generated name (label without TLD) plus its coolness score."""

    name: str
    strategy: str
    coolness: float = 0.0
    breakdown: dict = field(default_factory=dict)


@dataclass
class RankedDomain:
    """A fully-evaluated domain: availability + price + final rank score."""

    domain: str
    name: str
    tld: str
    coolness: float
    available: bool
    price: Optional[float]
    renewal: Optional[float]
    premium: bool
    score: float
    strategy: str
    status: str  # available | premium | taken | unknown | error
    source: str  # dns | rdap-404 | whois-* | porkbun | *+cache
