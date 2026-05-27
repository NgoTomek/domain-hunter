from __future__ import annotations

import asyncio
import time

import httpx

BASE = "https://api.porkbun.com/api/json/v3"

# checkDomain is hard-limited to 1 request / 10 seconds, so serialize it with a
# little headroom. pricing/get and ping are unlimited.
CHECK_MIN_INTERVAL = 10.5


class PorkbunError(Exception):
    pass


def _to_float(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_check(data: dict) -> dict:
    """Normalize a checkDomain response into a flat dict (defensive about field names)."""
    resp = data.get("response", data) or {}
    avail_raw = str(resp.get("avail", resp.get("available", ""))).lower()
    if avail_raw in ("yes", "true", "1"):
        available: bool | None = True
    elif avail_raw in ("no", "false", "0"):
        available = False
    else:
        available = None

    additional = resp.get("additional") or {}
    renewal_block = additional.get("renewal") or {}
    return {
        "available": available,
        "price": _to_float(resp.get("price")),
        "regular": _to_float(resp.get("regularPrice")),
        "renewal": _to_float(renewal_block.get("price")),
        "premium": str(resp.get("premium", "")).lower() in ("yes", "true", "1"),
        "raw": resp,
    }


class Porkbun:
    def __init__(self, client: httpx.AsyncClient, api_key: str, secret_key: str):
        self.client = client
        self._auth = {"apikey": api_key, "secretapikey": secret_key}
        self._check_lock = asyncio.Lock()
        self._last_check = 0.0

    async def _post(self, path: str, payload: dict | None = None, auth: bool = True) -> dict:
        body: dict = dict(self._auth) if auth else {}
        if payload:
            body.update(payload)
        r = await self.client.post(f"{BASE}{path}", json=body, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "SUCCESS":
            raise PorkbunError(data.get("message", "unknown error"))
        return data

    async def ping(self) -> dict:
        return await self._post("/ping")

    async def pricing(self) -> dict:
        """Public per-TLD base prices, keyed by TLD without the leading dot."""
        data = await self._post("/pricing/get", auth=False)
        return data.get("pricing", {})

    async def check_domain(self, domain: str, retries: int = 3) -> dict:
        """Authoritative per-domain availability + price + premium flag.

        Serialized client-side to honor the 1-per-10s limit. A 400/429/503 is
        treated as a rate-limit hiccup and retried after a full window; any
        other 4xx (e.g. a genuinely malformed domain) is raised immediately.
        """
        async with self._check_lock:
            wait = CHECK_MIN_INTERVAL - (time.monotonic() - self._last_check)
            if wait > 0:
                await asyncio.sleep(wait)

            last_err: Exception | None = None
            for _ in range(retries):
                try:
                    data = await self._post(f"/domain/checkDomain/{domain}")
                    self._last_check = time.monotonic()
                    return data
                except httpx.HTTPStatusError as e:
                    code = e.response.status_code
                    body = e.response.text.lower()
                    rate_limited = code in (429, 503) or (
                        code == 400 and ("limit" in body or "rate" in body or "throttle" in body)
                    )
                    if not rate_limited:
                        self._last_check = time.monotonic()
                        raise
                    last_err = e
                    await asyncio.sleep(CHECK_MIN_INTERVAL)
                except PorkbunError as e:
                    last_err = e
                    await asyncio.sleep(CHECK_MIN_INTERVAL)
            self._last_check = time.monotonic()
            raise last_err or PorkbunError("checkDomain failed")

    @staticmethod
    def base_price(pricing: dict, tld: str) -> tuple[float | None, float | None]:
        """(registration, renewal) base price for a TLD from a pricing/get dict."""
        info = pricing.get(tld.lstrip("."))
        if not info:
            return None, None
        return _to_float(info.get("registration")), _to_float(info.get("renewal"))
