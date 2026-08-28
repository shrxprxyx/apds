from fastapi import APIRouter
from pydantic import BaseModel
import structlog

from app.core.model import infer

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────
class AdversarialRequest(BaseModel):
    content: str                # email body or page HTML snapshot


class AdversarialResponse(BaseModel):
    score: float                # phishing probability [0.0, 1.0]
    confidence: float           # model confidence
    signals: list[str]         # human-readable signals (doc 4.5.1)


# ─── POST /infer/adversarial ──────────────────────────────────
@router.post("/infer/adversarial", response_model=AdversarialResponse)
async def infer_adversarial(payload: AdversarialRequest):
    """
    Doc 4.4: Adversarial phishing text detection.
    Detects: homoglyph substitution, zero-width char injection,
             word-level perturbations, AI-generated phishing text.
    Pipeline: rule-based detectors → normalize → RoBERTa → blend scores.
    """
    result = await infer(content=payload.content)
    logger.info("infer/adversarial", score=result["score"])
    return AdversarialResponse(**result)