import asyncio
import json
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.redis import cache_set_indicator
from app.feeds.phishtank import fetch_phishtank
from app.feeds.openphish import fetch_openphish
from app.feeds.urlhaus import fetch_urlhaus

logger = structlog.get_logger()

# Postgres btree indexes cap out at 2704 bytes per index row. Some
# phishing kits deliberately stuff huge tokens/paths into URLs to evade
# naive filters, which can blow past that limit on the UNIQUE(indicator_type,
# indicator_value, source) index and abort the whole batch insert. The
# domain/host — what actually matters for matching — is always near the
# start of the string, so truncating the tail is a safe tradeoff.
MAX_INDICATOR_VALUE_LENGTH = 2000

# Maps each fetcher to the exact indicator_source_enum value in init.sql
# ('PHISHTANK', 'OPENPHISH', 'URLHAUS') — do not rename these without
# also updating the enum, or the upsert below will fail at the DB level.
FEED_SOURCES = {
    "PHISHTANK": fetch_phishtank,
    "OPENPHISH": fetch_openphish,
    "URLHAUS": fetch_urlhaus,
}


async def _upsert_indicators_batch(db: AsyncSession, indicators: list[dict], source: str, batch_size: int = 1000):
    # Individual awaited INSERTs for a feed this size (PhishTank alone is
    # ~150k indicator rows) is impractically slow — each round trip pays
    # full network latency. SQLAlchemy's execute() accepts a list of
    # parameter dicts as a single executemany-style call, so we batch in
    # chunks instead of one INSERT per row.
    stmt = text("""
        INSERT INTO threat_indicators
            (indicator_type, indicator_value, source, confidence_score, tags, last_seen)
        VALUES
            (:indicator_type, :indicator_value, :source, :confidence_score, :tags, NOW())
        ON CONFLICT (indicator_type, indicator_value, source)
        DO UPDATE SET
            last_seen = NOW(),
            confidence_score = EXCLUDED.confidence_score,
            tags = EXCLUDED.tags
    """)

    for i in range(0, len(indicators), batch_size):
        chunk = indicators[i:i + batch_size]
        params = [
            {
                "indicator_type": ind["indicator_type"],
                "indicator_value": ind["indicator_value"][:MAX_INDICATOR_VALUE_LENGTH],
                "source": source,
                "confidence_score": ind["confidence_score"],
                "tags": json.dumps(ind.get("tags", [])),
            }
            for ind in chunk
        ]
        await db.execute(stmt, params)


# Caps how many concurrent Redis SETs run at once during cache warming —
# firing tens of thousands of connections simultaneously would just
# thrash the connection pool rather than actually go faster.
CACHE_WARM_CONCURRENCY = 200


async def _warm_domain_cache(domain_indicators: list[dict], source: str):
    semaphore = asyncio.Semaphore(CACHE_WARM_CONCURRENCY)

    async def _set_one(ind: dict):
        async with semaphore:
            await cache_set_indicator(ind["indicator_value"], {
                "flagged": True,
                "source": source,
                "confidence_score": ind["confidence_score"],
            })

    await asyncio.gather(*(_set_one(ind) for ind in domain_indicators))


async def run_ingestion_cycle() -> dict:
    """
    Fetches all three feeds concurrently, upserts everything into Postgres,
    and warms the Redis domain-reputation cache for DOMAIN-type indicators
    so url-service's fast-path lookup (doc 6.4) doesn't wait on the first
    cold Postgres query after each refresh.

    Feeds are isolated with return_exceptions=True — one feed being down
    (e.g. URLhaus without a key) should never block the other two from
    ingesting on schedule.
    """
    results = await asyncio.gather(
        *(fetcher() for fetcher in FEED_SOURCES.values()),
        return_exceptions=True,
    )

    summary = {}
    async with AsyncSessionLocal() as db:
        for source, result in zip(FEED_SOURCES.keys(), results):
            if isinstance(result, Exception):
                logger.error("feed ingestion failed", source=source, error=str(result))
                summary[source] = {"status": "failed", "error": str(result)}
                continue

            await _upsert_indicators_batch(db, result, source)

            # Only warm the Redis cache for domains, bounded-concurrency
            # instead of firing tens of thousands of writes at once.
            domain_indicators = [ind for ind in result if ind["indicator_type"] == "DOMAIN"]
            await _warm_domain_cache(domain_indicators, source)

            summary[source] = {"status": "ok", "indicator_count": len(result)}

        await db.commit()

    logger.info("ingestion cycle complete", summary=summary)
    return summary