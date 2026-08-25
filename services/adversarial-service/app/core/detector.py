import re
import unicodedata
from typing import Optional

# ─── Zero-width characters (doc 4.4) ─────────────────────────
ZERO_WIDTH_CHARS = {
    '\u200b',  # zero-width space
    '\u200c',  # zero-width non-joiner
    '\u200d',  # zero-width joiner
    '\ufeff',  # byte order mark
    '\u00ad',  # soft hyphen
    '\u2060',  # word joiner
    '\u180e',  # mongolian vowel separator
}

# ─── Homoglyph map (doc 4.4) ─────────────────────────────────
# Maps confusable Unicode chars back to ASCII equivalents
HOMOGLYPH_MAP = {
    # Cyrillic lookalikes
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p',
    'с': 'c', 'х': 'x', 'у': 'y', 'і': 'i',
    'ѕ': 's', 'ԁ': 'd', 'ɡ': 'g', 'ʜ': 'h',
    # Greek lookalikes
    'ο': 'o', 'ρ': 'p', 'ν': 'v', 'κ': 'k',
    'α': 'a', 'ε': 'e', 'ι': 'i', 'τ': 't',
    # Mathematical lookalikes
    '𝐚': 'a', '𝐛': 'b', '𝐜': 'c', '𝐝': 'd',
    '𝐞': 'e', '𝐟': 'f', '𝐠': 'g', '𝐡': 'h',
    # Fullwidth chars
    'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd',
    'ｅ': 'e', 'ｆ': 'f', 'ｇ': 'g', 'ｈ': 'h',
}

# ─── Leetspeak patterns (doc 4.4 word-level perturbations) ───
LEETSPEAK_PATTERN = re.compile(r'[0-9@!$]+')

# ─── AI-generated phishing indicators ────────────────────────
AI_PHISHING_PATTERNS = [
    r'dear\s+valued\s+customer',
    r'your\s+account\s+has\s+been\s+(suspended|compromised|flagged)',
    r'click\s+(?:here|below)\s+(?:to\s+)?(?:verify|confirm|update)',
    r'within\s+\d+\s+hours?\s+or\s+your\s+account',
    r'we\s+have\s+detected\s+(?:unusual|suspicious)\s+activity',
    r'immediately\s+(?:verify|confirm|update)\s+your',
    r'failure\s+to\s+(?:comply|verify|respond)',
]


# ─── Detectors ────────────────────────────────────────────────
def detect_zero_width_chars(text: str) -> dict:
    """Doc 4.4: detect invisible Unicode chars injected between letters."""
    found = [ch for ch in text if ch in ZERO_WIDTH_CHARS]
    count = len(found)
    return {
        "detected": count > 0,
        "count": count,
        "signal": f"Zero-width character injection detected ({count} chars)" if count > 0 else None,
    }


def detect_homoglyphs(text: str) -> dict:
    """Doc 4.4: detect Unicode chars that visually resemble ASCII letters."""
    found = [(i, ch, HOMOGLYPH_MAP[ch]) for i, ch in enumerate(text) if ch in HOMOGLYPH_MAP]
    count = len(found)
    return {
        "detected": count > 0,
        "count": count,
        "signal": f"Homoglyph substitution detected ({count} chars)" if count > 0 else None,
    }


def detect_leetspeak(text: str) -> dict:
    """Doc 4.4: detect character substitutions like paypa1, verif!cation."""
    matches = LEETSPEAK_PATTERN.findall(text.lower())
    suspicious = [m for m in matches if len(m) >= 2]
    detected = len(suspicious) > 0
    return {
        "detected": detected,
        "count": len(suspicious),
        "signal": f"Leetspeak/character substitution detected" if detected else None,
    }


def detect_ai_generated_patterns(text: str) -> dict:
    """Doc 4.4: detect AI-generated phishing text patterns."""
    text_lower = text.lower()
    matched = []
    for pattern in AI_PHISHING_PATTERNS:
        if re.search(pattern, text_lower):
            matched.append(pattern)

    detected = len(matched) > 0
    return {
        "detected": detected,
        "count": len(matched),
        "signal": f"AI-generated phishing pattern detected ({len(matched)} patterns)" if detected else None,
    }


def normalize_text(text: str) -> str:
    """
    Normalize text for RoBERTa input:
    - Remove zero-width chars
    - Replace homoglyphs with ASCII equivalents
    - NFKC Unicode normalization
    """
    # Remove zero-width chars
    text = ''.join(ch for ch in text if ch not in ZERO_WIDTH_CHARS)
    # Replace homoglyphs
    text = ''.join(HOMOGLYPH_MAP.get(ch, ch) for ch in text)
    # NFKC normalization
    text = unicodedata.normalize('NFKC', text)
    return text


# ─── Full Rule-based Detection Pipeline ──────────────────────
def run_detectors(text: str) -> dict:
    """
    Run all rule-based detectors before RoBERTa.
    Returns aggregated signals and a heuristic score.
    """
    results = {
        "zero_width": detect_zero_width_chars(text),
        "homoglyphs": detect_homoglyphs(text),
        "leetspeak": detect_leetspeak(text),
        "ai_patterns": detect_ai_generated_patterns(text),
    }

    signals = [
        v["signal"] for v in results.values()
        if v["detected"] and v["signal"]
    ]

    # Heuristic score based on detections
    score = 0.0
    if results["zero_width"]["detected"]:
        score += 0.4
    if results["homoglyphs"]["detected"]:
        score += 0.4
    if results["leetspeak"]["detected"]:
        score += 0.2
    if results["ai_patterns"]["detected"]:
        score += 0.3

    score = min(score, 1.0)

    return {
        "heuristic_score": round(score, 4),
        "signals": signals,
        "detections": results,
        "normalized_text": normalize_text(text),
    }