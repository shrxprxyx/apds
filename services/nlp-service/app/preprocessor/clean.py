import re
import html
from typing import Optional


# ─── Email/text cleaning before tokenisation ──────────────────

def remove_html_tags(text: str) -> str:
    """Strip HTML tags, keep visible text."""
    text = html.unescape(text)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    return text


def normalize_urls(text: str) -> str:
    """Replace full URLs with a [URL] token to reduce noise."""
    return re.sub(r'https?://\S+', '[URL]', text)


def normalize_emails(text: str) -> str:
    """Replace email addresses with [EMAIL] token."""
    return re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', text)


def remove_extra_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single space."""
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


def remove_zero_width_chars(text: str) -> str:
    """
    Remove zero-width and invisible Unicode characters.
    Used in adversarial phishing to break tokenisation (doc 4.4).
    """
    zero_width = [
        '\u200b',  # zero-width space
        '\u200c',  # zero-width non-joiner
        '\u200d',  # zero-width joiner
        '\ufeff',  # byte order mark
        '\u00ad',  # soft hyphen
    ]
    for char in zero_width:
        text = text.replace(char, '')
    return text


def normalize_homoglyphs(text: str) -> str:
    """
    Normalize common homoglyph substitutions back to ASCII.
    e.g. Cyrillic 'а' → Latin 'a' (doc 4.4 adversarial attacks).
    """
    homoglyph_map = {
        'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p',
        'с': 'c', 'х': 'x', 'у': 'y', 'і': 'i',
        'ѕ': 's', 'ԁ': 'd', 'ɡ': 'g', 'ʜ': 'h',
    }
    return ''.join(homoglyph_map.get(ch, ch) for ch in text)


def clean(
    text: str,
    subject: Optional[str] = None,
    max_chars: int = 4096,
) -> str:
    """
    Full cleaning pipeline before DistilBERT tokenisation.
    Prepends subject if provided (doc 4.1.1: subject + body concatenated).
    """
    text = remove_zero_width_chars(text)
    text = normalize_homoglyphs(text)
    text = remove_html_tags(text)
    text = normalize_urls(text)
    text = normalize_emails(text)
    text = remove_extra_whitespace(text)

    # Prepend subject per doc 4.1.1
    if subject:
        subject = remove_zero_width_chars(subject)
        subject = normalize_homoglyphs(subject)
        subject = remove_extra_whitespace(subject)
        text = f"{subject} [SEP] {text}"

    # Truncate to max_chars before tokeniser handles token truncation
    return text[:max_chars]