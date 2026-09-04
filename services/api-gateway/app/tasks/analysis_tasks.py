import asyncio
import json
import time
import httpx
import structlog

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import cache_set
from app.api.v1.endpoints.analyse import (
    call_service,
    persist_verdict,
    score_to_verdict,
)

logger = structlog.get_logger()


# ─── Async implementation ───────────────────────────────────────
# Reuses the exact same call_service / persist_verdict / score_to_verdict
# helpers analyse.py already uses synchronously in-request, so the two
# code paths can never silently drift apart.
async def _run_analysis(url: str, url_hash: str, html_snapshot: str | None,
                         screenshot_b64: str | None, context: str) -> dict:
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            call_service(client, f"{settings.NLP_SERVICE_URL}/infer/content", {
                "content": html_snapshot or url,
                "context": context,
            }),
            call_service(client, f"{settings.URL_SERVICE_URL}/infer/url", {
                "url": url,
            }),
            call_service(client, f"{settings.VISUAL_SERVICE_URL}/infer/visual", {
                "url": url,
                "screenshot_b64": screenshot_b64,
            }),
            call_service(client, f"{settings.ADVERSARIAL_SERVICE_URL}/infer/adversarial", {
                "content": html_snapshot or "",
            }),
        )

    nlp_result, url_result, visual_result, adversarial_result = results
    scores = {
        "nlp": nlp_result["score"],
        "url": url_result["score"],
        "visual": visual_result["score"],
        "adversarial": adversarial_result["score"],
    }

    async with httpx.AsyncClient() as client:
        fusion_result = await call_service(
            client, f"{settings.FUSION_SERVICE_URL}/fuse", {"scores": scores}
        )

    final_score = fusion_result.get("score", scores["nlp"])
    verdict = score_to_verdict(final_score)

    explainability = {
        "top_signals": (
            nlp_result.get("signals", []) +
            url_result.get("signals", []) +
            visual_result.get("signals", []) +
            adversarial_result.get("signals", [])
        )[:5],
        "top_model": fusion_result.get("top_model"),
    }

    async with AsyncSessionLocal() as db:
        task_id = await persist_verdict(db, url_hash, verdict, final_score, scores, explainability)

    cache_key = f"APDS:VERDICT:{url_hash}"
    payload = {
        "task_id": task_id,
        "verdict": verdict,
        "final_score": final_score,
        "scores": scores,
        "explainability": explainability,
        "processing_ms": int((time.time() - start_time) * 1000),
        "cache_hit": False,
    }
    await cache_set(cache_key, json.dumps(payload), ttl=3600)

    logger.info("verdict issued (async task)", task_id=task_id, verdict=verdict, score=final_score)
    return payload


# ─── Celery task entrypoint ─────────────────────────────────────
# Runs on the high_priority queue by default — this is the real-time
# "someone's actively waiting on a verdict" path (extension, dashboard
# "scan now" button). Bulk/email scans should route to `normal` once
# the email plugin exists, by passing queue="normal" at .apply_async() time.
@celery_app.task(
    name="app.tasks.analysis_tasks.run_analysis",
    bind=True,
    queue="high_priority",
    max_retries=2,
    default_retry_delay=5,
)
def run_analysis(self, url: str, url_hash: str, html_snapshot: str | None = None,
                  screenshot_b64: str | None = None, context: str = "browser") -> dict:
    try:
        return asyncio.run(
            _run_analysis(url, url_hash, html_snapshot, screenshot_b64, context)
        )
    except Exception as exc:
        logger.error("analysis task failed", url_hash=url_hash, error=str(exc))
        raise self.retry(exc=exc)