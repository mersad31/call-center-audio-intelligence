# app/domain/models.py
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.domain.behaviors import BehaviorName


class STTSegment(BaseModel):
    speaker: str
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class DetectionRequest(BaseModel):
    transcript: List[STTSegment]
    model: Optional[str] = None


class DetectionError(BaseModel):
    behavior: Optional[BehaviorName] = None
    code: str
    message: str


class DetectionResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Optional[int]]] = None
    errors: Optional[List[DetectionError]] = None
