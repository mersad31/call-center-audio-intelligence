#app/preprocessing/operator_filter.py
from typing import List
from app.domain.models import STTSegment

def extract_operator_speech(segments: List[STTSegment]) -> List[STTSegment]:
    return [s for s in segments if s.speaker.lower() == "operator"]