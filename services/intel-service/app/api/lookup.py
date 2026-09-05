from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
import structlog

from app.core.database import AsyncSessionLocal
from app.core.redis import cache_get_indicator, cache_set_indicator

logger = structlog.get_logger()
router = APIRouter()


class LookupResponse(BaseModel):
    flagged: bool
    indicator_type: str | None = None
    source: str | None = None
    confidence_score: float = 0.0
    tags: list[str] = []
    cache_hit: bool = False


# ─── GET /lookup/{value} ────────────────────────────────────────
# doc 6.4: url-service checks this before running the full GNN
# pipeline — a domain already confirmed as phishing shouldn't need
# a second, expensive inference pass to reach the same conclusion.
#
# Redis-first (APDS:TI:DOMAIN:{domain}), only DOMAIN-type lookups
# are cached — URL and IP values go straight to Postgres, since the
# cache-warming step in ingest.py only ever populates domain keys.
@router.get("/lookup/{value}", response_model=LookupResponse)
async def lookup(value: str):
    cached = await cache_get_indicator(value)
    if cached:
        return LookupResponse(
            flagged=cached.get("flagged", True),
            source=cached.get("source"),
            confidence_score=cached.get("confidence_score", 0.0),
            indicator_type="DOMAIN",
            cache_hit=True,
        )

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT indicator_type, source, confidence_score, tags
                FROM threat_indicators
                WHERE indicator_value = :value
                ORDER BY confidence_score DESC
                LIMIT 1
            """),
            {"value": value},
        )
        row = result.fetchone()

    if not row:
        return LookupResponse(flagged=False)

    data = dict(row._mapping)

    # Warm the cache on a cold-path hit so the next lookup for this
    # same domain is fast, even outside the normal 15-min ingest cycle
    # (e.g. a domain that was already in Postgres before this service
    # existed, or a DOMAIN row that fell out of TTL between cycles).
    if data["indicator_type"] == "DOMAIN":
        await cache_set_indicator(value, {
            "flagged": True,
            "source": data["source"],
            "confidence_score": data["confidence_score"],
        })

    return LookupResponse(
        flagged=True,
        indicator_type=data["indicator_type"],
        source=data["source"],
        confidence_score=data["confidence_score"],
        tags=data["tags"] or [],
        cache_hit=False,
    )