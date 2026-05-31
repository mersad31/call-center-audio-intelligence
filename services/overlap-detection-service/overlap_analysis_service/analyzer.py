"""Deterministic overlap analysis for two-party call-center conversations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

Role = Literal["operator", "customer"]

OVERLAP_THRESHOLD_SEC = 0.5
MERGE_GAP_SEC = 0.3
_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class SpeechSegment:
    start_sec: float
    end_sec: float
    speaker: Role


@dataclass(frozen=True, slots=True)
class OverlapInterval:
    start_sec: float
    end_sec: float

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec


@dataclass(frozen=True, slots=True)
class OverlapAnalysis:
    raw_overlaps: tuple[OverlapInterval, ...]
    filtered_overlaps: tuple[OverlapInterval, ...]
    merged_blocks: tuple[OverlapInterval, ...]


def analyze_overlaps(
    segments: Iterable[SpeechSegment],
    overlap_threshold_sec: float = OVERLAP_THRESHOLD_SEC,
    merge_gap_sec: float = MERGE_GAP_SEC,
) -> OverlapAnalysis:
    """Find customer/operator overlap blocks from already role-mapped segments."""
    by_role: dict[Role, list[OverlapInterval]] = {"operator": [], "customer": []}
    for segment in segments:
        by_role[segment.speaker].append(OverlapInterval(segment.start_sec, segment.end_sec))

    operator_intervals = _coalesce_intervals(by_role["operator"])
    customer_intervals = _coalesce_intervals(by_role["customer"])
    raw_overlaps = _intersect_intervals(operator_intervals, customer_intervals)
    filtered = tuple(
        interval
        for interval in raw_overlaps
        if interval.duration_sec + _EPSILON >= overlap_threshold_sec
    )
    merged = _merge_nearby_overlaps(filtered, merge_gap_sec)
    return OverlapAnalysis(raw_overlaps=raw_overlaps, filtered_overlaps=filtered, merged_blocks=merged)


def _coalesce_intervals(intervals: Iterable[OverlapInterval]) -> tuple[OverlapInterval, ...]:
    ordered = sorted(intervals, key=lambda interval: (interval.start_sec, interval.end_sec))
    if not ordered:
        return ()

    merged: list[OverlapInterval] = [ordered[0]]
    for current in ordered[1:]:
        previous = merged[-1]
        if current.start_sec <= previous.end_sec + _EPSILON:
            merged[-1] = OverlapInterval(previous.start_sec, max(previous.end_sec, current.end_sec))
        else:
            merged.append(current)
    return tuple(merged)


def _intersect_intervals(
    operator_intervals: tuple[OverlapInterval, ...],
    customer_intervals: tuple[OverlapInterval, ...],
) -> tuple[OverlapInterval, ...]:
    overlaps: list[OverlapInterval] = []
    operator_index = 0
    customer_index = 0

    while operator_index < len(operator_intervals) and customer_index < len(customer_intervals):
        operator_interval = operator_intervals[operator_index]
        customer_interval = customer_intervals[customer_index]
        start_sec = max(operator_interval.start_sec, customer_interval.start_sec)
        end_sec = min(operator_interval.end_sec, customer_interval.end_sec)

        if end_sec > start_sec + _EPSILON:
            overlaps.append(OverlapInterval(start_sec, end_sec))

        if operator_interval.end_sec <= customer_interval.end_sec + _EPSILON:
            operator_index += 1
        else:
            customer_index += 1

    return tuple(overlaps)


def _merge_nearby_overlaps(
    intervals: Iterable[OverlapInterval],
    merge_gap_sec: float,
) -> tuple[OverlapInterval, ...]:
    ordered = sorted(intervals, key=lambda interval: (interval.start_sec, interval.end_sec))
    if not ordered:
        return ()

    merged: list[OverlapInterval] = [ordered[0]]
    for current in ordered[1:]:
        previous = merged[-1]
        gap_sec = current.start_sec - previous.end_sec
        if gap_sec < merge_gap_sec - _EPSILON:
            merged[-1] = OverlapInterval(previous.start_sec, max(previous.end_sec, current.end_sec))
        else:
            merged.append(current)
    return tuple(merged)
