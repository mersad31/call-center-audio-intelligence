"""API schemas for the standalone overlap analysis service."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["operator", "customer"]


class SegmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_sec: float = Field(..., ge=0)
    end_sec: float = Field(..., ge=0)
    speaker: Role
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("start_sec", "end_sec", "confidence")
    @classmethod
    def values_must_be_finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("numeric values must be finite")
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "SegmentInput":
        if self.end_sec <= self.start_sec:
            raise ValueError("end_sec must be greater than start_sec")
        return self


class OverlapAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str = Field(..., min_length=1)
    audio_duration_sec: float = Field(..., gt=0)
    segments: list[SegmentInput] = Field(default_factory=list)

    @field_validator("audio_duration_sec")
    @classmethod
    def duration_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("audio_duration_sec must be finite")
        return value


class Metrics(BaseModel):
    overlap_count: int
    total_overlap_duration_sec: float
    overlap_percentage: float


class OverlapBlock(BaseModel):
    block_id: int
    start_sec: float
    end_sec: float
    duration_sec: float


class OverlapAnalysisResponse(BaseModel):
    call_id: str
    call_duration_sec: float
    overlap_threshold_ms: int
    merge_gap_ms: int
    metrics: Metrics
    overlap_blocks: list[OverlapBlock]
    processing_timestamp: str
