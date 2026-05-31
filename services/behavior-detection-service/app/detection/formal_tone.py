# app/detection/formal_tone.py
from typing import Optional

from app.detection.base import BaseBehaviorDetector, DetectionResult
from app.domain.behaviors import BehaviorName
from app.llm.prompt_builder import build_behavior_prompt


class FormalToneDetector(BaseBehaviorDetector):
    behavior_name = BehaviorName.FORMAL_TONE
    min_sentences = 3

    start_ratio = 0.0
    end_ratio = 1.0

    async def _llm_detect(
        self,
        text: str,
        request_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> DetectionResult:
        prompt = build_behavior_prompt(self.behavior_name.value, text)
        result = await self.llm.detect(
            prompt=prompt,
            request_id=request_id,
            model_name=model_name,
        )

        return DetectionResult(
            label=result["label"],
            error_code=None,
            error_message=None,
        )
