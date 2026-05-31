import subprocess
import tempfile
from pathlib import Path


def sec_to_time_str(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}.{ms:03d}"


def cut_audio_segment(input_audio: Path, start: float, end: float) -> Path:
    duration = end - start
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_audio),
        "-ss", str(start),
        "-t", str(duration),
        str(tmp_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return tmp_path
