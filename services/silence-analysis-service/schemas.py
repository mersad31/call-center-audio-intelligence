from typing import List, Optional
from pydantic import BaseModel, Field


class SegmentInfo(BaseModel):
    speaker: str = Field(..., description="Speaker label, e.g. SPEAKER_00")
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")


class SpeakerInfo(BaseModel):
    speaker_id: Optional[str] = Field(None, description="Speaker label")
    total_time: float = Field(0.0, description="Total speaking time in seconds")
    first_speech_time: float = Field(0.0, description="First speech timestamp in seconds")
    number_of_turns: int = Field(0, description="Number of speaking turns")


class SilenceSegment(BaseModel):
    start: float = Field(..., description="Silence start time in seconds")
    end: float = Field(..., description="Silence end time in seconds")
    duration: float = Field(..., description="Silence duration in seconds")


class SilenceResponse(BaseModel):
    call_id: str
    total_duration: float
    operator: SpeakerInfo
    customer: SpeakerInfo
    segments: List[SegmentInfo]
    silence_duration_seconds: float
    silence_duration_mmss: str
    silence_percent_total_call: float
    silence_percent_operator_time: float
    silence_segments: List[SilenceSegment]
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    service: str



class RoleSegmentInfo(BaseModel):
    speaker: str = Field(..., description="Speaker label, e.g. SPEAKER_00")
    start: float = Field(..., description="Segment start time in seconds")
    end: float = Field(..., description="Segment end time in seconds")
    text: Optional[str] = Field(None, description="Transcript text (optional)")
    role: Optional[str] = Field(None, description="Role label e.g. operator/customer (optional)")


class SilenceFromSegmentsRequest(BaseModel):
    call_id: str
    segments: List[RoleSegmentInfo]
    total_duration: Optional[float] = Field(
        None, description="Total call duration seconds. If omitted, inferred from segments."
    )
    silence_threshold: Optional[float] = Field(
        None, description="Override silence threshold in seconds."
    )


class SilenceFromSegmentsResponse(BaseModel):
    call_id: str
    total_duration: float
    operator_total_time: float
    silence_duration_seconds: float
    silence_duration_mmss: str
    silence_percent_total_call: float
    silence_percent_operator_time: float
    silence_segments: List[SilenceSegment]
    timestamp: str
