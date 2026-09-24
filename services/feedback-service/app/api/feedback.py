from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
import structlog

from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    verdict_id: str
    label: str                                  # TRUE_PHISHING | FALSE_POSITIVE
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    message: str


# ─── POST /feedback ───────────────────────────────────────────
@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.label not in ("TRUE_PHISHING", "FALSE_POSITIVE"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="label must be 'TRUE_PHISHING' or 'FALSE_POSITIVE'",
        )

    # Check verdict exists
    result = await db.execute(
        text("SELECT id FROM verdicts WHERE id = :id"),
        {"id": payload.verdict_id},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verdict not found",
        )

    # Insert feedback record
    result = await db.execute(
        text("""
            INSERT INTO feedback (verdict_id, label, comment)
            VALUES (:verdict_id, :label, :comment)
            RETURNING id
        """),
        {
            "verdict_id": payload.verdict_id,
            "label": payload.label,
            "comment": payload.comment,
        },
    )
    feedback_id = str(result.fetchone()[0])

    # Keep the verdict's own feedback_label column in sync
    await db.execute(
        text("UPDATE verdicts SET feedback_label = :label WHERE id = :id"),
        {"label": payload.label, "id": payload.verdict_id},
    )
    await db.commit()

    logger.info("feedback submitted", feedback_id=feedback_id, label=payload.label)
    return FeedbackResponse(feedback_id=feedback_id, message="Feedback recorded.")


# ─── GET /feedback/labels ──────────────────────────────────────
# Used by training-service to pull labeled examples for retraining.
@router.get("/labels")
async def list_labels(
    used_for_training: Optional[bool] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = """
        SELECT f.id, f.verdict_id, f.label, f.comment, f.used_for_training, f.created_at
        FROM feedback f
    """
    params = {"limit": limit}
    if used_for_training is not None:
        query += " WHERE f.used_for_training = :used_for_training"
        params["used_for_training"] = used_for_training
    query += " ORDER BY f.created_at DESC LIMIT :limit"

    result = await db.execute(text(query), params)
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]


# ─── PATCH /feedback/{feedback_id}/mark-trained ────────────────
# Called by training-service once a feedback row has been folded
# into a retraining run, so it isn't reused next cycle.
@router.patch("/{feedback_id}/mark-trained")
async def mark_used_for_training(feedback_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("UPDATE feedback SET used_for_training = TRUE WHERE id = :id RETURNING id"),
        {"id": feedback_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    await db.commit()
    return {"feedback_id": feedback_id, "used_for_training": True}


# ─── POST /feedback/report/fp ──────────────────────────────────
@router.post("/report/fp", response_model=FeedbackResponse)
async def report_false_positive(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    payload.label = "FALSE_POSITIVE"
    return await submit_feedback(payload, db)


# ─── POST /feedback/report/fn ──────────────────────────────────
@router.post("/report/fn", response_model=FeedbackResponse)
async def report_false_negative(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    payload.label = "TRUE_PHISHING"
    return await submit_feedback(payload, db)
