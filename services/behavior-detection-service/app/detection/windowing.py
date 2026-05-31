#app/detection/windowing.py
from typing import List
from app.domain.models import STTSegment

def window_segments(segments: List[STTSegment], start_ratio: float, end_ratio: float):
    if not segments:
        return []

    total = len(segments)
    start = int(total * start_ratio)
    end = int(total * end_ratio)

    return segments[start:end]