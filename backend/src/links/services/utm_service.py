"""UTM parameter parsing utility."""
from urllib.parse import parse_qs, urlparse


def parse_utm(url: str) -> dict[str, str | None]:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return {
        "utm_source": params.get("utm_source", [None])[0],
        "utm_medium": params.get("utm_medium", [None])[0],
        "utm_campaign": params.get("utm_campaign", [None])[0],
    }
