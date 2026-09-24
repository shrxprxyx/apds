from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import httpx
import structlog

from app.core.config import settings

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas (unchanged — same contract the extension/dashboard expect) ──
class FeedbackRequest(BaseModel):
    verdict_id: str
    label: str                                  # TRUE_PHISHING | FALSE_POSITIVE
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    message: str


# ─── Helper: forward to feedback-service, surface its errors honestly ────
async def forward(method: str, path: str, **kwargs) -> dict:
    url = f"{settings.FEEDBACK_SERVICE_URL}{path}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(method, url, timeout=10.0, **kwargs)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()
    except httpx.RequestError as e:
        logger.warning("feedback-service unreachable", url=url, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feedback service unavailable",
        )


# ─── POST /api/v1/feedback ────────────────────────────────────
@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest):
    data = await forward("POST", "/feedback/", json=payload.model_dump())
    return FeedbackResponse(**data)


# ─── GET /api/v1/feedback/labels ──────────────────────────────
@router.get("/labels")
async def list_labels(used_for_training: Optional[bool] = None, limit: int = 100):
    params = {"limit": limit}
    if used_for_training is not None:
        params["used_for_training"] = used_for_training
    return await forward("GET", "/feedback/labels", params=params)


# ─── POST /api/v1/feedback/report/fp ──────────────────────────
@router.post("/report/fp", response_model=FeedbackResponse)
async def report_false_positive(payload: FeedbackRequest):
    data = await forward("POST", "/feedback/report/fp", json=payload.model_dump())
    return FeedbackResponse(**data)


# ─── POST /api/v1/feedback/report/fn ──────────────────────────
@router.post("/report/fn", response_model=FeedbackResponse)
async def report_false_negative(payload: FeedbackRequest):
    data = await forward("POST", "/feedback/report/fn", json=payload.model_dump())
    return FeedbackResponse(**data)