# app/detection/base.py
from abc import ABC, abstractmethod
from typing import List, Optional

from app.domain.models import STTSegment
from app.domain.enums import BehaviorLabel
from app.domain.behaviors import BehaviorName
from app.core.errors import ErrorCode
from app.llm.client import LLMClient
from app.detection.windowing import window_segments
from app.core.logging import logger


class DetectionResult:
    """
    خروجی استاندارد هر Behavior Detector
    """

    def __init__(
        self,
        label: Optional[BehaviorLabel],
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ):
        self.label = label
        self.error_code = error_code
        self.error_message = error_message


class BaseBehaviorDetector(ABC):
    behavior_name: BehaviorName
    min_sentences: int = 1
    start_ratio: float = 0.0
    end_ratio: float = 1.0

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    async def detect(
        self,
        segments: List[STTSegment],
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> DetectionResult:
        logger.info(
            "Starting behavior detection",
            extra={
                "behavior": self.behavior_name.value,
                "total_segments": len(segments),
                "request_id": request_id,
                "model_name": model_name,
            },
        )

        # 1) بررسی حداقل داده
        if len(segments) < self.min_sentences:
            logger.warning(
                "Insufficient segments for detection",
                extra={
                    "behavior": self.behavior_name.value,
                    "required_min_sentences": self.min_sentences,
                    "actual_segments": len(segments),
                    "request_id": request_id,
                },
            )
            return DetectionResult(
                label=None,
                error_code=ErrorCode.INSUFFICIENT_DATA,
                error_message="تعداد جملات اپراتور برای تشخیص این رفتار کافی نیست",
            )

        # 2) پنجره‌بندی
        windowed_segments = window_segments(
            segments=segments,
            start_ratio=self.start_ratio,
            end_ratio=self.end_ratio,
        )

        if not windowed_segments:
            logger.warning(
                "No windowed segments found for detection",
                extra={
                    "behavior": self.behavior_name.value,
                    "request_id": request_id,
                },
            )
            return DetectionResult(
                label=None,
                error_code=ErrorCode.INSUFFICIENT_DATA,
                error_message="بازه مناسب برای بررسی این رفتار خالی است",
            )

        text = "\n".join(
            seg.text.strip() for seg in windowed_segments if seg.text and seg.text.strip()
        )

        if not text:
            logger.warning(
                "Windowed text is empty",
                extra={
                    "behavior": self.behavior_name.value,
                    "request_id": request_id,
                },
            )
            return DetectionResult(
                label=None,
                error_code=ErrorCode.INSUFFICIENT_DATA,
                error_message="متن قابل بررسی برای این رفتار یافت نشد",
            )

        # 3) تشخیص توسط LLM
        try:
            result = await self._llm_detect(
                text=text,
                request_id=request_id,
                model_name=model_name,
            )

            logger.info(
                "Behavior detection completed",
                extra={
                    "behavior": self.behavior_name.value,
                    "request_id": request_id,
                    "model_name": model_name,
                    "label": result.label.value if result.label is not None else None,
                    "error_code": result.error_code,
                },
            )
            return result

        except Exception as exc:
            logger.exception(
                "Behavior detection failed",
                extra={
                    "behavior": self.behavior_name.value,
                    "request_id": request_id,
                    "model_name": model_name,
                    "error": str(exc),
                },
            )
            return DetectionResult(
                label=None,
                error_code=ErrorCode.LLM_FAILURE,
                error_message="خطا در پردازش تشخیص رفتار",
            )

    @abstractmethod
    async def _llm_detect(
        self,
        text: str,
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> DetectionResult:
        raise NotImplementedError
