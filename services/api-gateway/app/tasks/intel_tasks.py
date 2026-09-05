import asyncio
import httpx
import structlog

from app.celery_app import celery_app
from app.core.config import settings

logger = structlog.get_logger()


async def _trigger_intel_ingestion() -> dict:
    async with httpx.AsyncClient(timeout=120) as client:
        # Longer timeout than the usual inference calls — a full feed
        # refresh (PhishTank alone is ~150k rows) genuinely takes longer
        # than a single-URL analysis request.
        response = await client.post(f"{settings.INTEL_SERVICE_URL}/ingest/run")
        response.raise_for_status()
        return response.json()


@celery_app.task(
    name="app.tasks.intel_tasks.trigger_intel_ingestion",
    bind=True,
    queue="background",
    max_retries=1,
    default_retry_delay=60,
)
def trigger_intel_ingestion(self):
    try:
        result = asyncio.run(_trigger_intel_ingestion())
        logger.info("intel ingestion triggered", summary=result.get("summary"))
        return result
    except Exception as exc:
        logger.error("intel ingestion trigger failed", error=str(exc))
        raise self.retry(exc=exc)