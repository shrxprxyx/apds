from fastapi import APIRouter
import structlog

from app.core.ingest import run_ingestion_cycle

logger = structlog.get_logger()
router = APIRouter()


# ─── POST /ingest/run ────────────────────────────────────────────
# Called by api-gateway's Celery Beat schedule every
# FEED_REFRESH_INTERVAL_MINUTES (doc 6.4). Exposed over HTTP rather
# than api-gateway importing intel-service's Python code directly —
# keeps services independently deployable and avoids api-gateway
# needing this service's dependencies installed.
@router.post("/ingest/run")
async def trigger_ingestion():
    summary = await run_ingestion_cycle()
    return {"status": "completed", "summary": summary}