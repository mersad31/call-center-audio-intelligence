from __future__ import annotations

from pathlib import Path
import random
import time

from openai import OpenAI
from openai import RateLimitError, APIError, APITimeoutError

from app.config import settings
from app.exceptions import ExternalAPIError
from app.logger import app_logger


class GapGPTTranscriber:
    def __init__(self):
        if not settings.GAPGPT_API_KEY:
            raise RuntimeError("GAPGPT_API_KEY is not set")

        self.client = OpenAI(
            base_url=settings.GAPGPT_BASE_URL,
            api_key=settings.GAPGPT_API_KEY,
        )

        # قابل تنظیم با env اگر خواستی (اختیاری)
        self.max_retries = getattr(settings, "GAPGPT_MAX_RETRIES", 5)
        self.base_delay_sec = getattr(settings, "GAPGPT_RETRY_BASE_DELAY_SEC", 1.5)
        self.max_delay_sec = getattr(settings, "GAPGPT_RETRY_MAX_DELAY_SEC", 60)

    def _sleep_before_retry(self, attempt: int) -> float:
        # exponential backoff + jitter
        delay = min(self.max_delay_sec, (2 ** attempt) * self.base_delay_sec)
        delay += random.random()  # jitter 0..1
        return delay

    def transcribe_file(self, audio_path: Path, language: str = "fa") -> str:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise ExternalAPIError(f"Audio file not found: {audio_path}")

        last_err: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                with open(audio_path, "rb") as f:
                    response = self.client.audio.transcriptions.create(
                        model=settings.WHISPER_MODEL,
                        file=f,
                        language=language,
                    )

                text = getattr(response, "text", "") or ""
                return text.strip()

            except (RateLimitError, APITimeoutError, APIError) as e:
                # این‌ها معمولاً transient هستند => retry
                last_err = e
                delay = self._sleep_before_retry(attempt)

                app_logger.warning(
                    "GapGPT transient error; retrying",
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                    sleep_seconds=round(delay, 2),
                    error=str(e),
                    audio_path=str(audio_path),
                )

                time.sleep(delay)
                continue

            except Exception as e:
                # بقیه خطاها: retry نمی‌کنیم (می‌تونی تغییر بدی)
                app_logger.exception(
                    "GapGPT transcription failed (non-retriable)",
                    error=str(e),
                    audio_path=str(audio_path),
                )
                raise ExternalAPIError(f"GapGPT transcription failed: {str(e)}")

        # اگر بعد از retryها هم نشد
        app_logger.error(
            "GapGPT transcription failed after retries",
            max_retries=self.max_retries,
            error=str(last_err),
            audio_path=str(audio_path),
        )
        raise ExternalAPIError(f"GapGPT transcription failed after retries: {str(last_err)}")
