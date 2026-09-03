from fastapi import APIRouter
from pydantic import BaseModel
import structlog

from app.core.fusion import fuse_scores
from app.core.redis import get_fusion_weights

logger = structlog.get_logger()
router = APIRouter()


class FuseRequest(BaseModel):
    scores: dict[str, float]


@router.post("/fuse")
async def fuse(payload: FuseRequest):
    weights = await get_fusion_weights()
    result = fuse_scores(payload.scores, weights)
    return result