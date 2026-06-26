from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import structlog

from app.core.model import infer

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────
class ContentRequest(BaseModel):
    content: str                    # email body or page HTML snapshot
    subject: Optional[str] = None  # email subject (doc 4.1.1)
    from_hash: Optional[str] = None  # SHA-256 of sender (doc 9.1)
    context: str = "browser"       # browser | email | network (doc 12.2)


class InferResponse(BaseModel):
    score: float                    # phishing probability [0.0, 1.0]
    confidence: float               # model confidence
    signals: list[str]             # top human-readable signals (doc 4.5.1)


# ─── POST /infer/content ──────────────────────────────────────
@router.post("/infer/content", response_model=InferResponse)
async def infer_content(payload: ContentRequest):
    """
    Doc 4.1.1: Full DistilBERT fine-tuned model for email/page content.
    Input: email headers (Subject) + body text, truncated to 512 tokens.
    Output: binary phishing probability score.
    """
    result = await infer(
        content=payload.content,
        subject=payload.subject,
        from_hash=payload.from_hash,
        context=payload.context,
    )
    logger.info("infer/content", score=result["score"], context=payload.context)
    return InferResponse(**result)