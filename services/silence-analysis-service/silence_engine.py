from typing import Dict, List


def format_mmss(seconds: float) -> str:
    total_seconds = int(round(seconds))
    minutes = total_seconds // 60
    remaining_seconds = total_seconds % 60
    return f"{minutes:02d}:{remaining_seconds:02d}"


def round_float(value: float, digits: int = 3) -> float:
    return round(float(value), digits)


def calculate_operator_silence(
    segments: List[Dict],
    operator_speaker: str,
    total_duration: float,
    operator_total_time: float,
    silence_threshold: float = 1.0,
) -> Dict:
    if not operator_speaker:
        return {
            "silence_duration_seconds": 0.0,
            "silence_duration_mmss": "00:00",
            "silence_percent_total_call": 0.0,
            "silence_percent_operator_time": 0.0,
            "silence_segments": [],
        }

    sorted_segments = sorted(
        segments,
        key=lambda x: (float(x["start"]), float(x["end"]))
    )

    operator_segments = [
        seg for seg in sorted_segments if seg["speaker"] == operator_speaker
    ]

    if len(operator_segments) < 2:
        return {
            "silence_duration_seconds": 0.0,
            "silence_duration_mmss": "00:00",
            "silence_percent_total_call": 0.0,
            "silence_percent_operator_time": 0.0,
            "silence_segments": [],
        }

    silence_segments = []

    for idx in range(len(operator_segments) - 1):
        current_seg = operator_segments[idx]
        next_seg = operator_segments[idx + 1]

        gap_start = float(current_seg["end"])
        gap_end = float(next_seg["start"])
        gap_duration = gap_end - gap_start

        if gap_duration <= 0:
            continue

        if gap_duration < silence_threshold:
            continue

        has_overlap = False
        for seg in sorted_segments:
            seg_start = float(seg["start"])
            seg_end = float(seg["end"])

            if seg_end <= gap_start or seg_start >= gap_end:
                continue

            has_overlap = True
            break

        if not has_overlap:
            silence_segments.append(
                {
                    "start": round_float(gap_start),
                    "end": round_float(gap_end),
                    "duration": round_float(gap_duration),
                }
            )

    total_silence = round_float(sum(item["duration"] for item in silence_segments))
    silence_percent_total_call = (
        round_float((total_silence / total_duration) * 100, 3)
        if total_duration > 0 else 0.0
    )
    silence_percent_operator_time = (
        round_float((total_silence / operator_total_time) * 100, 3)
        if operator_total_time > 0 else 0.0
    )

    return {
        "silence_duration_seconds": total_silence,
        "silence_duration_mmss": format_mmss(total_silence),
        "silence_percent_total_call": silence_percent_total_call,
        "silence_percent_operator_time": silence_percent_operator_time,
        "silence_segments": silence_segments,
    }
