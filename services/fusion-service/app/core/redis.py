import json
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


# ─── Fusion Weights (doc 7.2: APDS:MODEL:WEIGHTS, TTL 25h) ────
# training-service publishes recalibrated weights here nightly
# (doc 8.2, step 6). Until that job exists, this key will simply
# be empty and we fall back to the static defaults from config.
async def get_fusion_weights() -> dict:
    fallback = {
        "w1": settings.DEFAULT_WEIGHT_NLP,
        "w2": settings.DEFAULT_WEIGHT_URL,
        "w3": settings.DEFAULT_WEIGHT_VISUAL,
        "w4": settings.DEFAULT_WEIGHT_ADVERSARIAL,
        "bias": settings.DEFAULT_BIAS,
    }

    if redis_client is None:
        return fallback

    try:
        cached = await redis_client.get(settings.WEIGHTS_CACHE_KEY)
        if cached:
            weights = json.loads(cached)
            # guard against a partially-written or malformed key
            if all(k in weights for k in ("w1", "w2", "w3", "w4", "bias")):
                return weights
            logger.warning("fusion weights cache malformed, using fallback")
    except Exception as e:
        logger.warning("failed to read fusion weights from redis", error=str(e))

    return fallback