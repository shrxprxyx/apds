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
    scan_id: str
    correct_label: str       # phishing | legitimate
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    message: str


# ─── Routes ───────────────────────────────────────────────────
@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    if payload.correct_label not in ("phishing", "legitimate"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="correct_label must be 'phishing' or 'legitimate'",
        )

    # Check scan exists
    result = await db.execute(
        text("SELECT id FROM scan_results WHERE id = :id"),
        {"id": payload.scan_id},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        )

    # Insert feedback
    result = await db.execute(
        text("""
            INSERT INTO feedback (scan_id, correct_label, comment)
            VALUES (:scan_id, :correct_label, :comment)
            RETURNING id
        """),
        {
            "scan_id": payload.scan_id,
            "correct_label": payload.correct_label,
            "comment": payload.comment,
        },
    )
    feedback_id = str(result.fetchone()[0])
    await db.commit()

    logger.info("feedback submitted", feedback_id=feedback_id, scan_id=payload.scan_id)
    return FeedbackResponse(
        feedback_id=feedback_id,
        message="Feedback recorded. Thank you.",
    )


@router.get("/")
async def list_feedback(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM feedback ORDER BY created_at DESC LIMIT 100")
    )
    rows = result.fetchall()
    return [dict(row._mapping) for row in rows]