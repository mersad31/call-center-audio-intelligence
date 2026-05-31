# app/detection/survey.py
from typing import Optional

from app.detection.base import BaseBehaviorDetector, DetectionResult
from app.domain.behaviors import BehaviorName
from app.llm.prompt_builder import build_behavior_prompt


class SurveyInvitationDetector(BaseBehaviorDetector):
    behavior_name = BehaviorName.SURVEY_INVITATION
    min_sentences = 1

    start_ratio = 0.6
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
