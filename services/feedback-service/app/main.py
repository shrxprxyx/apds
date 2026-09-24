from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
import structlog

from app.core.config import settings
from app.api.feedback import router

logger = structlog.get_logger()

app = FastAPI(
    title="APDS Feedback Service",
    description="Records analyst/user feedback (TRUE_PHISHING / FALSE_POSITIVE) on verdicts, used later by training-service.",
    version="1.0.0",
)

Instrumentator().instrument(app).expose(app)

app.include_router(router, prefix="/feedback")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "feedback-service", "port": 8007}
