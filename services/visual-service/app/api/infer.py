from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import structlog

from app.core.screenshot import capture_screenshot, upload_screenshot_to_minio
from app.core.model import infer_visual

router = APIRouter()
logger = structlog.get_logger()


# ─── Schemas ──────────────────────────────────────────────────
class VisualRequest(BaseModel):
    url: str
    screenshot_b64: Optional[str] = None   # pre-captured screenshot from extension


class VisualResponse(BaseModel):
    score: float                            # phishing probability [0.0, 1.0]
    confidence: float                       # similarity confidence
    brand_detected: Optional[str] = None   # impersonated brand name
    brand_similarity: Optional[float] = None
    signals: list[str]                     # human-readable signals (doc 4.5.1)


# ─── POST /infer/visual ───────────────────────────────────────
@router.post("/infer/visual", response_model=VisualResponse)
async def infer_visual_endpoint(payload: VisualRequest):
    """
    Doc 4.3:
    1. Capture screenshot via Playwright (or use pre-captured from extension)
    2. Run EfficientNet-B3 to extract visual embedding
    3. Search FAISS brand index for similarity
    4. Return brand impersonation score
    """
    image_bytes = None

    # ── Use pre-captured screenshot if provided (doc 12: extension) ──
    if payload.screenshot_b64:
        import base64
        try:
            image_bytes = base64.b64decode(payload.screenshot_b64)
            logger.info("using pre-captured screenshot", url=payload.url)
        except Exception:
            pass

    # ── Otherwise capture via Playwright (doc 4.3.1) ──────────
    if image_bytes is None:
        image_bytes = await capture_screenshot(payload.url)

    if image_bytes is None:
        logger.warning("screenshot capture failed", url=payload.url)
        return VisualResponse(
            score=0.0,
            confidence=0.0,
            brand_detected=None,
            brand_similarity=None,
            signals=["Screenshot capture failed"],
        )

    # ── Upload to MinIO (doc 7.3) ─────────────────────────────
    await upload_screenshot_to_minio(image_bytes, payload.url)

    # ── Run visual inference ───────────────────────────────────
    result = await infer_visual(image_bytes=image_bytes)

    logger.info(
        "visual inference complete",
        url=payload.url,
        score=result["score"],
        brand=result.get("brand_detected"),
    )

    return VisualResponse(**result)