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
    logger.info("starting url-service", environment=settings.ENVIRONMENT)
    from app.core.model import load_model
    await load_model()
    yield
    logger.info("shutting down url-service")


app = FastAPI(
    title="APDS URL Service",
    description="GraphSAGE GNN for URL redirect chain analysis — /infer/url",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "url-service", "port": 8002}