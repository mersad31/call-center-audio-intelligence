import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.diarization.model_loader import get_diarization_pipeline
from app.logger import setup_logger

logger = setup_logger("diarization_service")

GAP_THRESHOLD = 0.5          # seconds — merge same-speaker segments closer than this
MIN_SEGMENT_DURATION = 0.3   # seconds — skip segments shorter than this


class DiarizationService:
    """
    Only diarization:
    - No STT
    - No Audio Cutter
    """

    def __init__(self):
        self.pipeline = get_diarization_pipeline()
        logger.info("DiarizationService initialized")

    def _run_diarization(
        self,
        audio_path: str,
        num_speakers: int,
        speaker_sample_paths: Optional[List[str]] = None,
    ):
        """Run pyannote diarization (CPU/GPU bound)."""
        logger.info(f"Running diarization | speakers={num_speakers} | file={Path(audio_path).name}")

        kwargs = {
            "min_speakers": num_speakers,
            "max_speakers": num_speakers,
        }

        # Optional speaker profiles (if provided)
        if speaker_sample_paths:
            logger.info(f"Using {len(speaker_sample_paths)} speaker reference samples")
            from pyannote.audio import Audio
            audio_loader = Audio(sample_rate=16000, mono=True)
            profiles = {}
            for i, sample_path in enumerate(speaker_sample_paths):
                waveform, sr = audio_loader(sample_path)
                profiles[f"Speaker_{i + 1}"] = waveform
            kwargs["speaker_profiles"] = profiles

        annotation = self.pipeline(audio_path, **kwargs)
        logger.info("Diarization complete")
        return annotation

    def _extract_and_group_segments(self, annotation) -> List[Dict]:
        """Extract segments and merge consecutive turns of the same speaker."""
        raw = sorted(
            [
                {"start": seg.start, "end": seg.end, "speaker": label}
                for seg, _, label in annotation.itertracks(yield_label=True)
                if (seg.end - seg.start) >= MIN_SEGMENT_DURATION
            ],
            key=lambda x: x["start"],
        )

        if not raw:
            return []

        grouped = []
        current = raw[0].copy()

        for seg in raw[1:]:
            same_speaker = seg["speaker"] == current["speaker"]
            small_gap = (seg["start"] - current["end"]) < GAP_THRESHOLD
            if same_speaker and small_gap:
                current["end"] = seg["end"]
            else:
                grouped.append(current)
                current = seg.copy()
        grouped.append(current)

        logger.info(f"Segments: {len(raw)} raw → {len(grouped)} grouped")
        return grouped

    @staticmethod
    def get_audio_duration(audio_path: str) -> float:
        """Get audio duration via ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception as e:
            logger.warning(f"Could not get duration for {audio_path}: {e}")
            return 0.0

    async def process(
        self,
        audio_path: str,
        num_speakers: int,
        speaker_sample_paths: Optional[List[str]] = None,
    ) -> Tuple[List[Dict], float]:
        """
        Diarization-only pipeline:
        Returns (segments, total_duration_seconds)
        """
        logger.info("=" * 60)
        logger.info(f"Pipeline start | file={Path(audio_path).name} | speakers={num_speakers}")

        loop = asyncio.get_event_loop()

        # Step 1: Diarization
        annotation = await loop.run_in_executor(
            None,
            lambda: self._run_diarization(audio_path, num_speakers, speaker_sample_paths),
        )

        # Step 2: Extract and group segments
        segments = self._extract_and_group_segments(annotation)

        # Step 3: Total duration
        total_duration = await loop.run_in_executor(
            None, lambda: self.get_audio_duration(audio_path)
        )

        logger.info(f"Pipeline complete | {len(segments)} segments | duration={total_duration:.1f}s")
        logger.info("=" * 60)

        return segments, total_duration
