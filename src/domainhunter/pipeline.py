from __future__ import annotations

import asyncio
import random
from typing import Callable, Optional

import httpx

from . import store
from .availability.dns import has_dns_records
from .availability.rdap import load_bootstrap, rdap_check
from .availability.whois import whois_check
from .config import ROOT, Config
from .generate import build_markov, generate_all
from .models import Candidate, RankedDomain
from .pricing.porkbun import Porkbun, parse_check
from .rank import final_score
from .score import score_name
from .wordlists import load_known_words

BOOTSTRAP_CACHE = ROOT / "data" / "rdap_bootstrap.json"
# on_progress(phase_label, done, total)
ProgressCb = Optional[Callable[[str, int, int], None]]


def _split(domain: str) -> tuple[str, str]:
    name, _, tld = domain.partition(".")
    return name, "." + tld


def _weighted_sample(items, weights, k, rng):
    """Weighted sampling without replacement (Efraimidis-Spirakis)."""
    keyed = [(rng.random() ** (1.0 / max(w, 1e-9)), it) for it, w in zip(items, weights)]
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    return [it for _, it in keyed[:k]]


def _porkbun(client: httpx.AsyncClient, config: Config) -> Porkbun | None:
    sk = config.secrets
    if sk.porkbun_api_key and sk.porkbun_secret_key:
        return Porkbun(client, sk.porkbun_api_key, sk.porkbun_secret_key)
    return None


async def _availability(con, client, bootstrap, domain, config, sem_whois, use_dns=True):
    cached = store.get_availability(con, domain, config.cache_ttl_days)
    if cached is not None:
        av = cached["available"]
        return (None if av is None else bool(av)), cached["source"] + "+cache"

    if use_dns:
        try:
            if await has_dns_records(domain) is True:
                store.save_availability(con, domain, False, "dns")
                return False, "dns"
        except Exception:
            pass

    avail, src = await rdap_check(client, domain, bootstrap)
    if avail is None:
        async with sem_whois:  # WHOIS (now only .co) is touchy — throttle it
            avail, src = await whois_check(domain)
    store.save_availability(con, domain, avail, src)
    return avail, src


async def _process(con, client, bootstrap, base_pricing, cand, tld, domain, config, sem_task, sem_whois) -> RankedDomain:
    """Availability (free) + TLD base price. No checkDomain — that's the verify step."""
    async with sem_task:
        # A fresh authoritative price (from a prior verify) wins — already premium-aware.
        cp = store.get_price(con, domain, config.cache_ttl_days)
        if cp is not None:
            av = None if cp["available"] is None else bool(cp["available"])
            prem = bool(cp["premium"])
            score = final_score(cand.coolness, bool(av), cp["price"], prem, config.budget, tld)
            if av is True:
                status = "premium" if prem else "available"
            elif av is False:
                status = "taken"
            else:
                status = "unknown"
            return RankedDomain(domain, cand.name, tld, cand.coolness, bool(av), cp["price"],
                                cp["renewal"], prem, score, cand.strategy, status, "cache")

        avail, src = await _availability(con, client, bootstrap, domain, config, sem_whois)
        reg, renew = Porkbun.base_price(base_pricing, tld)
        if avail is True:
            score = final_score(cand.coolness, True, reg, False, config.budget, tld)
            return RankedDomain(domain, cand.name, tld, cand.coolness, True, reg, renew,
                                False, score, cand.strategy, "available", src)
        status = "taken" if avail is False else "unknown"
        return RankedDomain(domain, cand.name, tld, cand.coolness,
                            bool(avail) if avail is not None else False,
                            None, None, False, -1.0, cand.strategy, status, src)


async def _verify(results, porkbun, con, config, n, on_progress: ProgressCb = None) -> None:
    """Authoritatively re-price the top N available gems (premium-aware, ~10s each)."""
    if porkbun is None or n <= 0:
        return
    targets = [
        r for r in results
        if r.available and r.status in ("available", "premium") and r.source not in ("porkbun", "cache")
    ][:n]
    total = len(targets)
    phase = "Verifying premium status (~10s each)"
    for i, r in enumerate(targets):
        if on_progress:
            on_progress(phase, i, total)
        try:
            p = parse_check(await porkbun.check_domain(r.domain))
        except Exception as e:  # noqa: BLE001 — keep going through the shortlist
            r.source = f"{r.source}|verify-err:{type(e).__name__}"
            continue
        final_avail = True if p["available"] is None else p["available"]
        price = p["price"] if p["price"] is not None else p["regular"]
        r.available = bool(final_avail)
        r.price = price
        r.renewal = p["renewal"]
        r.premium = p["premium"]
        r.status = ("premium" if p["premium"] else "available") if final_avail else "taken"
        r.source = "porkbun"
        r.score = final_score(r.coolness, final_avail, price, p["premium"], config.budget, r.tld)
        store.save_price(con, r.domain, final_avail, price, p["renewal"], p["premium"], "USD", p["raw"])
    if on_progress and total:
        on_progress(phase, total, total)


async def _drive(domains: list[tuple[Candidate, str, str]], config: Config,
                 on_progress: ProgressCb, verify: int = 0) -> list[RankedDomain]:
    con = store.connect()
    results: list[RankedDomain] = []
    try:
        async with httpx.AsyncClient(http2=True, headers={"User-Agent": "domain-hunter/0.1"}) as client:
            try:
                bootstrap = await load_bootstrap(client, BOOTSTRAP_CACHE)
            except Exception:
                bootstrap = {}
            porkbun = _porkbun(client, config)
            base_pricing: dict = {}
            if porkbun is not None:
                try:
                    base_pricing = await porkbun.pricing()
                except Exception:
                    base_pricing = {}

            sem_task = asyncio.Semaphore(config.rdap_concurrency)
            sem_whois = asyncio.Semaphore(config.whois_concurrency)
            tasks = [
                asyncio.create_task(_process(con, client, bootstrap, base_pricing, c, tld, dom, config, sem_task, sem_whois))
                for (c, tld, dom) in domains
            ]
            total = len(tasks)
            phase = "Checking availability + price"
            for done, fut in enumerate(asyncio.as_completed(tasks), 1):
                results.append(await fut)
                if on_progress:
                    on_progress(phase, done, total)

            results.sort(key=lambda r: r.score, reverse=True)
            if verify and porkbun is not None:
                await _verify(results, porkbun, con, config, verify, on_progress)
                results.sort(key=lambda r: r.score, reverse=True)
            store.save_gems(con, results)
    finally:
        con.close()
    return results


async def run_hunt(config: Config, limit: int | None = None, verify: int = 0,
                   on_progress: ProgressCb = None, rng=None) -> list[RankedDomain]:
    rng = rng or random.Random()
    markov = build_markov()
    known = load_known_words()
    candidates = generate_all(config, markov, rng)

    # Score + de-dupe by name, keeping the best-scoring instance of each.
    best: dict[str, Candidate] = {}
    for c in candidates:
        c.coolness, c.breakdown = score_name(c.name, markov, known, config.min_len, config.max_len)
        if c.name not in best or c.coolness > best[c.name].coolness:
            best[c.name] = c

    pool = [c for c in best.values() if c.coolness >= config.min_coolness]
    check_limit = limit or config.check_limit
    per_name = max(1, check_limit // max(1, len(config.tlds)))

    # Weighted-sample (NOT strict top-N) so every run explores DIFFERENT names.
    # The highest-coolness names are mostly taken real words; re-checking the same
    # top-N each round would find nothing new (the whole point of `dh loop`).
    if len(pool) > per_name:
        weights = [max(c.coolness, 0.01) ** 2 for c in pool]
        chosen = _weighted_sample(pool, weights, per_name, rng)
    else:
        chosen = pool

    domains = [(c, tld, c.name + tld) for c in chosen for tld in config.tlds][:check_limit]
    return await _drive(domains, config, on_progress, verify=verify)


async def check_domains(config: Config, raw_domains: list[str],
                        on_progress: ProgressCb = None, verify: bool = True) -> list[RankedDomain]:
    markov = build_markov()
    known = load_known_words()
    expanded: list[str] = []
    for d in raw_domains:
        d = d.strip().lower()
        if not d:
            continue
        if "." not in d:
            expanded.extend(d + tld for tld in config.tlds)
        else:
            expanded.append(d)

    domains: list[tuple[Candidate, str, str]] = []
    for dom in expanded:
        name, tld = _split(dom)
        cool, bd = score_name(name, markov, known, config.min_len, config.max_len)
        domains.append((Candidate(name=name, strategy="manual", coolness=cool, breakdown=bd), tld, dom))

    # Explicit picks → verify every available one authoritatively.
    return await _drive(domains, config, on_progress, verify=10_000 if verify else 0)
