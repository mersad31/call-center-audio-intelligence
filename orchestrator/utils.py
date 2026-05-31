import subprocess
from pathlib import Path
from logger import get_logger

logger = get_logger("audio_cutter")


class AudioCutter:
    """Cuts audio segments using FFmpeg."""

    @staticmethod
    def cut_audio(input_path: str, output_path: str, start_time: float, end_time: float) -> bool:
        duration = end_time - start_time
        if duration <= 0:
            logger.warning(f"Invalid segment duration: {duration:.3f}s",
                           extra_data={"start": start_time, "end": end_time})
            return False

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ss", f"{start_time:.3f}", "-t", f"{duration:.3f}",
            "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-avoid_negative_ts", "make_zero", "-loglevel", "error",
            output_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                return True
            else:
                logger.error(f"FFmpeg failed", extra_data={"stderr": result.stderr[:300]})
                return False
        except Exception as e:
            logger.error("Cut error", exc_info=True)
            return False