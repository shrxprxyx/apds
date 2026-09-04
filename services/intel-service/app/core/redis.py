import json
import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger()

redis_client: aioredis.Redis | None = None


async def init_redis():
    global redis_client
    try:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        await redis_client.ping()
        logger.info("redis connected")
    except Exception as e:
        logger.error("redis connection failed", error=str(e))
        raise


async def get_redis() -> aioredis.Redis:
    return redis_client


# ─── Domain Reputation Cache (doc 6.4: APDS:TI:DOMAIN:{domain}) ──
# url-service checks this before hitting /lookup here over HTTP,
# and this service itself checks it before hitting Postgres, so a
# hot domain (e.g. actively-flagged in a fast-moving campaign) never
# needs a DB round trip more than once per TTL window.
async def cache_get_indicator(domain: str) -> dict | None:
    if redis_client is None:
        return None
    try:
        cached = await redis_client.get(f"{settings.TI_CACHE_PREFIX}{domain}")
        return json.loads(cached) if cached else None
    except Exception as e:
        logger.warning("ti cache read failed", domain=domain, error=str(e))
        return None


async def cache_set_indicator(domain: str, data: dict):
    if redis_client is None:
        return
    try:
        await redis_client.set(
            f"{settings.TI_CACHE_PREFIX}{domain}",
            json.dumps(data),
            ex=settings.TI_CACHE_TTL_SECONDS,
        )
    except Exception as e:
        logger.warning("ti cache write failed", domain=domain, error=str(e))