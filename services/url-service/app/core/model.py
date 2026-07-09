import torch
import structlog
from app.gnn.graphsage import GraphSAGEClassifier
from app.features.extractor import FEATURE_DIM
from app.core.config import settings

logger = structlog.get_logger()
_model: GraphSAGEClassifier | None = None

async def load_model():
    global _model
    _model = GraphSAGEClassifier(in_channels=FEATURE_DIM)
    try:
        state = torch.load(settings.MODEL_PATH, map_location="cpu")
        _model.load_state_dict(state)
        logger.info("loaded trained GNN weights", path=settings.MODEL_PATH)
    except FileNotFoundError:
        logger.warning("no weights found — using untrained model (random scores)")
    _model.eval()

def get_model() -> GraphSAGEClassifier:
    if _model is None:
        raise RuntimeError("model not loaded")
    return _model