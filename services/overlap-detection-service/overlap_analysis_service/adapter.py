"""Adapter contract for converting Aggregator output into overlap-analysis input.

This module intentionally contains no overlap detection, merging, or counting logic.
It only maps Aggregator speaker IDs to the provided logical roles.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from overlap_analysis_service.schemas import OverlapAnalysisRequest, SegmentInput

Role = Literal["operator", "customer"]


class AggregatorRole(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speaker_id: str = Field(..., min_length=1)


class AggregatorSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speaker: str = Field(..., min_length=1)
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    text: str = ""

    @field_validator("start", "end")
    @classmethod
    def values_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("segment times must be finite")
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "AggregatorSegment":
        if self.end <= self.start:
            raise ValueError("segment end must be greater than start")
        return self


class AggregatorOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    call_id: str = Field(..., min_length=1)
    operator: AggregatorRole | None = None
    customer: AggregatorRole | None = None
    segments: list[AggregatorSegment] = Field(default_factory=list)

    @model_validator(mode="after")
    def roles_must_be_available_and_distinct(self) -> "AggregatorOutput":
        if self.operator is None or self.customer is None:
            raise ValueError("operator and customer speaker mappings are required")
        if self.operator.speaker_id == self.customer.speaker_id:
            raise ValueError("operator and customer speaker IDs must be distinct")
        return self


class AggregatorToOverlapAdapter:
    """Converts Aggregator /process output to the overlap service input contract."""

    def to_overlap_request(
        self,
        aggregator_output: AggregatorOutput | dict[str, Any],
        audio_duration_sec: float,
    ) -> OverlapAnalysisRequest:
        parsed = (
            aggregator_output
            if isinstance(aggregator_output, AggregatorOutput)
            else AggregatorOutput.model_validate(aggregator_output)
        )
        if not math.isfinite(audio_duration_sec) or audio_duration_sec <= 0:
            raise ValueError("audio_duration_sec must be a positive finite number")

        role_by_speaker_id = self._role_mapping(parsed)
        adapted_segments = [
            SegmentInput(
                start_sec=segment.start,
                end_sec=segment.end,
                speaker=role_by_speaker_id[segment.speaker],
            )
            for segment in parsed.segments
            if segment.speaker in role_by_speaker_id
        ]

        return OverlapAnalysisRequest(
            call_id=parsed.call_id,
            audio_duration_sec=audio_duration_sec,
            segments=adapted_segments,
        )

    @staticmethod
    def _role_mapping(aggregator_output: AggregatorOutput) -> dict[str, Role]:
        if aggregator_output.operator is None or aggregator_output.customer is None:
            raise ValueError("operator and customer speaker mappings are required")
        return {
            aggregator_output.operator.speaker_id: "operator",
            aggregator_output.customer.speaker_id: "customer",
        }
