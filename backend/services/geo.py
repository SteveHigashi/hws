import httpx
from typing import Dict

# Uses ip-api.com (free tier, no key needed, 45 req/min)
# Swap to MaxMind GeoLite2 for production / high volume
GEO_API = "http://ip-api.com/json/{ip}?fields=countryCode,regionName,city,as,timezone"

_private_ranges = (
    "127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
    "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "::1", "localhost",
)


async def resolve_geo(ip: str) -> Dict[str, str]:
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
