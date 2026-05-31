from pydantic import BaseModel
from typing import List, Optional, Dict, Literal


class SegmentBase(BaseModel):
    speaker: str
    start: float
    end: float
    text: Optional[str] = None
    role: Optional[str] = None  # operator or customer


class TranscriptionResponse(BaseModel):
    call_id: str
    segments: List[SegmentBase]


class SilenceSegmentInfo(BaseModel):
    start: float
    end: float
    duration: float


class SilenceResponse(BaseModel):
    call_id: str
    silence_duration_seconds: float
    silence_duration_mmss: str
    silence_percent_total_call: float
    silence_segments: List[SilenceSegmentInfo]

class SilenceFromSegmentsRequest(BaseModel):
    call_id: str
    segments: List[SegmentBase]
    total_duration: Optional[float] = None
    silence_threshold: Optional[float] = None


class OverlapMetrics(BaseModel):
    overlap_count: int
    total_overlap_duration_sec: float
    overlap_percentage: float


class OverlapResponse(BaseModel):
    call_id: str
    metrics: OverlapMetrics
    overlap_blocks: List[dict]


class STTSegment(BaseModel):
    speaker: str
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class DetectionRequest(BaseModel):
    transcript: List[STTSegment]
    model: Optional[str] = None


class DetectionError(BaseModel):
    behavior: Optional[str] = None
    code: str
    message: str


class DetectionResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Optional[int]]] = None
    errors: Optional[List[DetectionError]] = None


class OrchestratedBehaviorResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Optional[int]]] = None
    errors: Optional[List[DetectionError]] = None
    call_id: Optional[str] = None


class SentimentAnalyzeRequest(BaseModel):
    conversation: str


class SentimentAnalyzeResponse(BaseModel):
    sentiment: Optional[str] = None
    error: Optional[str] = None


class OperatorScoreUtterance(BaseModel):
    speaker: Literal["operator", "customer"]
    start_time: float
    end_time: float
    text: str


class OperatorScoreRequest(BaseModel):
    conversation_id: str
    utterances: List[OperatorScoreUtterance]


class OperatorScoreResponse(BaseModel):
    politeness_score: int
    anger_control_score: int
    problem_solving_score: int