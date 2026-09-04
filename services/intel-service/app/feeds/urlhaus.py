import ipaddress
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urlparse

from app.core.config import settings

logger = structlog.get_logger()

USER_AGENT = "apds-phishing-detection-system/1.0"

# abuse.ch now requires an Auth-Key header for API access (they've been
# tightening this — unauthenticated requests increasingly get 401s).
# Get a free key at https://auth.abuse.ch/ and set URLHAUS_API_KEY in .env.
RECENT_URLS_ENDPOINT_TEMPLATE = "{base}/urls/recent/limit/{limit}/"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_urlhaus(limit: int = 1000) -> list[dict]:
    """
    URLhaus skews malware-distribution URLs rather than pure credential
    phishing (unlike PhishTank/OpenPhish) — per doc 6.4 this is meant to
    complement, not duplicate, the other two feeds. Only 'url_status':
    'online' entries are ingested, same reasoning as PhishTank's filter.
    """
    if not settings.URLHAUS_API_KEY:
        logger.warning(
            "no URLHAUS_API_KEY set — abuse.ch now requires auth for most "
            "requests, this call will likely fail with 401"
        )

    url = RECENT_URLS_ENDPOINT_TEMPLATE.format(base=settings.URLHAUS_API_URL, limit=limit)
    headers = {"User-Agent": USER_AGENT}
    if settings.URLHAUS_API_KEY:
        headers["Auth-Key"] = settings.URLHAUS_API_KEY

    async with httpx.AsyncClient(
        timeout=settings.FEED_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        body = response.json()

    if body.get("query_status") != "ok":
        logger.warning("urlhaus query not ok", query_status=body.get("query_status"))
        return []

    indicators = []
    for entry in body.get("urls", []):
        if entry.get("url_status") != "online":
            continue

        malware_url = entry.get("url")
        if not malware_url:
            continue

        indicators.append({
            "indicator_type": "URL",
            "indicator_value": malware_url,
            "confidence_score": 0.9,
            "tags": entry.get("tags") or [],
        })

        domain = urlparse(malware_url).netloc
        if domain:
            # URLhaus is heavy on raw IP:port hosts (e.g. Mozi botnet C2s),
            # unlike PhishTank/OpenPhish which are almost always domain
            # names. The schema has a distinct IP type — misclassifying
            # these as DOMAIN would silently break IP-based lookups.
            host = domain.split(":")[0]
            try:
                ipaddress.ip_address(host)
                indicator_type = "IP"
                indicator_value = host  # store without the port
            except ValueError:
                indicator_type = "DOMAIN"
                indicator_value = domain

            indicators.append({
                "indicator_type": indicator_type,
                "indicator_value": indicator_value,
                "confidence_score": 0.7,
                "tags": entry.get("tags") or [],
            })

    logger.info("urlhaus feed fetched", raw_count=len(body.get("urls", [])), indicator_count=len(indicators))
    return indicators