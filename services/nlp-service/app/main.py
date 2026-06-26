from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from contextlib import asynccontextmanager
import structlog

from app.core.config import settings
from app.api.infer import router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting nlp-service", environment=settings.ENVIRONMENT)
    from app.core.model import load_model
    await load_model()
    yield
    logger.info("shutting down nlp-service")


app = FastAPI(
    title="APDS NLP Service",
    description="DistilBERT-based phishing content analyser — /infer/content",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nlp-service", "port": 8001}
