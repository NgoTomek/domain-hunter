from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"

# TLDs with working RDAP that AREN'T in the IANA bootstrap (verified live).
# Using these avoids slow, heuristic WHOIS for io/me/sh.
RDAP_OVERRIDES = {
    "io": "https://rdap.identitydigital.services/rdap/",
    "me": "https://rdap.identitydigital.services/rdap/",
    "sh": "https://rdap.identitydigital.services/rdap/",
}


async def load_bootstrap(
    client: httpx.AsyncClient,
    cache_path: Path,
    ttl_days: int = 30,
) -> dict[str, str]:
    """Fetch + cache IANA's TLD → RDAP-base-URL map."""
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < ttl_days * 86400:
        try:
            return json.loads(cache_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass

    r = await client.get(BOOTSTRAP_URL, timeout=20)
    r.raise_for_status()
    data = r.json()
    mapping: dict[str, str] = {}
    for service in data.get("services", []):
        if len(service) < 2:
            continue
        tlds, urls = service[0], service[1]
        base = next((u for u in urls if u.startswith("https")), urls[0] if urls else None)
        if not base:
            continue
        for tld in tlds:
            mapping[tld.lower()] = base

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(mapping))
    return mapping


async def rdap_check(
    client: httpx.AsyncClient,
    domain: str,
    bootstrap: dict[str, str],
) -> tuple[bool | None, str]:
    """Authoritative availability: 404 → available, 200 → taken, else unknown."""
    tld = domain.rsplit(".", 1)[-1].lower()
    base = RDAP_OVERRIDES.get(tld) or bootstrap.get(tld)
    if not base:
        return None, "no-rdap"
    url = base.rstrip("/") + "/domain/" + domain
    try:
        r = await client.get(
            url,
            headers={"Accept": "application/rdap+json"},
            follow_redirects=True,
            timeout=15,
        )
    except httpx.HTTPError as e:
        return None, f"rdap-error:{type(e).__name__}"

    if r.status_code == 404:
        return True, "rdap-404"
    if r.status_code == 200:
        return False, "rdap-200"
    if r.status_code == 429:
        return None, "rdap-rate-limited"
    return None, f"rdap-http-{r.status_code}"
