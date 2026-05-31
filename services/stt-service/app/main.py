from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.models import SegmentsRequest, OutputResponse, OutputSegment
from app.logger import app_logger
from app.exceptions import (
    AppError,
    MissingFieldError,
    InvalidSegmentError,
    AudioProcessingError,
)
from app.transcriber import GapGPTTranscriber
from app.utils import cut_audio_segment
from app.config import settings
from app.middlewares import RequestIDMiddleware
from app.request_context import request_id_ctx_var
from app.database_logger import purge_logs


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
app.add_middleware(RequestIDMiddleware)

transcriber = GapGPTTranscriber()


def error_response(message: str, code: str, status_code: int, details: Any = None):
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id_ctx_var.get(),
        },
    }
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    request.state.error_message = exc.message # برای دریافت در دیتابیس لاگر
    app_logger.error(
        "Application error",
        path=str(request.url.path),
        code=exc.code,
        error_message=exc.message,
        details=getattr(exc, "details", None),
    )
    return error_response(
        exc.message,
        exc.code,
        exc.status_code,
        details=getattr(exc, "details", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request.state.error_message = str(exc.errors()) # برای دریافت در دیتابیس لاگر
    app_logger.error(
        "Request validation error",
        path=str(request.url.path),
        errors=exc.errors(),
    )
    return error_response(
        message="Request validation failed",
        code="request_validation_error",
        status_code=422,
        details=exc.errors(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request.state.error_message = str(exc) 
    app_logger.exception(
        "Unhandled server error",
        path=str(request.url.path),
        error=str(exc),
    )
    return error_response(
        message="Internal server error",
        code="internal_server_error",
        status_code=500,
    )


@app.get("/health")
async def health():
    return {
        "success": True,
        "message": "Service is up",
        "request_id": request_id_ctx_var.get(),
    }


def _resolve_audio_path(audio_path_str: str) -> Path:
    """
    Resolve orchestrator-provided path to an existing file on STT server.

    It tries:
      1) absolute path (if provided)
      2) relative to STT cwd
      3) relative to repo root (parent of Online-STT) for cases where
         Orchestrator_api/temp_audio is sibling to Online-STT.

    Returns: resolved Path (must exist and be a file)
    Raises: MissingFieldError if not found / invalid
    """
    raw = (audio_path_str or "").strip()
    if not raw:
        raise MissingFieldError("audio_path is empty")

    candidates: list[Path] = []
    p = Path(raw)

    # 1) as-is (absolute or relative)
    candidates.append(p)

    # 2) relative to STT cwd
    if not p.is_absolute():
        candidates.append(Path.cwd() / p)

    # 3) relative to repo root (parent of Online-STT)
    # Example:
    #   STT cwd: .../persian-ai/Online-STT
    #   Orchestrator temp: .../persian-ai/Orchestrator_api/temp_audio
    repo_root = Path.cwd().parent
    if not p.is_absolute():
        candidates.append(repo_root / p)

    # IMPORTANT: Orchestrator temp folder (sibling project)
    # audio_path usually is "temp_audio\\file.mp3"
    # so map it to ".../persian-ai/Orchestrator_api/temp_audio/file.mp3"
    if len(p.parts) >= 2 and p.parts[0].lower() == "temp_audio":
         candidates.append(repo_root / "Orchestrator_api" / Path(*p.parts))
    else:
         # if orchestrator sent only filename, try in orchestrator temp
         candidates.append(repo_root / "Orchestrator_api" / "temp_audio" / p.name)

    checked = []
    for c in candidates:
        try:
            resolved = c.resolve()
        except Exception:
            resolved = c

        checked.append(str(resolved))

        if resolved.exists():
            if resolved.is_dir():
                raise MissingFieldError(
                    "audio_path is a directory, expected a file",
                    details={"audio_path": raw, "interpreted_path": str(resolved)},
                )
            # file exists
            size = resolved.stat().st_size
            if size == 0:
                raise MissingFieldError(
                    "audio file is empty",
                    details={"audio_path": raw, "interpreted_path": str(resolved)},
                )
            return resolved

    raise MissingFieldError(
        "audio_path does not exist on STT server",
        details={
            "audio_path": raw,
            "cwd": str(Path.cwd()),
            "checked_paths": checked,
            "hint": "If STT and Orchestrator are in separate containers/machines, use a shared volume or upload the file instead of sending a local path.",
        },
    )


@app.post("/transcribe")
async def transcribe(request_data: SegmentsRequest, request: Request):
    # Always define these first (prevents UnboundLocalError)
    audio_path_str = (request_data.audio_path or "").strip()
    audio_url_str = (request_data.audio_url or "").strip() or None

    app_logger.info(
        "Incoming transcription request",
        extra={
            "audio_path": audio_path_str or None,
            "audio_url": audio_url_str,
            "segment_count": len(request_data.segments or []),
            "cwd": str(Path.cwd()),
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    # guard
    if not request_data.audio_path and not request_data.audio_url:
        raise MissingFieldError("audio_path or audio_url is required")

    if request_data.audio_url:
        # not supported for now
        raise MissingFieldError("audio_url is not supported yet")

    # Resolve actual file path on STT server
    tmp_path = _resolve_audio_path(audio_path_str)

    app_logger.info(
        "Audio file resolved",
        audio_path=audio_path_str,
        interpreted_path=str(tmp_path),
        size_bytes=tmp_path.stat().st_size,
    )

    output_segments: list[OutputSegment] = []

    for idx, seg in enumerate(request_data.segments):
        # parse times
        try:
            start_sec = time_str_to_seconds(seg.start)
            end_sec = time_str_to_seconds(seg.end)
        except ValueError as e:
            app_logger.error(
                "Invalid segment time format",
                index=idx,
                speaker=seg.speaker,
                start=seg.start,
                end=seg.end,
                error=str(e),
            )
            raise InvalidSegmentError(
                f"Invalid time format at index {idx}",
                details={"index": idx, "start": seg.start, "end": seg.end},
            )

        if end_sec <= start_sec:
            app_logger.error(
                "Invalid segment timing",
                index=idx,
                speaker=seg.speaker,
                start=seg.start,
                end=seg.end,
            )
            raise InvalidSegmentError(
                f"Invalid segment timing at index {idx}: end must be greater than start",
                details={"index": idx, "start": seg.start, "end": seg.end},
            )

        app_logger.info(
            "Processing segment",
            index=idx,
            speaker=seg.speaker,
            start=seg.start,
            end=seg.end,
            start_sec=start_sec,
            end_sec=end_sec,
        )

        # Cut segment
        try:
            seg_audio_path = cut_audio_segment(tmp_path, start_sec, end_sec)
        except Exception as e:
            app_logger.exception(
                "Failed to cut audio segment",
                index=idx,
                speaker=seg.speaker,
                error=str(e),
            )
            raise AudioProcessingError(
                f"Failed to cut segment at index {idx}",
                details={"index": idx, "error": str(e)},
            )

        # Transcribe
        try:
            try:
                text = transcriber.transcribe_file(seg_audio_path, language="fa")
            except Exception as e:
                app_logger.exception(
                    "Transcriber failed",
                    index=idx,
                    speaker=seg.speaker,
                    error=str(e),
                )
                raise AudioProcessingError(
                    f"Transcription failed at index {idx}",
                    details={"index": idx, "error": str(e)},
                )
        finally:
            # cleanup
            try:
                seg_audio_path.unlink(missing_ok=True)
            except Exception:
                pass

        output_segments.append(
            OutputSegment(
                speaker=seg.speaker,
                start=seg.start,
                end=seg.end,
                text=text or "",
            )
        )

    response = OutputResponse(success=True, segments=output_segments)

    app_logger.info(
        "Transcription completed successfully",
        segment_count=len(output_segments),
    )

    return response.model_dump()


@app.delete("/admin/logs/purge")
async def purge_logs_endpoint(days: int, x_api_key: str = Header(...)):
    """
    Purges API logs older than X days from the SQLite database.
    Reclaims disk space using VACUUM command.
    """
    if x_api_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    
    deleted_rows = purge_logs(days)
    return {
        "success": True,
        "message": f"Successfully deleted {deleted_rows} logs older than {days} days and reclaimed disk space."
    }


def time_str_to_seconds(t: str) -> float:
    """
    Accepts:
      MM:SS
      MM:SS.mmm
      HH:MM:SS
      HH:MM:SS.mmm
    """
    t = t.strip()
    parts = [p.strip() for p in t.split(":")]

    if len(parts) == 2:
        h = 0
        m, s = parts
    elif len(parts) == 3:
        h, m, s = parts
    else:
        raise ValueError(f"Invalid time format: {t}")

    return int(h) * 3600 + int(m) * 60 + float(s)
