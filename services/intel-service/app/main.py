from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.redis import init_redis
from app.api.lookup import router as lookup_router
from app.api.ingest import router as ingest_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting intel-service", environment=settings.ENVIRONMENT)
    await init_redis()
    # No init_db() here on purpose — database.py deliberately doesn't own
    # schema creation (api-gateway's init.sql already does), see database.py.
    yield
    logger.info("shutting down intel-service")


app = FastAPI(
    title="APDS Intel Service",
    description="Threat intelligence ingestion (PhishTank/OpenPhish/URLhaus) and reputation lookups — /lookup",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(lookup_router)
app.include_router(ingest_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "intel-service", "port": 8006}