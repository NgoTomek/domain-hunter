from __future__ import annotations

import dns.asyncresolver
import dns.exception
import dns.resolver


async def has_dns_records(domain: str, timeout: float = 5.0) -> bool | None:
    """Cheap NEGATIVE filter.

    Returns True only when the domain clearly resolves (NS/SOA present) → taken.
    Returns None otherwise — absence of DNS does NOT prove availability, so the
    caller must confirm with RDAP/WHOIS.
    """
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout
    resolver.timeout = timeout
    for rtype in ("NS", "SOA"):
        try:
            answer = await resolver.resolve(domain, rtype)
            if answer:
                return True
        except dns.resolver.NXDOMAIN:
            return None
        except dns.resolver.NoAnswer:
            continue
        except (dns.resolver.NoNameservers, dns.exception.Timeout, dns.exception.DNSException):
            return None
    return None
