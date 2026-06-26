from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import httpx
import asyncio
import hashlib
import json
import time
import structlog

from app.core.database import get_db
from app.core.redis import cache_get, cache_set
from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────
class AnalyseRequest(BaseModel):
    url: str
    html_snapshot: Optional[str] = None
    screenshot_b64: Optional[str] = None
    context: str = "browser"                    # browser | email | network


class AnalyseAccepted(BaseModel):
    task_id: str
    websocket_channel: str
    cache_hit: bool = False


class VerdictResponse(BaseModel):
    task_id: str
    verdict: str                                # ALLOW | WARN | BLOCK
    final_score: float
    scores: dict
    explainability: dict
    processing_ms: int
    cache_hit: bool = False


class EmailScanRequest(BaseModel):
    from_hash: str                              # SHA-256 of sender address
    reply_to_hash: Optional[str] = None
    subject: str
    body_text: str
    links: list[str] = []
    headers: dict = {}


# ─── Helpers ──────────────────────────────────────────────────
def hash_url(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def score_to_verdict(score: float) -> str:
    if score >= 0.85:
        return "BLOCK"
    elif score >= 0.55:
        return "WARN"
    else:
        return "ALLOW"


async def call_service(client: httpx.AsyncClient, url: str, payload: dict) -> dict:
    try:
        response = await client.post(url, json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("service call failed", url=url, error=str(e))
        return {"score": 0.0, "confidence": 0.0, "signals": []}


async def persist_verdict(
    db: AsyncSession,
    url_hash: str,
    verdict: str,
    final_score: float,
    scores: dict,
    explainability: dict,
    geo_country: Optional[str] = None,
) -> str:
    result = await db.execute(
        text("""
            INSERT INTO verdicts
                (url_hash, verdict, final_score, score_nlp, score_url,
                 score_visual, score_adversarial, explainability, geo_country)
            VALUES
                (:url_hash, :verdict, :final_score, :score_nlp, :score_url,
                 :score_visual, :score_adversarial, :explainability, :geo_country)
            RETURNING id
        """),
        {
            "url_hash": url_hash,
            "verdict": verdict,
            "final_score": final_score,
            "score_nlp": scores.get("nlp", 0.0),
            "score_url": scores.get("url", 0.0),
            "score_visual": scores.get("visual", 0.0),
            "score_adversarial": scores.get("adversarial", 0.0),
            "explainability": json.dumps(explainability),
            "geo_country": geo_country,
        },
    )
    task_id = str(result.fetchone()[0])
    await db.commit()
    return task_id


# ─── POST /api/v1/analyse ─────────────────────────────────────
@router.post("/", response_model=AnalyseAccepted, status_code=status.HTTP_202_ACCEPTED)
async def analyse(
    payload: AnalyseRequest,
    db: AsyncSession = Depends(get_db),
):
    start_time = time.time()
    url_hash = hash_url(payload.url)

    # ── Cache check (APDS:VERDICT:{url_hash}, TTL 1h) ─────────
    cache_key = f"APDS:VERDICT:{url_hash}"
    cached = await cache_get(cache_key)
    if cached:
        data = json.loads(cached)
        return AnalyseAccepted(
            task_id=data["task_id"],
            websocket_channel=f"/ws/tasks/{data['task_id']}",
            cache_hit=True,
        )

    # ── Fan out to ML services in parallel ────────────────────
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            call_service(client, f"{settings.NLP_SERVICE_URL}/infer/content", {
                "content": payload.html_snapshot or payload.url,
                "context": payload.context,
            }),
            call_service(client, f"{settings.URL_SERVICE_URL}/infer/url", {
                "url": payload.url,
            }),
            call_service(client, f"{settings.VISUAL_SERVICE_URL}/infer/visual", {
                "url": payload.url,
                "screenshot_b64": payload.screenshot_b64,
            }),
            call_service(client, f"{settings.ADVERSARIAL_SERVICE_URL}/infer/adversarial", {
                "content": payload.html_snapshot or "",
            }),
        )

    nlp_result, url_result, visual_result, adversarial_result = results
    scores = {
        "nlp": nlp_result["score"],
        "url": url_result["score"],
        "visual": visual_result["score"],
        "adversarial": adversarial_result["score"],
    }

    # ── Fusion (weighted Bayesian ensemble) ───────────────────
    async with httpx.AsyncClient() as client:
        fusion_result = await call_service(
            client,
            f"{settings.FUSION_SERVICE_URL}/fuse",
            {"scores": scores},
        )

    final_score = fusion_result.get("score", scores["nlp"])
    verdict = score_to_verdict(final_score)

    # ── Explainability ────────────────────────────────────────
    explainability = {
        "top_signals": (
            nlp_result.get("signals", []) +
            url_result.get("signals", []) +
            visual_result.get("signals", []) +
            adversarial_result.get("signals", [])
        )[:5]
    }

    # ── Persist to verdicts table ──────────────────────────────
    task_id = await persist_verdict(db, url_hash, verdict, final_score, scores, explainability)

    # ── Cache result (TTL 1h per doc) ─────────────────────────
    await cache_set(cache_key, json.dumps({
        "task_id": task_id,
        "verdict": verdict,
        "final_score": final_score,
        "scores": scores,
        "explainability": explainability,
        "processing_ms": int((time.time() - start_time) * 1000),
        "cache_hit": False,
    }), ttl=3600)

    logger.info("verdict issued", task_id=task_id, verdict=verdict, score=final_score)
    return AnalyseAccepted(
        task_id=task_id,
        websocket_channel=f"/ws/tasks/{task_id}",
        cache_hit=False,
    )


# ─── GET /api/v1/verdict/{task_id} ───────────────────────────
@router.get("/verdict/{task_id}", response_model=VerdictResponse)
async def get_verdict(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM verdicts WHERE id = :id"),
        {"id": task_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found")

    data = dict(row._mapping)
    return VerdictResponse(
        task_id=str(data["id"]),
        verdict=data["verdict"],
        final_score=data["final_score"],
        scores={
            "nlp": data["score_nlp"] or 0.0,
            "url": data["score_url"] or 0.0,
            "visual": data["score_visual"] or 0.0,
            "adversarial": data["score_adversarial"] or 0.0,
        },
        explainability=data["explainability"] or {},
        processing_ms=0,
        cache_hit=False,
    )


# ─── POST /api/v1/email/scan ──────────────────────────────────
@router.post("/email/scan")
async def email_scan(
    payload: EmailScanRequest,
    db: AsyncSession = Depends(get_db),
):
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        nlp_result, adversarial_result = await asyncio.gather(
            call_service(client, f"{settings.NLP_SERVICE_URL}/infer/content", {
                "content": payload.body_text,
                "subject": payload.subject,
                "from_hash": payload.from_hash,
                "context": "email",
            }),
            call_service(client, f"{settings.ADVERSARIAL_SERVICE_URL}/infer/adversarial", {
                "content": payload.body_text,
            }),
        )

    scores = {
        "nlp": nlp_result["score"],
        "url": 0.0,
        "visual": 0.0,
        "adversarial": adversarial_result["score"],
    }

    async with httpx.AsyncClient() as client:
        fusion_result = await call_service(
            client,
            f"{settings.FUSION_SERVICE_URL}/fuse",
            {"scores": scores},
        )

    final_score = fusion_result.get("score", scores["nlp"])
    verdict = score_to_verdict(final_score)
    explainability = {"top_signals": nlp_result.get("signals", [])}

    # Use from_hash as url_hash for email scans (privacy by design)
    task_id = await persist_verdict(
        db, payload.from_hash, verdict, final_score, scores, explainability
    )

    # Persist email_analysis record
    await db.execute(
        text("""
            INSERT INTO email_analysis
                (verdict_id, from_hash, reply_to_hash, subject_text,
                 body_text, links, headers)
            VALUES
                (:verdict_id, :from_hash, :reply_to_hash, :subject_text,
                 :body_text, :links, :headers)
        """),
        {
            "verdict_id": task_id,
            "from_hash": payload.from_hash,
            "reply_to_hash": payload.reply_to_hash,
            "subject_text": payload.subject,
            "body_text": payload.body_text[:5000],
            "links": json.dumps(payload.links),
            "headers": json.dumps(payload.headers),
        },
    )
    await db.commit()

    logger.info("email verdict", task_id=task_id, verdict=verdict)
    return {
        "verdict_id": task_id,
        "verdict": verdict,
        "final_score": final_score,
        "scores": scores,
        "explainability": explainability,
        "processing_ms": int((time.time() - start_time) * 1000),
    }