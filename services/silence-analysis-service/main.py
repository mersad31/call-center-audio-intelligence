import os
import time
import uuid
import json
import hashlib
import shutil
import asyncio
import tempfile
import traceback
import httpx

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, File, HTTPException, UploadFile, Request, Security, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException

from calculate_silence_api.logger import get_logger
from calculate_silence_api.schemas import (
    HealthResponse,
    SilenceResponse,
    SilenceFromSegmentsRequest,
    SilenceFromSegmentsResponse,
)
from calculate_silence_api.silence_engine import calculate_operator_silence
from calculate_silence_api.database_logger import init_db, async_log_to_db, purge_logs


load_dotenv()

# Initialize DB on Startup
init_db()

app = FastAPI(title="Calculate Silence API", version="1.0.0")
logger = get_logger()

DIARIZATION_URL = os.getenv("DIARIZATION_URL", "http://192.168.100.38:8001/diarize")
DEFAULT_SILENCE_THRESHOLD = float(os.getenv("SILENCE_THRESHOLD", "1.0"))
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav"}

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

# --------------------------------------------------
# Exception Handlers (To catch detailed errors for DB Logger)
# --------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request.state.error_message = json.dumps(exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request.state.error_message = exc.detail
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request.state.error_message = traceback.format_exc()
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


# --------------------------------------------------
# Smart Middleware (Non-blocking DB Logging)
# --------------------------------------------------
@app.middleware("http")
async def database_logging_middleware(request: Request, call_next):
    start_time = time.time()
    
    # 1. Generate 8-char hashed request ID
    raw_uuid = str(uuid.uuid4()).encode()
    request_id = hashlib.sha256(raw_uuid).hexdigest()[:8]
    request.state.request_id = request_id

    status_code = 500
    error_message = None
    response = None

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        error_message = traceback.format_exc()
        raise e
    finally:
        response_time_sec = round(time.time() - start_time, 4)
        
        # Check if exception handlers caught any error messages
        if getattr(request.state, "error_message", None):
            error_message = request.state.error_message

        # Determine Log Level
        log_level = "INFO"
        if status_code >= 500:
            log_level = "CRITICAL" if error_message else "ERROR"
        elif status_code >= 400:
            log_level = "WARNING"

        # Safe Input Data Extraction (Avoids streaming binary bodies)
        input_data_dict = {"query_params": dict(request.query_params)}
        if hasattr(request.state, "file_metadata"):
            input_data_dict["file_metadata"] = request.state.file_metadata
        if hasattr(request.state, "payload_metadata"):
            input_data_dict["payload_metadata"] = request.state.payload_metadata
            
        input_data_str = json.dumps(input_data_dict)
        output_data_str = json.dumps({"status": "hidden_to_prevent_stream_consumption"})

        # Fire and forget database log (Non-blocking)
        asyncio.create_task(
            async_log_to_db(
                request_id=request_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                request_time=datetime.utcnow().isoformat() + "Z",
                response_time_sec=response_time_sec,
                input_data=input_data_str,
                output_data=output_data_str,
                error_message=error_message,
                log_level=log_level
            )
        )

    return response


# --------------------------------------------------
# Time helpers & File validation & Metrics logic
# --------------------------------------------------
def parse_time_value(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip()
        if value.replace(".", "", 1).isdigit():
            return float(value)
        if ":" in value:
            parts = value.split(":")
            parts = [float(p) for p in parts]
            if len(parts) == 2:
                minutes, seconds = parts
                return minutes * 60 + seconds
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return hours * 3600 + minutes * 60 + seconds
    raise ValueError(f"Unsupported time format: {value}")

def round_float(value, digits: int = 3) -> float:
    return round(parse_time_value(value), digits)

def validate_audio_file(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is missing")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Allowed formats: mp3, m4a, wav"
        )
    return extension

def get_audio_duration(file_path: str) -> float:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(file_path)
        return round_float(len(audio) / 1000.0, 3)
    except Exception as exc:
        logger.exception("Failed to get audio duration: %s", exc)
        return 0.0

def compute_metrics(segments: List[Dict]) -> Dict[str, Dict]:
    metrics: Dict[str, Dict] = {}
    for seg in segments:
        speaker = seg["speaker"]
        start = round_float(seg["start"])
        end = round_float(seg["end"])
        duration = max(0.0, end - start)
        if speaker not in metrics:
            metrics[speaker] = {
                "speaker_id": speaker,
                "total_time": 0.0,
                "first_speech_time": start,
                "number_of_turns": 0,
            }
        metrics[speaker]["total_time"] += duration
        metrics[speaker]["number_of_turns"] += 1
        metrics[speaker]["first_speech_time"] = min(metrics[speaker]["first_speech_time"], start)
    for speaker in metrics:
        metrics[speaker]["total_time"] = round_float(metrics[speaker]["total_time"])
        metrics[speaker]["first_speech_time"] = round_float(metrics[speaker]["first_speech_time"])
    return metrics

def decide_operator(metrics: Dict[str, Dict]) -> Optional[str]:
    if not metrics:
        return None
    ordered = sorted(metrics.values(), key=lambda item: (item["first_speech_time"], -item["number_of_turns"], -item["total_time"]))
    return ordered[0]["speaker_id"] if ordered else None

def decide_customer(metrics: Dict[str, Dict], operator_speaker: Optional[str]) -> Optional[str]:
    candidates = [item for item in metrics.values() if item["speaker_id"] != operator_speaker]
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda item: (-item["total_time"], -item["number_of_turns"], item["first_speech_time"]))
    return ordered[0]["speaker_id"] if ordered else None

def build_speaker_info(metrics: Dict[str, Dict], speaker_id: Optional[str]) -> Dict:
    if not speaker_id or speaker_id not in metrics:
        return {"speaker_id": None, "total_time": 0.0, "first_speech_time": 0.0, "number_of_turns": 0}
    return {
        "speaker_id": metrics[speaker_id]["speaker_id"],
        "total_time": round_float(metrics[speaker_id]["total_time"]),
        "first_speech_time": round_float(metrics[speaker_id]["first_speech_time"]),
        "number_of_turns": int(metrics[speaker_id]["number_of_turns"]),
    }

async def call_diarization_api(file_path: str, original_filename: str, speaker_count: int = 2) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            with open(file_path, "rb") as audio_file:
                files = {"audio_file": (original_filename, audio_file, "application/octet-stream")}
                data = {"speaker_count": str(speaker_count)}
                response = await client.post(DIARIZATION_URL, files=files, data=data)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "segments" in data:
            return data["segments"]
        if isinstance(data, list):
            return data
        raise ValueError("Unexpected diarization response format")
    except Exception as exc:
        logger.exception("Diarization API call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Diarization API failed: {str(exc)}")


# --------------------------------------------------
# API endpoints
# --------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", service="calculate_silence_api")


@app.post("/process-silence", response_model=SilenceResponse)
async def process_silence(request: Request, file: UploadFile = File(...)):
    # Safely attach metadata for database logger (without reading binary stream)
    request.state.file_metadata = {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_mb": round(int(request.headers.get("content-length", 0)) / (1024 * 1024), 3) if request.headers.get("content-length") else "Unknown"
    }

    extension = validate_audio_file(file)
    call_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp_file:
        temp_path = temp_file.name
        shutil.copyfileobj(file.file, temp_file)

    try:
        logger.info("Processing silence for call_id=%s file=%s", call_id, file.filename)
        total_duration = get_audio_duration(temp_path)
        segments = await call_diarization_api(temp_path, file.filename)

        normalized_segments = [
            {"speaker": str(seg["speaker"]), "start": round_float(seg["start"]), "end": round_float(seg["end"])}
            for seg in segments
        ]

        metrics = compute_metrics(normalized_segments)
        operator_speaker = decide_operator(metrics)
        customer_speaker = decide_customer(metrics, operator_speaker)

        operator_info = build_speaker_info(metrics, operator_speaker)
        customer_info = build_speaker_info(metrics, customer_speaker)

        silence_result = calculate_operator_silence(
            segments=normalized_segments,
            operator_speaker=operator_speaker,
            total_duration=total_duration,
            operator_total_time=operator_info["total_time"],
            silence_threshold=DEFAULT_SILENCE_THRESHOLD,
        )

        response_payload = {
            "call_id": call_id,
            "total_duration": round_float(total_duration),
            "operator": operator_info,
            "customer": customer_info,
            "segments": normalized_segments,
            "silence_duration_seconds": silence_result["silence_duration_seconds"],
            "silence_duration_mmss": silence_result["silence_duration_mmss"],
            "silence_percent_total_call": silence_result["silence_percent_total_call"],
            "silence_percent_operator_time": silence_result["silence_percent_operator_time"],
            "silence_segments": silence_result["silence_segments"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        logger.info("Silence processing completed for call_id=%s operator=%s silence=%s sec", call_id, operator_speaker, silence_result["silence_duration_seconds"])
        return SilenceResponse(**response_payload)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in process_silence: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


def infer_total_duration_from_segments(segments: List[Dict]) -> float:
    if not segments:
        return 0.0
    return round_float(max(parse_time_value(s.get("end", 0.0)) for s in segments), 3)

def sum_duration_seconds(segments: List[Dict]) -> float:
    total = 0.0
    for s in segments:
        start = parse_time_value(s.get("start", 0.0))
        end = parse_time_value(s.get("end", 0.0))
        total += max(0.0, end - start)
    return round_float(total, 3)


@app.post("/process-silence-from-segments", response_model=SilenceFromSegmentsResponse)
async def process_silence_from_segments(request: Request, payload: SilenceFromSegmentsRequest):
    # Attach payload metadata for the logger
    request.state.payload_metadata = {"call_id": payload.call_id, "segments_count": len(payload.segments)}

    try:
        call_id = payload.call_id
        raw_segments = [seg.model_dump() for seg in payload.segments]

        total_duration = (round_float(payload.total_duration) if payload.total_duration is not None else infer_total_duration_from_segments(raw_segments))
        silence_threshold = (float(payload.silence_threshold) if payload.silence_threshold is not None else DEFAULT_SILENCE_THRESHOLD)

        operator_only = [s for s in raw_segments if (s.get("role") or "").strip().lower() == "operator"]
        operator_total_time = sum_duration_seconds(operator_only)

        normalized_all = []
        for s in raw_segments:
            role = (s.get("role") or "").strip().lower()
            normalized_all.append({"speaker": "OPERATOR" if role == "operator" else "OTHER", "start": round_float(s.get("start", 0.0)), "end": round_float(s.get("end", 0.0))})

        silence_result = calculate_operator_silence(
            segments=normalized_all,
            operator_speaker="OPERATOR",
            total_duration=total_duration,
            operator_total_time=operator_total_time,
            silence_threshold=silence_threshold,
        )

        response_payload = {
            "call_id": call_id,
            "total_duration": total_duration,
            "operator_total_time": operator_total_time,
            "silence_duration_seconds": silence_result["silence_duration_seconds"],
            "silence_duration_mmss": silence_result["silence_duration_mmss"],
            "silence_percent_total_call": silence_result["silence_percent_total_call"],
            "silence_percent_operator_time": silence_result["silence_percent_operator_time"],
            "silence_segments": silence_result["silence_segments"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return SilenceFromSegmentsResponse(**response_payload)

    except Exception as exc:
        logger.exception("Unexpected error in process_silence_from_segments: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

# --------------------------------------------------
# Admin Log Purge Endpoint
# --------------------------------------------------
@app.delete("/admin/logs/purge")
async def purge_database_logs_endpoint(days: int = 30, x_api_key: str = Header(None)):
    """
    Purges database logs older than the specified number of days and reclaims disk space.
    Secured by x-api-key header matching the ADMIN_SECRET_KEY environment variable.
    """
    if x_api_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
        
    deleted_count = purge_logs(days)
    
    if deleted_count == -1:
        raise HTTPException(status_code=500, detail="Failed to purge logs due to an internal error.")
        
    return {"message": f"Successfully purged {deleted_count} logs older than {days} days."}