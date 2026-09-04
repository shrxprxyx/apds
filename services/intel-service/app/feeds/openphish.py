import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from urllib.parse import urlparse

from app.core.config import settings

logger = structlog.get_logger()

USER_AGENT = "apds-phishing-detection-system/1.0"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def fetch_openphish() -> list[dict]:
    """
    OpenPhish's free community feed has no auth and no per-URL metadata —
    it's a raw text file, one URL per line, covering roughly the last 7
    days of detections. No "online" status field exists here (unlike
    PhishTank), so we trust every line as-is; OpenPhish's own detection
    engine already did that filtering before publishing.
    """
    async with httpx.AsyncClient(
        timeout=settings.FEED_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = await client.get(
            settings.OPENPHISH_FEED_URL,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        raw_lines = response.text.splitlines()

    indicators = []
    for line in raw_lines:
        phish_url = line.strip()
        if not phish_url or not phish_url.startswith(("http://", "https://")):
            continue

        indicators.append({
            "indicator_type": "URL",
            "indicator_value": phish_url,
            "confidence_score": 1.0,  # OpenPhish publishes at 100% claimed accuracy
            "tags": [],  # no brand/target metadata in the free text feed
        })

        domain = urlparse(phish_url).netloc
        if domain:
            indicators.append({
                "indicator_type": "DOMAIN",
                "indicator_value": domain,
                "confidence_score": 0.7,
                "tags": [],
            })

    logger.info("openphish feed fetched", raw_count=len(raw_lines), indicator_count=len(indicators))
    return indicators