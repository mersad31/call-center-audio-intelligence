# rules.py
from typing import List, Optional
import re

from .errors import error_response
from .preprocessing import is_persian
from .scoring import (
    has_emotion_words,
    NEUTRAL_PHRASES,
    INTENSIFIER_FACTORS,
    normalize_text,
)


def validate_input(raw_text: str, messages: List[str]) -> Optional[dict]:
    if raw_text is None or raw_text.strip() == "":
        return error_response("E01")

    if not messages:
        return error_response("E02")

    all_text = " ".join(str(m) for m in messages if m is not None).strip()

    # relaxed_validation — only reject meaningless (punctuation-only) input
    content_only = re.sub(r"[^\w\u0600-\u06FF]+", "", all_text)
    if content_only == "":
        return error_response("E03")

    if not is_persian(all_text):
        return error_response("E04")

    return None


def validate_emotional_content(messages: List[str], sentiment_labels: List[str]) -> Optional[dict]:
    if not messages:
        return error_response("E02")

    normalized_messages = [normalize_text(m) for m in messages if m is not None]

    # accept short but emotional / sentiment-bearing inputs
    has_emotion = any(
        has_emotion_words(m)
        or any(p in m for p in NEUTRAL_PHRASES)
        or any(t in m.split() for t in INTENSIFIER_FACTORS.keys())
        for m in normalized_messages
    )

    # backward-compatible neutral detection
    neutral_aliases = {"neutral", "معمولی", "خنثی"}
    normalized_labels = [str(lbl).strip().lower() for lbl in sentiment_labels if lbl is not None]

    all_neutral = bool(normalized_labels) and all(
        (lbl in neutral_aliases) or (lbl == "خنثی")
        for lbl in normalized_labels
    )

    if all_neutral and not has_emotion:
        return error_response("E06")

    return None
