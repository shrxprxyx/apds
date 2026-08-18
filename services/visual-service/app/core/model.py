import io
import numpy as np
import structlog
from typing import Optional
from pathlib import Path

import torch

from app.core.config import settings

logger = structlog.get_logger()

# ─── Globals ──────────────────────────────────────────────────
efficientnet_model = None
transform = None
device = "cuda" if torch.cuda.is_available() else "cpu"


# ─── Load EfficientNet-B3 (doc 4.3.1) ────────────────────────
async def load_model():
    global efficientnet_model, transform, device

    import torch
    import torchvision.transforms as T
    import timm

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model_path = settings.VISUAL_MODEL_PATH

    if Path(model_path).exists():
        logger.info("loading fine-tuned visual model", path=model_path)
        efficientnet_model = timm.create_model(
            "efficientnet_b3", pretrained=False, num_classes=0
        )
        import torch
        efficientnet_model.load_state_dict(
            torch.load(f"{model_path}/efficientnet_b3.pt", map_location=device)
        )
    else:
        logger.info("loading pretrained EfficientNet-B3")
        efficientnet_model = timm.create_model(
            "efficientnet_b3", pretrained=True, num_classes=0
        )

    efficientnet_model.to(device)
    efficientnet_model.eval()

    # Doc 4.3.1: standard ImageNet normalization
    transform = T.Compose([
        T.Resize((300, 300)),
        T.ToTensor(),
        T.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])

    logger.info("visual model loaded", device=device)


# ─── Extract Embedding ────────────────────────────────────────
def extract_embedding(image_bytes: bytes) -> Optional[np.ndarray]:
    """
    Doc 4.3.1: Run EfficientNet-B3 on screenshot to get
    1536-dim feature embedding. L2 normalized for cosine similarity.
    """
    import torch
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = transform(img).unsqueeze(0).to(device)

        with torch.no_grad():
            embedding = efficientnet_model(tensor).squeeze().cpu().numpy()

        # L2 normalize for cosine similarity in FAISS
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding.astype(np.float32)

    except Exception as e:
        logger.error("embedding extraction failed", error=str(e))
        return None


# ─── Infer ────────────────────────────────────────────────────
async def infer_visual(
    image_bytes: Optional[bytes] = None,
    screenshot_b64: Optional[str] = None,
) -> dict:
    """
    Doc 4.3: Full visual pipeline.
    Input: screenshot bytes or base64
    Output: score, brand_detected, similarity_score, signals
    """
    from app.core.brand_index import search_brand_index

    # Decode base64 if provided
    if image_bytes is None and screenshot_b64:
        import base64
        try:
            image_bytes = base64.b64decode(screenshot_b64)
        except Exception:
            return {"score": 0.0, "confidence": 0.0, "signals": []}

    if image_bytes is None:
        return {"score": 0.0, "confidence": 0.0, "signals": []}

    # Extract embedding
    embedding = extract_embedding(image_bytes)
    if embedding is None:
        return {"score": 0.0, "confidence": 0.0, "signals": []}

    # Search FAISS brand index (doc 4.3.2)
    brand_match = search_brand_index(embedding)

    if brand_match is None:
        return {"score": 0.0, "confidence": 0.0, "signals": []}

    brand_name = brand_match["brand"]
    similarity = brand_match["similarity"]

    # Doc 4.3.2: threshold 0.85 for brand impersonation flag
    if similarity >= settings.BRAND_SIMILARITY_THRESHOLD:
        score = similarity
        signals = [
            f"Visual similarity to {brand_name} login page: {similarity:.2%}",
            f"Possible brand impersonation of {brand_name}",
        ]
    else:
        score = 0.0
        signals = []

    logger.info(
        "visual inference complete",
        brand=brand_name,
        similarity=similarity,
        score=score,
    )

    return {
        "score": round(score, 4),
        "confidence": round(similarity, 4),
        "brand_detected": brand_name if score > 0 else None,
        "brand_similarity": round(similarity, 4),
        "signals": signals,
    }