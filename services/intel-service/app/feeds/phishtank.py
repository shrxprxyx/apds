import gzip
import json
import httpx
import structlog

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from urllib.parse import urlparse

from app.core.config import settings

logger = structlog.get_logger()

PHISHTANK_BASE_URL = "https://data.phishtank.com/data"
USER_AGENT = "apds-phishing-detection-system/1.0"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (httpx.ConnectError, httpx.TimeoutException)
    ),
)
async def fetch_phishtank() -> list[dict]:

    api_key = settings.PHISHTANK_API_KEY

    if api_key and api_key != "your_phishtank_api_key_here":
        url = f"{PHISHTANK_BASE_URL}/{api_key}/online-valid.json.gz"
    else:
        url = f"{PHISHTANK_BASE_URL}/online-valid.json.gz"
        logger.warning(
            "no PHISHTANK_API_KEY set, using public rate-limited feed"
        )

    async with httpx.AsyncClient(
        timeout=settings.FEED_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:

        response = await client.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )

        response.raise_for_status()

        # IMPORTANT: .json.gz is a gzip-compressed file
        raw_entries = json.loads(
            gzip.decompress(response.content).decode("utf-8")
        )

    indicators = []

    for entry in raw_entries:

        if entry.get("online") != "yes":
            continue

        phish_url = entry.get("url")

        if not phish_url:
            continue

        tags = [entry["target"]] if entry.get("target") else []

        indicators.append({
            "indicator_type": "URL",
            "indicator_value": phish_url,
            "confidence_score": 0.9,
            "tags": tags,
        })

        domain = urlparse(phish_url).hostname

        if domain:
            indicators.append({
                "indicator_type": "DOMAIN",
                "indicator_value": domain,
                "confidence_score": 0.7,
                "tags": tags,
            })

    logger.info(
        "phishtank feed fetched",
        raw_count=len(raw_entries),
        indicator_count=len(indicators),
    )

    return indicators