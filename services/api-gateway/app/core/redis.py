import redis.asyncio as aioredis
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ─── Redis Client ─────────────────────────────────────────────
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


async def cache_set(key: str, value: str, ttl: int = 300):
    await redis_client.setex(key, ttl, value)


async def cache_get(key: str) -> str | None:
    return await redis_client.get(key)


async def cache_delete(key: str):
    await redis_client.delete(key)