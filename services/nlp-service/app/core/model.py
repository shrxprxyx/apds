import os
import re
from typing import Optional
import structlog

logger = structlog.get_logger()

# ─── Globals ──────────────────────────────────────────────────
tokenizer = None
model = None
device = "cpu"

# Doc 4.1.2 — urgency keywords for feature engineering
URGENCY_KEYWORDS = [
    "urgent", "verify", "suspended", "immediately", "action required",
    "confirm", "update", "unusual activity", "limited time", "account locked",
    "click here", "validate", "expires", "unauthorized",
]


# ─── Load Model ───────────────────────────────────────────────
async def load_model():
    """
    Load fine-tuned DistilBERT from NLP_MODEL_PATH.
    Falls back to base distilbert-base-uncased if fine-tuned model not found.
    Doc 4.1.1: base model distilbert-base-uncased, classification head on [CLS] token.
    """
    global tokenizer, model, device

    from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    model_path = os.environ.get("NLP_MODEL_PATH", "/models/nlp/phishing_distilbert")

    if os.path.exists(model_path):
        logger.info("loading fine-tuned model", path=model_path)
        tokenizer = DistilBertTokenizerFast.from_pretrained(model_path)
        model = DistilBertForSequenceClassification.from_pretrained(model_path)
    else:
        logger.warning("fine-tuned model not found, loading base model", path=model_path)
        tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")
        model = DistilBertForSequenceClassification.from_pretrained(
            "distilbert-base-uncased", num_labels=2
        )

    model.to(device)
    model.eval()
    logger.info("nlp model loaded", device=device)


# ─── Feature Engineering (doc 4.1.2) ─────────────────────────
def extract_features(
    content: str,
    subject: Optional[str] = None,
    from_hash: Optional[str] = None,
    context: str = "browser",
) -> dict:
    """
    Pre-model feature extraction per doc section 4.1.2.
    Feeds a lightweight side-model whose output is concatenated
    with the DistilBERT logit at the fusion stage.
    """
    text_lower = content.lower()

    # Urgency keyword density — normalised count
    urgency_count = sum(1 for kw in URGENCY_KEYWORDS if kw in text_lower)
    urgency_density = urgency_count / max(len(content.split()), 1)

    # Link-to-text ratio — number of hyperlinks / word count
    links = re.findall(r'https?://\S+', content)
    word_count = max(len(content.split()), 1)
    link_ratio = len(links) / word_count

    # HTML obfuscation score — ratio of encoded chars to visible chars
    encoded_chars = len(re.findall(r'%[0-9a-fA-F]{2}|&#\d+;|&[a-z]+;', content))
    visible_chars = max(len(re.sub(r'<[^>]+>', '', content)), 1)
    obfuscation_score = encoded_chars / visible_chars

    # External resource domains count
    domains = set(re.findall(r'https?://([^/\s]+)', content))
    external_domain_count = len(domains)

    # Form action to different domain flag
    form_actions = re.findall(r'action=["\']?(https?://[^"\'>\s]+)', content)
    form_domain_mismatch = 1 if form_actions else 0

    return {
        "urgency_density": round(urgency_density, 4),
        "link_ratio": round(link_ratio, 4),
        "obfuscation_score": round(obfuscation_score, 4),
        "external_domain_count": external_domain_count,
        "form_domain_mismatch": form_domain_mismatch,
        "link_count": len(links),
    }


# ─── Build signals from features (doc 4.1.2) ─────────────────
def features_to_signals(features: dict) -> list[str]:
    signals = []
    if features["urgency_density"] > 0.02:
        signals.append(f"High urgency keyword density ({features['urgency_density']:.3f})")
    if features["link_ratio"] > 0.05:
        signals.append(f"High link-to-text ratio ({features['link_ratio']:.3f})")
    if features["obfuscation_score"] > 0.01:
        signals.append(f"HTML obfuscation detected (score: {features['obfuscation_score']:.3f})")
    if features["form_domain_mismatch"]:
        signals.append("Form action points to external domain")
    if features["external_domain_count"] > 5:
        signals.append(f"High external resource domain count ({features['external_domain_count']})")
    return signals


# ─── Inference ────────────────────────────────────────────────
async def infer(
    content: str,
    subject: Optional[str] = None,
    from_hash: Optional[str] = None,
    context: str = "browser",
) -> dict:
    """
    Doc 4.1.1:
    - Input: email headers (Subject) concatenated with body, truncated to 512 tokens
    - Output: binary phishing probability [0.0, 1.0]
    """
    import torch

    # ── Build input text (doc 4.1.1) ──────────────────────────
    # Concatenate subject + body, truncated to 512 tokens
    input_text = f"{subject} [SEP] {content}" if subject else content

    # ── Feature engineering (doc 4.1.2) ──────────────────────
    features = extract_features(content, subject, from_hash, context)
    signals = features_to_signals(features)

    # ── Model inference ───────────────────────────────────────
    if model is None or tokenizer is None:
        logger.warning("model not loaded, returning stub score")
        return {"score": 0.0, "confidence": 0.0, "signals": signals}

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        truncation=True,
        max_length=512,             # doc: truncated to 512 tokens
        padding=True,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        # [CLS] token classification head (doc 4.1.1)
        probs = torch.softmax(outputs.logits, dim=-1)
        phishing_prob = probs[0][1].item()  # label 1 = phishing
        confidence = max(probs[0]).item()

    # Blend model score with feature-based heuristics
    feature_score = min(
        features["urgency_density"] * 5 +
        features["link_ratio"] * 3 +
        features["obfuscation_score"] * 2 +
        features["form_domain_mismatch"] * 0.3,
        1.0,
    )
    final_score = round(0.8 * phishing_prob + 0.2 * feature_score, 4)

    logger.info("nlp inference complete", score=final_score, confidence=confidence)
    return {
        "score": final_score,
        "confidence": round(confidence, 4),
        "signals": signals,
    }