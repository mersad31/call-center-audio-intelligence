# role_detection_api/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import re

# ==============================================================================
# 1. Configuration & Keywords
# ==============================================================================

# نکته: این لیست‌ها باید با دیالوگ‌های واقعی اپراتور همخوان باشند.
# از نمونه‌ی شما: «سلام وقتتون خیر... چطور میتونم کمکتون کنم؟»، «مرسی برای تماس...»
OPERATOR_KEYWORDS = [
    # عمومی/اداری
    "پشتیبانی", "پشتیبان", "کارشناس",
    "در خدمتم", "در خدمتتون", "در خدمت شما",
    "لطفا", "لطفاً", "خواهشمند",

    # شروع مکالمه
    "سلام",
    "وقت بخیر", "وقتتون بخیر", "وقتتون خیر",

    # جملات اپراتوری رایج
    "چطور میتونم کمکتون کنم",
    "چطور می‌تونم کمکتون کنم",
    "چطور می تونم کمکتون کنم",
    "چطور میتونم کمک کنم",
    "چطور می‌تونم کمک کنم",
    "بفرمایید",
    "راهنمایی", "کمکتون کنم", "کمک کنم",

    # جمع‌آوری اطلاعات/سیستمی
    "شماره", "کد ملی", "سیستم", "پرونده", "ثبت", "بررسی",
    "در سیستم", "ثبت شد", "در حال بررسی",

    # پایان مکالمه
    "مرسی برای تماس",
    "ممنون از تماس",
]

FORMAL_PATTERNS = [
    "در خدمتم",
    "در خدمتتون",
    "لطفا",
    "لطفاً",
    "خواهشمند",
    "اطلاعات شما",
    "در سیستم",
    "ثبت شد",
    "در حال بررسی",
    "وقت بخیر",
    "وقتتون بخیر",
    "وقتتون خیر",
    "چطور میتونم کمکتون کنم",
    "چطور می‌تونم کمکتون کنم",
    "بفرمایید",
    "مرسی برای تماس",
    "ممنون از تماس",
]

# اگر خواستی می‌تونی وزن‌ها رو هم بعداً تنظیم کنی
KEYWORD_WEIGHT = 1
FORMAL_PATTERN_BONUS = 2  # به جای 1، اثرگذارتر می‌کنیم


# ==============================================================================
# 2. Pydantic Schemas for the API
# ==============================================================================

class SegmentInput(BaseModel):
    """
    Represents a single speech segment.
    'text' is optional. If called before STT, pass an empty string.
    """
    speaker: str = Field(..., description="Speaker identifier (e.g., SPEAKER_00)")
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: Optional[str] = Field(default="", description="Transcribed text (if available)")


class RoleDetectionRequest(BaseModel):
    segments: List[SegmentInput]


class SpeakerStats(BaseModel):
    speaker_id: str
    total_speech_time: float
    first_speech_time: float
    number_of_turns: int
    avg_segment_length: float


class RoleDetectionResponse(BaseModel):
    operator_id: Optional[str]
    customer_id: Optional[str]
    metrics: Dict[str, SpeakerStats]


# ==============================================================================
# 3. Core Logic Functions
# ==============================================================================

def normalize_fa(text: str) -> str:
    """
    Normalize Persian/Arabic variants and whitespace so keyword matching works better.
    """
    if not text:
        return ""
    t = text.strip()
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = t.replace("\u200c", " ")  # ZWNJ -> space
    t = re.sub(r"\s+", " ", t)
    return t


def compute_content_scores(segments: List[SegmentInput]) -> Dict[str, int]:
    """
    Computes scores based on the presence of operator-specific keywords
    and formal patterns in the transcribed text.
    """
    scores: Dict[str, int] = {}
    speaker_texts: Dict[str, str] = {}

    # Concatenate all text for each speaker
    for seg in segments:
        spk = (seg.speaker or "").strip()
        if not spk:
            continue

        txt = normalize_fa(seg.text or "")
        if spk not in speaker_texts:
            speaker_texts[spk] = ""

        if txt:
            speaker_texts[spk] += (" " + txt)

    # Score based on keywords and formal patterns
    for spk, full_text in speaker_texts.items():
        text = normalize_fa(full_text)
        if not text:
            scores[spk] = 0
            continue

        score = 0

        # Count individual keywords (simple but effective)
        for kw in OPERATOR_KEYWORDS:
            kw_n = normalize_fa(kw)
            if not kw_n:
                continue
            score += text.count(kw_n) * KEYWORD_WEIGHT

        # Add bonus points for EACH matched formal phrase (not just any)
        matched_formals = 0
        for p in FORMAL_PATTERNS:
            p_n = normalize_fa(p)
            if p_n and (p_n in text):
                matched_formals += 1
        score += matched_formals * FORMAL_PATTERN_BONUS

        scores[spk] = score

    return scores


def compute_metrics(segments: List[SegmentInput]) -> Dict[str, Dict]:
    """
    Calculates acoustic/time-based metrics for each speaker:
    total time, first speech time, turn counts, etc.
    """
    metrics: Dict[str, Dict] = {}

    for idx, seg in enumerate(segments):
        speaker = (seg.speaker or "").strip()
        start = float(seg.start or 0.0)
        end = float(seg.end or 0.0)

        if end < start:
            start, end = end, start

        duration = end - start
        if duration <= 0:
            continue

        if not speaker:
            continue

        # Initialize metrics for a new speaker
        if speaker not in metrics:
            metrics[speaker] = {
                "total_speech_time": 0.0,
                "first_speech_time": start,
                "number_of_turns": 0,
                "avg_segment_length": 0.0,
                "first_segment_index": idx,
            }

        m = metrics[speaker]
        m["total_speech_time"] += duration
        m["first_speech_time"] = min(m["first_speech_time"], start)
        m["number_of_turns"] += 1

    # Calculate averages
    for _, m in metrics.items():
        if m["number_of_turns"] > 0:
            m["avg_segment_length"] = m["total_speech_time"] / m["number_of_turns"]

    return metrics


def decide_operator(metrics: Dict[str, Dict], segments: List[SegmentInput]) -> Optional[str]:
    """
    Determines the operator by combining time-based rule scores and content scores.
    """
    if not metrics:
        return None

    speakers = list(metrics.keys())

    first_idx = min(metrics[s]["first_segment_index"] for s in speakers)
    max_total = max(metrics[s]["total_speech_time"] for s in speakers)
    max_turns = max(metrics[s]["number_of_turns"] for s in speakers)

    # 1) Time-based rule scoring
    rule_scores: Dict[str, int] = {s: 0 for s in speakers}
    for s in speakers:
        if metrics[s]["first_segment_index"] == first_idx:
            rule_scores[s] += 2  # spoke first
        if metrics[s]["total_speech_time"] == max_total:
            rule_scores[s] += 2  # spoke most
        if metrics[s]["number_of_turns"] == max_turns:
            rule_scores[s] += 1  # most turns

    # 2) Content-based scoring
    content_scores = compute_content_scores(segments)

    # 3) Combine
    total_scores: Dict[str, int] = {}
    for s in speakers:
        total_scores[s] = rule_scores.get(s, 0) + content_scores.get(s, 0)

    # Debug-ish safety: if everyone has 0 content, we still rank by rules.
    ranked = sorted(
        speakers,
        key=lambda s: (
            total_scores[s],                  # highest combined score
            content_scores.get(s, 0),          # prefer content when available
            rule_scores.get(s, 0),             # then acoustic rules
            metrics[s]["total_speech_time"],   # most speech time
            -metrics[s]["first_speech_time"],  # earliest to speak
            s,                                 # stable fallback
        ),
        reverse=True,
    )

    return ranked[0] if ranked else None


# ==============================================================================
# 4. FastAPI Setup & Endpoints
# ==============================================================================

app = FastAPI(
    title="Role Detection Service",
    description="Standalone microservice to identify Operator and Customer from call segments.",
    version="1.1.0"
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "role_detection"}


@app.post("/detect", response_model=RoleDetectionResponse)
async def detect_roles_endpoint(request: RoleDetectionRequest):
    if not request.segments:
        raise HTTPException(status_code=400, detail="Segments list cannot be empty.")

    # sort segments by start time
    sorted_segments = sorted(request.segments, key=lambda x: float(x.start or 0.0))

    metrics = compute_metrics(sorted_segments)
    if not metrics:
        return RoleDetectionResponse(operator_id=None, customer_id=None, metrics={})

    operator_id = decide_operator(metrics, sorted_segments)

    customer_id = None
    if operator_id:
        remaining = [s for s in metrics.keys() if s != operator_id]
        if remaining:
            customer_id = max(remaining, key=lambda s: metrics[s]["total_speech_time"])

    response_metrics: Dict[str, SpeakerStats] = {}
    for spk, m in metrics.items():
        response_metrics[spk] = SpeakerStats(
            speaker_id=spk,
            total_speech_time=round(m["total_speech_time"], 3),
            first_speech_time=round(m["first_speech_time"], 3),
            number_of_turns=int(m["number_of_turns"]),
            avg_segment_length=round(m["avg_segment_length"], 3),
        )

    return RoleDetectionResponse(
        operator_id=operator_id,
        customer_id=customer_id,
        metrics=response_metrics,
    )
