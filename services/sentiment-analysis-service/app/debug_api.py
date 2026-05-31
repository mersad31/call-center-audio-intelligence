# app/debug_api.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .preprocessing import preprocess_conversation
from .rules import validate_input, validate_emotional_content
from .sentiment_model import SentimentModel
from . import scoring
from .request_id import get_request_id


def analyze_messages(messages: List[str], raw_text: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(messages, list):
        return {"error": "messages must be a list of strings"}

    if not messages:
        return {"error": "empty message list"}

    joined_text = raw_text if raw_text is not None else "\n".join(messages)

    err = validate_input(joined_text, messages)
    if err:
        return {"error": err}

    try:
        model = SentimentModel()
        labels = model.predict(messages)
    except Exception as e:
        return {"error": f"model prediction failed: {repr(e)}"}

    try:
        err = validate_emotional_content(messages, labels)
        if err:
            return {"error": err}
    except Exception as e:
        return {"error": f"emotional validation failed: {repr(e)}"}

    try:
        conversation_label, conversation_detail = scoring.score_messages(messages, debug=True)
        conversation_score = conversation_detail.get("aggregate_score", 0.0)
        conversation_sentiment = conversation_label
    except Exception as e:
        return {"error": f"conversation scoring failed: {repr(e)}"}

    message_debug = _build_message_debug(messages, labels)

    last_debug = _safe_get_last(message_debug, default={
        "index": None,
        "text": None,
        "model_label": "خنثی",
        "message_score": 0.0,
        "base_score": 0.0,
        "token_score": 0.0,
        "phrase_score": 0.0,
        "normalized_text": None,
        "reasons": [],
        "raw_detail": None,
    })

    # تزریق کانتکستِ تفکیک‌شده به ساختار دیکشنری دیتای دیباگ
    return {
        "ok": True,
        "request_id": get_request_id(),  # این بخش شناسه جاری را به آرایه لاگ‌های قدیمی شما اضافه می‌کند
        "input_raw": raw_text,
        "messages": messages,
        "model_labels": labels,
        "conversation_score": conversation_score,
        "conversation_sentiment": conversation_sentiment,
        "conversation_detail": conversation_detail,
        "message_debug": message_debug,
        "last_message_detail": {
            "text": last_debug.get("text"),
            "model_label": last_debug.get("model_label"),
            "score": last_debug.get("message_score"),
            "base_score": last_debug.get("base_score"),
            "token_score": last_debug.get("token_score"),
            "phrase_score": last_debug.get("phrase_score"),
            "normalized_text": last_debug.get("normalized_text"),
            "reasons": last_debug.get("reasons"),
            "raw": last_debug.get("raw_detail"),
        },
    }


def _safe_get_last(items: List[Any], default: Any = None) -> Any:
    return items[-1] if items else default


def _get_sentiment_label_fn():
    """
    سازگاری با نسخه‌های مختلف scoring.py
    """
    if hasattr(scoring, "sentiment_label"):
        return scoring.sentiment_label
    if hasattr(scoring, "map_final_sentiment"):
        return scoring.map_final_sentiment
    if hasattr(scoring, "_normalize_score_to_label"):
        return scoring._normalize_score_to_label

    def _fallback(score: float) -> str:
        if score >= 1.75:
            return "عالی"
        if score >= 0.55:
            return "خوب"
        if score <= -2.0:
            return "خیلی ناراضی"
        if score <= -0.55:
            return "ناراضی"
        return "خنثی"

    return _fallback


def _score_single_message(text: str, label: str | None = None) -> Dict[str, Any]:
    """
    برای سازگاری با نسخه‌های مختلف scoring.py
    """
    if hasattr(scoring, "score_message_with_reasons"):
        try:
            detail = scoring.score_message_with_reasons(text)
            if isinstance(detail, dict):
                return detail
        except TypeError:
            # fallback برای نسخه‌های خیلی قدیمی
            try:
                detail = scoring.score_message_with_reasons(text, label)
                if isinstance(detail, dict):
                    return detail
            except Exception as e:
                return {
                    "score": 0.0,
                    "base_score": 0.0,
                    "token_score": 0.0,
                    "phrase_score": 0.0,
                    "normalized_text": text,
                    "reasons": [],
                    "raw_detail": {"error": repr(e), "source": "score_message_with_reasons"},
                }
        except Exception as e:
            return {
                "score": 0.0,
                "base_score": 0.0,
                "token_score": 0.0,
                "phrase_score": 0.0,
                "normalized_text": text,
                "reasons": [],
                "raw_detail": {"error": repr(e), "source": "score_message_with_reasons"},
            }

    if hasattr(scoring, "score_text"):
        try:
            result = scoring.score_text(text, debug=True)

            if isinstance(result, tuple) and len(result) == 2:
                label_out, detail = result
                if isinstance(detail, dict):
                    return {
                        "score": detail.get("final_score", 0.0),
                        "base_score": detail.get("base_score", 0.0),
                        "token_score": detail.get("token_score", 0.0),
                        "phrase_score": detail.get("phrase_score", 0.0),
                        "normalized_text": detail.get("normalized_text", text),
                        "label": detail.get("label", label_out),
                        "reasons": detail.get("reasons", []),
                        "raw_detail": detail,
                    }

            if isinstance(result, (int, float)):
                return {
                    "score": float(result),
                    "base_score": float(result),
                    "token_score": 0.0,
                    "phrase_score": 0.0,
                    "normalized_text": text,
                    "reasons": ["fallback: numeric score_text"],
                    "raw_detail": {"source": "score_text_numeric"},
                }

        except Exception as e:
            return {
                "score": 0.0,
                "base_score": 0.0,
                "token_score": 0.0,
                "phrase_score": 0.0,
                "normalized_text": text,
                "reasons": [],
                "raw_detail": {"error": repr(e), "source": "score_text"},
            }

    return {
        "score": 0.0,
        "base_score": 0.0,
        "token_score": 0.0,
        "phrase_score": 0.0,
        "normalized_text": text,
        "reasons": ["fallback: no scoring detail function found"],
        "raw_detail": {"source": "fallback"},
    }


def _normalize_debug_detail(detail: Any) -> Dict[str, Any]:
    if detail is None:
        return {
            "score": 0.0,
            "base_score": 0.0,
            "token_score": 0.0,
            "phrase_score": 0.0,
            "reasons": [],
            "normalized_text": None,
            "raw": None,
        }

    if isinstance(detail, dict):
        score = detail.get("score", detail.get("final_score", 0.0))
        base_score = detail.get("base_score", score)
        raw_obj = detail.get("raw_detail", detail)

        return {
            "score": score,
            "base_score": base_score,
            "token_score": detail.get("token_score", 0.0),
            "phrase_score": detail.get("phrase_score", 0.0),
            "reasons": detail.get("reasons", []),
            "normalized_text": detail.get("normalized_text"),
            "raw": raw_obj,
        }

    return {
        "score": 0.0,
        "base_score": 0.0,
        "token_score": 0.0,
        "phrase_score": 0.0,
        "reasons": [],
        "normalized_text": None,
        "raw": detail,
    }


def _build_message_debug(
    messages: List[str],
    labels: List[str],
) -> List[Dict[str, Any]]:
    debug_rows: List[Dict[str, Any]] = []

    for idx, text in enumerate(messages):
        label = labels[idx] if idx < len(labels) else "خنثی"

        try:
            detail = _score_single_message(text, label)
            detail_norm = _normalize_debug_detail(detail)
        except Exception as e:
            detail_norm = {
                "score": 0.0,
                "base_score": 0.0,
                "token_score": 0.0,
                "phrase_score": 0.0,
                "reasons": [],
                "normalized_text": None,
                "raw": {"error": repr(e)},
            }

        debug_rows.append({
            "index": idx,
            "text": text,
            "model_label": label,
            "message_score": detail_norm["score"],
            "base_score": detail_norm["base_score"],
            "token_score": detail_norm["token_score"],
            "phrase_score": detail_norm["phrase_score"],
            "normalized_text": detail_norm["normalized_text"],
            "reasons": detail_norm["reasons"],
            "raw_detail": detail_norm["raw"],
        })

    return debug_rows


def analyze_messages(messages: List[str], raw_text: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(messages, list):
        return {"error": "messages must be a list of strings"}

    if not messages:
        return {"error": "empty message list"}

    joined_text = raw_text if raw_text is not None else "\n".join(messages)

    err = validate_input(joined_text, messages)
    if err:
        return {"error": err}

    try:
        model = SentimentModel()
        labels = model.predict(messages)
    except Exception as e:
        return {"error": f"model prediction failed: {repr(e)}"}

    try:
        err = validate_emotional_content(messages, labels)
        if err:
            return {"error": err}
    except Exception as e:
        return {"error": f"emotional validation failed: {repr(e)}"}

    try:
        conversation_label, conversation_detail = scoring.score_messages(messages, debug=True)
        conversation_score = conversation_detail.get("aggregate_score", 0.0)
        conversation_sentiment = conversation_label
    except Exception as e:
        return {"error": f"conversation scoring failed: {repr(e)}"}

    message_debug = _build_message_debug(messages, labels)

    last_debug = _safe_get_last(message_debug, default={
        "index": None,
        "text": None,
        "model_label": "خنثی",
        "message_score": 0.0,
        "base_score": 0.0,
        "token_score": 0.0,
        "phrase_score": 0.0,
        "normalized_text": None,
        "reasons": [],
        "raw_detail": None,
    })

    return {
        "ok": True,
        "input_raw": raw_text,
        "messages": messages,
        "model_labels": labels,
        "conversation_score": conversation_score,
        "conversation_sentiment": conversation_sentiment,
        "conversation_detail": conversation_detail,
        "message_debug": message_debug,
        "last_message_detail": {
            "text": last_debug.get("text"),
            "model_label": last_debug.get("model_label"),
            "score": last_debug.get("message_score"),
            "base_score": last_debug.get("base_score"),
            "token_score": last_debug.get("token_score"),
            "phrase_score": last_debug.get("phrase_score"),
            "normalized_text": last_debug.get("normalized_text"),
            "reasons": last_debug.get("reasons"),
            "raw": last_debug.get("raw_detail"),
        },
    }


def analyze_single_utterance(text: str) -> Dict[str, Any]:
    if text is None:
        return {"error": "text is None"}

    if not isinstance(text, str):
        return {"error": "text must be a string"}

    stripped = text.strip()
    if not stripped:
        return {"error": "empty text"}

    try:
        messages = preprocess_conversation(stripped)
    except Exception as e:
        return {"error": f"preprocessing failed: {repr(e)}"}

    return analyze_messages(messages, raw_text=stripped)


def analyze_batch(texts: List[str]) -> Dict[str, Any]:
    if not isinstance(texts, list):
        return {"error": "texts must be a list of strings"}

    results: List[Dict[str, Any]] = []
    for i, text in enumerate(texts):
        try:
            result = analyze_single_utterance(text)
            result["_batch_index"] = i
            results.append(result)
        except Exception as e:
            results.append({
                "_batch_index": i,
                "error": repr(e),
                "input_raw": text,
            })

    return {
        "ok": True,
        "total": len(texts),
        "results": results,
    }
