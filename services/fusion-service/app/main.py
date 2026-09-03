from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.redis import init_redis
from app.api.fuse import router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting fusion-service", environment=settings.ENVIRONMENT)
    await init_redis()
    yield
    logger.info("shutting down fusion-service")


app = FastAPI(
    title="APDS Fusion Service",
    description="Weighted Bayesian ensemble combining nlp/url/visual/adversarial scores — /fuse",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fusion-service", "port": 8005}