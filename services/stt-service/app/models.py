from typing import List, Optional
from pydantic import BaseModel, Field, model_validator, ConfigDict


class STTSegmentIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    speaker: str = Field(..., description="operator یا customer")
    start: str = Field(..., description="زمان شروع در فرمت MM:SS یا HH:MM:SS (ms اختیاری)")
    end: str = Field(..., description="زمان پایان در فرمت MM:SS یا HH:MM:SS (ms اختیاری)")


class STTRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    audio_path: Optional[str] = Field(
        None, description="مسیر فایل روی سرور، مثلا /data/calls/call_001.wav"
    )
    audio_url: Optional[str] = Field(
        None, description="اگر فایل روی object storage است، URL آن"
    )
    segments: List[STTSegmentIn] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_audio_source(self):
        if not self.audio_path and not self.audio_url:
            raise ValueError("یکی از audio_path یا audio_url الزامی است")
        return self


class STTSegmentOut(BaseModel):
    speaker: str
    start: str
    end: str
    text: str


class STTResponse(BaseModel):
    success: bool
    segments: List[STTSegmentOut]


SegmentsRequest = STTRequest
OutputSegment = STTSegmentOut
OutputResponse = STTResponse
