from __future__ import annotations

import asyncio

# Authoritative WHOIS servers for TLDs that lack (or unreliably serve) RDAP.
WHOIS_SERVERS = {
    "ai": "whois.nic.ai",
    "sh": "whois.nic.sh",
    "io": "whois.nic.io",
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "co": "whois.nic.co",
    "me": "whois.nic.me",
    "app": "whois.nic.google",
    "dev": "whois.nic.google",
    "xyz": "whois.nic.xyz",
}

AVAILABLE_MARKERS = (
    "no match",
    "not found",
    "no entries found",
    "no data found",
    "not registered",
    "no object found",
    "available for registration",
    "status: free",
    "domain not found",
)
TAKEN_MARKERS = (
    "creation date",
    "registry domain id",
    "registrar:",
    "name server",
    "registrant",
    "updated date",
    "domain status: ok",
)


async def whois_check(domain: str, timeout: float = 10.0) -> tuple[bool | None, str]:
    tld = domain.rsplit(".", 1)[-1].lower()
    server = WHOIS_SERVERS.get(tld)
    if not server:
        return None, "no-whois-server"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, 43), timeout=timeout
        )
        writer.write((domain + "\r\n").encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(-1), timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
    except (asyncio.TimeoutError, OSError) as e:
        return None, f"whois-error:{type(e).__name__}"

    text = raw.decode("utf-8", "ignore").lower()
    if any(m in text for m in AVAILABLE_MARKERS):
        return True, "whois-available"
    if any(m in text for m in TAKEN_MARKERS):
        return False, "whois-taken"
    return None, "whois-ambiguous"
