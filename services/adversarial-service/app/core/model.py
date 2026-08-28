import os
from typing import Optional
from pathlib import Path
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# ─── Globals ──────────────────────────────────────────────────
tokenizer = None
model = None
device = "cpu"


# ─── Load RoBERTa (doc 4.4) ───────────────────────────────────
async def load_model():
    """
    Doc 4.4: RoBERTa-base fine-tuned for adversarial phishing detection.
    Falls back to base roberta-base if fine-tuned model not found.
    """
    global tokenizer, model, device

    from transformers import RobertaTokenizerFast, RobertaForSequenceClassification
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_path = settings.ADVERSARIAL_MODEL_PATH

    if Path(model_path).exists():
        logger.info("loading fine-tuned RoBERTa", path=model_path)
        tokenizer = RobertaTokenizerFast.from_pretrained(model_path)
        model = RobertaForSequenceClassification.from_pretrained(model_path)
    else:
        logger.warning("fine-tuned model not found, loading base RoBERTa")
        tokenizer = RobertaTokenizerFast.from_pretrained("roberta-base")
        model = RobertaForSequenceClassification.from_pretrained(
            "roberta-base", num_labels=2
        )

    model.to(device)
    model.eval()
    logger.info("adversarial model loaded", device=device)


# ─── Inference ────────────────────────────────────────────────
async def infer(content: str) -> dict:
    """
    Doc 4.4: Full adversarial detection pipeline.
    1. Run rule-based detectors (homoglyphs, zero-width, leetspeak, AI patterns)
    2. Normalize text
    3. Run RoBERTa on normalized text
    4. Blend heuristic + model scores
    """
    import torch
    from app.core.detector import run_detectors

    # ── Rule-based detection ──────────────────────────────────
    detection = run_detectors(content)
    heuristic_score = detection["heuristic_score"]
    signals = detection["signals"]
    normalized_text = detection["normalized_text"]

    # ── RoBERTa inference ─────────────────────────────────────
    if model is None or tokenizer is None:
        logger.warning("model not loaded, returning heuristic score only")
        return {
            "score": heuristic_score,
            "confidence": heuristic_score,
            "signals": signals,
        }

    inputs = tokenizer(
        normalized_text,
        return_tensors="pt",
        truncation=True,
        max_length=settings.MAX_SEQ_LENGTH,
        padding=True,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        phishing_prob = probs[0][1].item()
        confidence = max(probs[0]).item()

    # ── Blend scores (doc 4.4) ────────────────────────────────
    # Heuristic catches obvious attacks, RoBERTa catches subtle ones
    final_score = round(0.6 * phishing_prob + 0.4 * heuristic_score, 4)

    logger.info(
        "adversarial inference complete",
        score=final_score,
        heuristic=heuristic_score,
        roberta=phishing_prob,
    )

    return {
        "score": final_score,
        "confidence": round(confidence, 4),
        "signals": signals,
    }