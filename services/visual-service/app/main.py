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
    logger.info("starting visual-service", environment=settings.ENVIRONMENT)
    from app.core.model import load_model
    from app.core.brand_index import load_brand_index
    await load_model()
    await load_brand_index()
    yield
    logger.info("shutting down visual-service")


app = FastAPI(
    title="APDS Visual Service",
    description="EfficientNet-B3 + FAISS brand impersonation detector — /infer/visual",
    version="1.0.0",
    lifespan=lifespan,
)

Instrumentator().instrument(app).expose(app)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "visual-service", "port": 8003}