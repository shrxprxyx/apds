from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.core.database import init_db
from app.core.redis import init_redis
from app.api.v1.router import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info("starting api-gateway", environment=settings.ENVIRONMENT)
    await init_db()
    await init_redis()
    yield
    # ── Shutdown ─────────────────────────────────────────────
    logger.info("shutting down api-gateway")


app = FastAPI(
    title="APDS API Gateway",
    description="Advanced Phishing Detection System — API Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Prometheus metrics ──────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ─── Routes ──────────────────────────────────────────────────
app.include_router(api_router, prefix=f"/api/{settings.API_VERSION}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway"}