"""
Deprecated module.

STT is no longer used inside Diarization.
This client is retained only for backward compatibility.
"""

import httpx
from pathlib import Path
from typing import Optional

from app.logger import setup_logger



logger = setup_logger("transcription_client")

_client_instance: Optional["TranscriptionClient"] = None


class TranscriptionClient:
    """Async HTTP client for the STT API (deprecated in v2)."""

    def __init__(self, base_url: str, timeout: float = 180.0, max_connections: int = 10):
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/transcribe"
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=max_connections),
        )
        logger.info(f"TranscriptionClient ready | url={self.base_url} | timeout={timeout}s")

    async def transcribe(self, audio_path: str) -> Optional[str]:
        path = Path(audio_path)
        logger.debug(f"Sending to STT API: {path.name}")

        try:
            with open(audio_path, "rb") as f:
                files = {"file": (path.name, f, "audio/wav")}
                response = await self._client.post(self.endpoint, files=files)

            if response.status_code == 200:
                return response.json().get("text", "").strip() or None
            else:
                logger.error(f"STT API error {response.status_code}: {response.text[:200]}")
                return None

        except Exception as e:
            logger.error(f"Transcription request failed: {e}", exc_info=True)
            return None

    async def close(self):
        await self._client.aclose()


def get_transcription_client(base_url: str) -> TranscriptionClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = TranscriptionClient(base_url)
    return _client_instance
