import json
import urllib.request
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class GeoInfo:
    city: str | None = None
    region: str | None = None
    country: str | None = None
    timezone: str | None = None
    lat: float | None = None
    lon: float | None = None

    def summary(self) -> str:
        """Human-readable location summary for LLM context."""
        parts = [p for p in [self.city, self.region, self.country] if p]
        location = ", ".join(parts) if parts else "Unknown"
        tz = self.timezone or "Unknown"
        return f"{location} (timezone: {tz})"


@lru_cache(maxsize=1)
def get_geo_info() -> GeoInfo:
    """Get geographic info based on IP address using ip-api.com (no key needed)."""
    try:
        url = "http://ip-api.com/json/?fields=city,regionName,country,timezone,lat,lon"
        req = urllib.request.Request(url, headers={"User-Agent": "ccal/0.1"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return GeoInfo(
            city=data.get("city"),
            region=data.get("regionName"),
            country=data.get("country"),
            timezone=data.get("timezone"),
            lat=data.get("lat"),
            lon=data.get("lon"),
        )
    except Exception:
        return GeoInfo()
