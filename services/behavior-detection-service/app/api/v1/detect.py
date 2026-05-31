# app/api/v1/detect.py

from typing import Dict, List, Optional
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.domain.models import (
    STTSegment,
    DetectionError,
    DetectionRequest,
    DetectionResponse,
)
from app.preprocessing.operator_filter import extract_operator_speech
from app.detection.greeting import GreetingDetector
from app.detection.introduction import IntroductionDetector
from app.detection.formal_tone import FormalToneDetector
from app.detection.survey import SurveyInvitationDetector
from app.core.errors import ErrorCode
from app.core.logging import logger
from app.llm.client import LLMClient

router = APIRouter()


# -------------------------------------------------------------
#   /detect — MAIN ENDPOINT
# -------------------------------------------------------------
@router.post("/detect", response_model=DetectionResponse)
async def detect_operator_behavior(payload: DetectionRequest, request: Request):
    request_id = getattr(request.state, "request_id", None)
    transcript = payload.transcript
    model_name: Optional[str] = payload.model

    if model_name == "string":
        model_name = None

    logger.info(
        "Received detection request",
        extra={
            "total_segments": len(transcript),
            "request_id": request_id,
            "model_name": model_name,
        },
    )

    # 1) Empty transcript
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail={
                "code": ErrorCode.EMPTY_TRANSCRIPT,
                "message": "هیچ سگمنتی وجود ندارد",
            },
        )

    # 2) Extract operator speech
    operator_segments = extract_operator_speech(transcript)

    if not operator_segments:
        return JSONResponse(
            status_code=422,
            content={
                "status": "failed",
                "error": {
                    "code": ErrorCode.NO_OPERATOR_SPEECH,
                    "message": "هیچ گفتاری از اپراتور یافت نشد",
                },
            },
        )

    logger.info(
        "Operator speech extracted",
        extra={
            "operator_segments": len(operator_segments),
            "request_id": request_id,
        },
    )

    # 3) Shared LLM client
    llm = LLMClient()

    # 4) Instantiate detectors
    detectors = [
        GreetingDetector(llm),
        IntroductionDetector(llm),
        FormalToneDetector(llm),
        SurveyInvitationDetector(llm),
    ]

    # 5) Run all detectors concurrently
    async def run_detector(detector):
        result = await detector.detect(
            operator_segments,
            request_id=request_id,
            model_name=model_name,
        )
        return detector.behavior_name, result

    tasks = [run_detector(det) for det in detectors]
    raw_results = await asyncio.gather(*tasks)

    # 6) Build response
    results: Dict[str, Optional[int]] = {}
    errors: List[DetectionError] = []

    for behavior_name, result in raw_results:
        results[behavior_name.value] = (
            result.label.value if result.label is not None else None
        )

        if result.error_code:
            errors.append(
                DetectionError(
                    behavior=behavior_name.value,
                    code=result.error_code,
                    message=result.error_message,
                )
            )

    status = "partial_success" if errors else "success"

    logger.info(
        "Detection completed",
        extra={
            "request_id": request_id,
            "status": status,
            "results": results,
            "errors_count": len(errors),
            "model_name": model_name,
        },
    )

    return DetectionResponse(
        status=status,
        results=results,
        errors=errors,
    )
