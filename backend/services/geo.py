import httpx
from typing import Dict

from config import get_settings

# ip-api.com, free tier: no key, 45 requests a minute, and NO TLS - the free tier
# is plain HTTP only, so an enabled lookup sends the IP in clear text.
#
# This is OFF unless the operator sets EXTERNAL_GEO=true in their settings.env.
# The gate lives in resolve_geo() rather than at the call sites deliberately:
# three call sites reach this (the log importer, the log-import script and the
# browser collector), and a gate per call site is how one of them quietly keeps
# calling out after somebody adds a fourth.
GEO_API = "http://ip-api.com/json/{ip}?fields=countryCode,regionName,city,as,timezone"

_private_ranges = (
    "127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
    "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "::1", "localhost",
)


async def resolve_geo(ip: str) -> Dict[str, str]:
    if not get_settings().external_geo:
        return {}
    if any(ip.startswith(prefix) for prefix in _private_ranges):
        return {}
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(GEO_API.format(ip=ip))
            if r.status_code == 200:
                data = r.json()
                return {
                    "country": data.get("countryCode"),
                    "region": data.get("regionName"),
                    "city": data.get("city"),
                    "asn": data.get("as"),
                    "timezone": data.get("timezone"),
                }
    except Exception:
        pass
    return {}
