import math
import structlog

logger = structlog.get_logger()

# ─── Numerical safety ──────────────────────────────────────────
# Raw model scores are probabilities in [0, 1]. logit(0) and
# logit(1) are undefined (-inf / +inf), so we clip before taking
# the log-odds transform. This matters in practice: an unavailable
# sub-service currently returns score=0.0 (see api-gateway's
# call_service() fallback), which would otherwise blow up here.
EPSILON = 1e-6


def _clip(p: float) -> float:
    return min(max(p, EPSILON), 1 - EPSILON)


def logit(p: float) -> float:
    p = _clip(p)
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    # guard against overflow on very large |x|
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


# ─── Doc 4.5.1: Weighted Bayesian Ensemble ────────────────────
# log_odds_combined = w1*logit(p_nlp) + w2*logit(p_url)
#                    + w3*logit(p_visual) + w4*logit(p_adversarial)
#                    + bias
# final_score = sigmoid(log_odds_combined)
def fuse_scores(scores: dict, weights: dict) -> dict:
    """
    scores: {"nlp": float, "url": float, "visual": float, "adversarial": float}
    weights: {"w1": float, "w2": float, "w3": float, "w4": float, "bias": float}
    """
    p_nlp = scores.get("nlp", 0.0)
    p_url = scores.get("url", 0.0)
    p_visual = scores.get("visual", 0.0)
    p_adversarial = scores.get("adversarial", 0.0)

    log_odds_combined = (
        weights["w1"] * logit(p_nlp)
        + weights["w2"] * logit(p_url)
        + weights["w3"] * logit(p_visual)
        + weights["w4"] * logit(p_adversarial)
        + weights["bias"]
    )

    final_score = sigmoid(log_odds_combined)

    # ─── Explainability: which model drove the verdict ────────
    # doc 4.5.1: "the top contributing model and its key signals
    # are surfaced in the verdict payload"
    contributions = {
        "nlp": weights["w1"] * logit(p_nlp),
        "url": weights["w2"] * logit(p_url),
        "visual": weights["w3"] * logit(p_visual),
        "adversarial": weights["w4"] * logit(p_adversarial),
    }
    top_model = max(contributions, key=contributions.get)

    logger.debug(
        "fusion computed",
        scores=scores,
        final_score=final_score,
        top_model=top_model,
    )

    return {
        "score": final_score,
        "top_model": top_model,
        "contributions": contributions,
    }