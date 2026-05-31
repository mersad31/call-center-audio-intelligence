"""FastAPI entrypoint for overlap_analysis_service."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from overlap_analysis_service.analyzer import (
    MERGE_GAP_SEC,
    OVERLAP_THRESHOLD_SEC,
    SpeechSegment,
    analyze_overlaps,
)
from overlap_analysis_service.logging_config import configure_logging
from overlap_analysis_service.schemas import (
    Metrics,
    OverlapAnalysisRequest,
    OverlapAnalysisResponse,
    OverlapBlock,
)

# وارد کردن میدل‌ور و دیتابیس لاگر
from overlap_analysis_service.middleware import RequestIDMiddleware
from overlap_analysis_service.database_logger import purge_logs




configure_logging()
logger = logging.getLogger("overlap_analysis_service")


load_dotenv()
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default_secret_key_change_me")

app = FastAPI(
    title="Overlap Analysis Service",
    version="0.1.0",
    description="Standalone CPU-only service for counting operator/customer simultaneous speech blocks.",
)

# اضافه کردن میدل‌ور دیتابیس لاگر
app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------
# Exception Handlers (To catch and log errors to Database)
# ---------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request.state.error_message = f"Unhandled Exception: {str(exc)}"
    logger.exception(
        "Unhandled request failure",
        extra={
            "oa_path": request.url.path, 
            "oa_method": request.method,
            "oa_request_id": getattr(request.state, "request_id", "unknown")
        },
    )
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request.state.error_message = f"Validation Error: {exc.errors()}"
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request.state.error_message = f"HTTP Error: {exc.detail}"
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=OverlapAnalysisResponse)
def analyze(request_body: OverlapAnalysisRequest) -> OverlapAnalysisResponse:
    logger.info(
        "Overlap analysis request started",
        extra={
            "oa_call_id": request_body.call_id,
            "oa_segment_count": len(request_body.segments),
        },
    )

    sorted_segments = sorted(
        request_body.segments,
        key=lambda segment: (segment.start_sec, segment.end_sec, segment.speaker),
    )
    speech_segments = [
        SpeechSegment(
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            speaker=segment.speaker,
        )
        for segment in sorted_segments
    ]

    analysis = analyze_overlaps(speech_segments)
    overlap_blocks = [
        OverlapBlock(
            block_id=index,
            start_sec=block.start_sec,
            end_sec=block.end_sec,
            duration_sec=block.duration_sec,
        )
        for index, block in enumerate(analysis.merged_blocks, start=1)
    ]
    total_overlap_duration = sum(block.duration_sec for block in analysis.merged_blocks)
    overlap_percentage = (total_overlap_duration / request_body.audio_duration_sec) * 100

    logger.info(
        "Overlap analysis request completed",
        extra={
            "oa_call_id": request_body.call_id,
            "oa_raw_overlap_count": len(analysis.raw_overlaps),
            "oa_filtered_overlap_count": len(analysis.filtered_overlaps),
            "oa_merged_overlap_block_count": len(analysis.merged_blocks),
        },
    )

    return OverlapAnalysisResponse(
        call_id=request_body.call_id,
        call_duration_sec=request_body.audio_duration_sec,
        overlap_threshold_ms=int(OVERLAP_THRESHOLD_SEC * 1000),
        merge_gap_ms=int(MERGE_GAP_SEC * 1000),
        metrics=Metrics(
            overlap_count=len(overlap_blocks),
            total_overlap_duration_sec=total_overlap_duration,
            overlap_percentage=overlap_percentage,
        ),
        overlap_blocks=overlap_blocks,
        processing_timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.delete("/admin/logs/purge")
async def purge_database_logs_endpoint(days: int = 30, x_api_key: str | None = Header(None)):
    """
    Purges database logs older than the specified number of days and reclaims disk space.
    Secured by x-api-key header matching the ADMIN_SECRET_KEY environment variable.
    """
    if not x_api_key or x_api_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
        
    deleted_count = purge_logs(days)
    
    if deleted_count == -1:
        raise HTTPException(status_code=500, detail="Failed to purge logs due to an internal error.")
        
    return {"message": f"Successfully purged {deleted_count} logs older than {days} days."}