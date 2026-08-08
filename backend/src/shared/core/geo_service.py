"""IP geolocation service using ipinfo.io with Redis caching."""
import json

import httpx

from src.shared.core.config import settings
from src.shared.core.redis import redis_client

_COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "GB": "United Kingdom",
    "CA": "Canada", "AU": "Australia", "DE": "Germany", "FR": "France",
    "JP": "Japan", "BR": "Brazil", "RU": "Russia", "CN": "China",
    "SG": "Singapore", "AE": "United Arab Emirates", "NL": "Netherlands",
}


class GeoService:
    CACHE_TTL = 86400  # 24 hours

    async def resolve(self, ip: str) -> dict:
        if not ip or ip in ("127.0.0.1", "::1", "localhost"):
            return {"country": None, "city": None}

        cache_key = f"geo:{ip}"
        if redis_client:
            cached = await redis_client.get(cache_key)
            if cached:
                return json.loads(cached)  # type: ignore[no-any-return]

        try:
            url = f"https://ipinfo.io/{ip}"
            if settings.IPINFO_TOKEN:
                url += f"?token={settings.IPINFO_TOKEN}"
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {"country": None, "city": None}
                data = resp.json()
        except Exception:
            return {"country": None, "city": None}

        code = data.get("country")
        country = _COUNTRY_NAMES.get(code, code)
        result = {
            "country": country,
            "city": data.get("city"),
        }

        if redis_client and result["country"]:
            await redis_client.setex(cache_key, self.CACHE_TTL, json.dumps(result))

        return result
