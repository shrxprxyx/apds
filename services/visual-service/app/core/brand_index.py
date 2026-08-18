import json
import numpy as np
import structlog
from typing import Optional
from pathlib import Path

from app.core.config import settings

logger = structlog.get_logger()

# ─── Globals ──────────────────────────────────────────────────
faiss_index = None
brand_labels = []


# ─── Load Brand Index (doc 4.3.2) ────────────────────────────
async def load_brand_index():
    global faiss_index, brand_labels

    import faiss

    index_path = settings.BRAND_INDEX_PATH
    labels_path = settings.BRAND_LABELS_PATH

    if not Path(index_path).exists():
        logger.warning(
            "FAISS brand index not found — run build_brand_index.py first",
            path=index_path,
        )
        return

    if not Path(labels_path).exists():
        logger.warning("brand labels not found", path=labels_path)
        return

    faiss_index = faiss.read_index(index_path)

    with open(labels_path, "r") as f:
        brand_labels = json.load(f)

    logger.info(
        "brand index loaded",
        brands=len(brand_labels),
        index_size=faiss_index.ntotal,
    )


# ─── Search Brand Index (doc 4.3.2) ──────────────────────────
def search_brand_index(
    embedding: np.ndarray,
    top_k: int = None,
) -> Optional[dict]:
    """
    Doc 4.3.2: Search FAISS IndexFlatIP with L2-normalized embedding.
    Returns top brand match with cosine similarity score.
    """
    if faiss_index is None or not brand_labels:
        logger.warning("brand index not loaded")
        return None

    top_k = top_k or settings.TOP_K_BRANDS

    # Reshape for FAISS
    query = embedding.reshape(1, -1).astype(np.float32)

    # Search — IndexFlatIP returns inner product (= cosine sim for L2-normalized)
    similarities, indices = faiss_index.search(query, top_k)

    results = []
    for sim, idx in zip(similarities[0], indices[0]):
        if idx < 0 or idx >= len(brand_labels):
            continue
        results.append({
            "brand": brand_labels[idx],
            "similarity": float(sim),
        })

    if not results:
        return None

    # Return top match
    top = results[0]
    top["top_k_results"] = results

    logger.info(
        "brand search complete",
        top_brand=top["brand"],
        similarity=top["similarity"],
    )

    return top