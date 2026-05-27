from domainhunter.pricing.porkbun import Porkbun, parse_check

TAKEN = {"status": "SUCCESS", "response": {
    "avail": "no", "price": "11.08", "regularPrice": "11.08", "premium": "no",
    "additional": {"renewal": {"price": "11.08"}}}}
AVAILABLE = {"status": "SUCCESS", "response": {
    "avail": "yes", "price": "11.08", "regularPrice": "11.08", "premium": "no",
    "additional": {"renewal": {"price": "11.08"}}}}
PREMIUM = {"status": "SUCCESS", "response": {
    "avail": "yes", "price": "174.10", "regularPrice": "174.10", "premium": "yes",
    "additional": {"renewal": {"price": "174.10"}}}}


def test_parse_taken():
    p = parse_check(TAKEN)
    assert p["available"] is False
    assert p["price"] == 11.08
    assert p["premium"] is False


def test_parse_available():
    p = parse_check(AVAILABLE)
    assert p["available"] is True
    assert p["premium"] is False
    assert p["renewal"] == 11.08


def test_parse_premium_trap():
    p = parse_check(PREMIUM)
    assert p["available"] is True
    assert p["premium"] is True
    assert p["price"] == 174.10


def test_base_price_lookup():
    pricing = {
        "com": {"registration": "11.08", "renewal": "11.08"},
        "io": {"registration": "28.12", "renewal": "51.80"},
    }
    assert Porkbun.base_price(pricing, ".com") == (11.08, 11.08)
    assert Porkbun.base_price(pricing, "io") == (28.12, 51.80)
    assert Porkbun.base_price(pricing, ".zzz") == (None, None)
