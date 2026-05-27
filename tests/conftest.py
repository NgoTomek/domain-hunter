import pytest

from domainhunter.generate.markov import Markov

# A small, fixed corpus → deterministic, network-free Markov model for tests.
_CORPUS = [
    "nova", "flux", "echo", "drift", "forge", "lumen", "vale", "mira", "velk", "river",
    "stone", "light", "cloud", "storm", "spark", "ember", "atlas", "prism", "crystal",
    "harbor", "beacon", "lunar", "solar", "swift", "vivid", "prime", "noble", "royal",
    "amber", "coral", "raven", "falcon", "maple", "cedar", "willow", "aspen", "copper",
    "cobalt", "photon", "vector", "matrix", "signal", "orbit", "comet", "zephyr", "gale",
    "glacier", "canyon", "delta", "ridge", "summit", "meadow", "tundra", "oasis",
]


@pytest.fixture(scope="session")
def markov():
    return Markov(order=3).train(_CORPUS)
