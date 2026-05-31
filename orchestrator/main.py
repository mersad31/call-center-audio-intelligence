import os
import time
import uuid
import hashlib
import json
import asyncio
import httpx
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Request, Header
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from logger import get_logger
from database_logger import async_log_to_db, purge_logs
from exceptions import ServiceUnavailableError, ServiceProcessingError, OrchestratorBaseException
import clients

from schemas import SilenceFromSegmentsRequest, SilenceResponse




logger = get_logger("orchestrator_main")

app = FastAPI(
    title="Call Center Orchestrator API",
    description="Central Orchestrator for Transcription, Silence, Overlap, Behavior, Sentiment Analysis, and Operator Scoring",
    version="1.2.0"
)

# --- MIDDLEWARE & LOGGING SETUP ---
_background_tasks = set()

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_time = datetime.now(timezone.utc).isoformat()

        raw_uuid = str(uuid.uuid4()).encode()
        request_id = hashlib.sha256(raw_uuid).hexdigest()[:8]
        request.state.request_id = request_id
        request.state.error_message = ""

        logger.info("Incoming request", extra={"oa_request_id": request_id})

        input_data_str = ""
        content_type = request.headers.get("content-type", "")

        if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
            content_length = request.headers.get("content-length", "Unknown")
            length_mb = round(int(content_length) / (1024 * 1024), 2) if content_length.isdigit() else "Unknown"
            input_data_str = json.dumps({
                "type": "file/stream",
                "content_type": content_type,
                "size_mb": length_mb
            })
        else:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    input_data_str = body_bytes.decode('utf-8')

                async def receive():
                    return {"type": "http.request", "body": body_bytes}

                request._receive = receive
            except Exception:
                input_data_str = "Could not parse request body"

        status_code = 500
        log_level = "INFO"

        try:
            response = await call_next(request)
            status_code = response.status_code

            if status_code >= 400:
                log_level = "ERROR"

            response.headers["X-Request-ID"] = request_id

        except Exception as e:
            status_code = 500
            log_level = "CRITICAL"
            request.state.error_message = f"Unhandled Middleware Exception: {str(e)}"
            raise e

        finally:
            response_time_sec = time.time() - start_time

            logger.info(
                "Request completed",
                extra={
                    "oa_request_id": request_id,
                    "oa_status_code": status_code,
                    "oa_response_time_sec": round(response_time_sec, 4)
                }
            )

            # ثبت لاگ در دیتابیس به صورت غیرهمگام
            task = asyncio.create_task(async_log_to_db(
                request_id=request_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                request_time=request_time,
                response_time_sec=response_time_sec,
                input_data=input_data_str,
                output_data=f"Status: {status_code}",
                error_message=getattr(request.state, "error_message", ""),
                log_level=log_level
            ))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return response

app.add_middleware(RequestIDMiddleware)
# ----------------------------------

@app.exception_handler(OrchestratorBaseException)
async def custom_orchestrator_exception_handler(request: Request, exc: OrchestratorBaseException):
    request.state.error_message = exc.message  # اضافه شده برای دیتابیس لاگر
    logger.error(
        f"Orchestrator Error: {exc.message}",
        extra={"service": exc.service_name, "details": exc.details}
    )
    status_code = 503 if isinstance(exc, ServiceUnavailableError) else 502
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.message, "service": exc.service_name, "details": exc.details}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request.state.error_message = str(exc)  # اضافه شده برای دیتابیس لاگر
    logger.error("Unhandled Exception", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "Internal Orchestrator Error"})


ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav"}


def validate_audio_input(file: UploadFile) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename is missing in the request!")

    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(ALLOWED_EXTENSIONS)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Allowed formats: {allowed_str}"
        )

    return suffix


def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Failed to extract audio duration for {file_path}", extra={"error": str(e)})
        return 0.0


def build_conversation_text(segments: List[dict], target_role: str = "customer") -> str:
    lines = []

    for seg in segments:
        role = (seg.get("role") or "").strip().lower()
        text = (seg.get("text") or "").strip()

        if not text:
            continue

        if target_role and role != target_role:
            continue

        lines.append(text)

    return "\n".join(lines)


def build_operator_score_utterances(segments: list) -> list:
    utterances = []
    for seg in segments:
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        raw_role = str(seg.get("role", seg.get("speaker", ""))).lower()
        if "operator" in raw_role or "agent" in raw_role or "support" in raw_role:
            speaker = "operator"
        elif "customer" in raw_role or "client" in raw_role or "user" in raw_role:
            speaker = "customer"
        else:
            continue 

        try:
            start_time = float(seg.get("start_time", seg.get("start", 0.0)))
            end_time = float(seg.get("end_time", seg.get("end", 0.0)))
        except (ValueError, TypeError):
            start_time = 0.0
            end_time = 0.0

        utterances.append({
            "speaker": speaker,
            "start_time": start_time,
            "end_time": end_time,
            "text": text
        })
        
    return utterances


def mmss_to_seconds(t: str) -> float:
    t = (t or "").strip()
    parts = t.split(":")
    parts = [p.strip() for p in parts]

    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    elif len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    else:
        return float(t)


def apply_role_labels_to_segments(
    segments: List[dict],
    operator_id: str | None,
    customer_id: str | None,
) -> List[dict]:
    for seg in segments or []:
        speaker = str(seg.get("speaker", ""))

        if operator_id and speaker == str(operator_id):
            seg["role"] = "operator"
        elif customer_id and speaker == str(customer_id):
            seg["role"] = "customer"
        else:
            seg.setdefault("role", "")

    return segments


def build_behavior_transcript(segments: List[dict]) -> List[dict]:
    transcript: List[dict] = []

    for seg in segments or []:
        text = (seg.get("text") or "").strip()
        speaker = (seg.get("role") or seg.get("speaker") or "").strip()

        if not text:
            continue
        if not speaker:
            continue

        transcript.append(
            {
                "speaker": speaker,
                "text": text,
                "start_time": float(seg.get("start", 0.0)),
                "end_time": float(seg.get("end", 0.0)),
            }
        )

    return transcript


async def run_base_pipeline(file: UploadFile, call_id: str) -> tuple[str, float, list]:
    file_extension = validate_audio_input(file)

    temp_dir = Path("temp_audio")
    temp_dir.mkdir(exist_ok=True)

    temp_path = temp_dir / f"{call_id}{file_extension}"

    content = await file.read()
    with open(temp_path, "wb") as f:
        f.write(content)

    audio_duration = get_audio_duration(str(temp_path))

    logger.info(f"[{call_id}] Calling Diarization...")
    diar_data = await clients.fetch_diarization(content, file.filename)
    raw_segments = diar_data.get("segments", [])

    segments = []
    for seg in raw_segments:
        segments.append(
            {
                "speaker": str(seg["speaker"]),
                "start": mmss_to_seconds(seg["start"]) if isinstance(seg["start"], str) else float(seg["start"]),
                "end": mmss_to_seconds(seg["end"]) if isinstance(seg["end"], str) else float(seg["end"]),
                "text": "",
            }
        )

    logger.info(f"[{call_id}] Diarization completed.", extra={"segment_count": len(segments)})

    return str(temp_path), audio_duration, segments


async def run_transcription_pipeline(file: UploadFile, call_id: str) -> Tuple[str, float, List[dict], List[str]]:
    main_audio_path, duration, segments = await run_base_pipeline(file, call_id)

    if not segments:
        logger.warning(f"[{call_id}] No diarization segments found.")
        return main_audio_path, duration, [], []

    logger.info(f"[{call_id}] Calling STT...")
    segments = await clients.fetch_stt(main_audio_path, segments)
    logger.info(f"[{call_id}] STT completed.", extra={"segment_count": len(segments)})

    logger.info(f"[{call_id}] Preparing segments for Role Detection...")
    segments_for_role = [
        seg for seg in segments
        if seg.get("text") and str(seg["text"]).strip()
    ]

    if not segments_for_role:
        logger.warning(f"[{call_id}] All STT segments are empty; skipping role detection.")
        role_data = {}
    else:
        logger.info(
            f"[{call_id}] Calling Role Detection...",
            extra={"segment_count": len(segments_for_role)}
        )
        role_data = await clients.fetch_roles({"segments": segments_for_role})

    operator_id = role_data.get("operator_id")
    customer_id = role_data.get("customer_id")

    logger.info(
        f"[{call_id}] Role Detection completed.",
        extra={
            "operator_id": operator_id,
            "customer_id": customer_id,
        }
    )

    final_segments = apply_role_labels_to_segments(segments, operator_id, customer_id)

    return main_audio_path, duration, final_segments, []


@app.post("/pipeline/transcription")
async def pipeline_transcription(file: UploadFile = File(...)):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None
    chunk_paths: List[str] = []

    logger.info(f"[{call_id}] Started transcription pipeline.")

    try:
        main_audio_path, duration, segments, chunk_paths = await run_transcription_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No segments found. Returning empty list.")
            return {"call_id": call_id, "segments": []}

        logger.info(f"[{call_id}] Transcription pipeline completed successfully.")
        return {
            "call_id": call_id,
            "segments": segments
        }

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

        for path in chunk_paths:
            if os.path.exists(path):
                os.remove(path)

        try:
            chunks_dir = Path(f"temp_audio/chunks_{call_id}")
            if chunks_dir.exists():
                chunks_dir.rmdir()
        except Exception as e:
            logger.warning(f"[{call_id}] Could not remove chunks directory: {e}")


@app.post("/pipeline/operator-silence", response_model=SilenceResponse)
async def pipeline_operator_silence(
    file: UploadFile = File(...),
    silence_threshold: Optional[float] = None,
):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None
    chunk_paths: List[str] = []

    logger.info(f"[{call_id}] Started operator_silence pipeline.")

    try:
        main_audio_path, duration, segments, chunk_paths = await run_transcription_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No segments found. Returning empty silence result.")
            return {
                "call_id": call_id,
                "silence_duration_seconds": 0.0,
                "silence_duration_mmss": "00:00",
                "silence_percent_total_call": 0.0,
                "silence_segments": [],
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            silence_result = await clients.fetch_silence_from_segments(
                client=client,
                call_id=call_id,
                segments=segments,
                total_duration=duration,
                silence_threshold=silence_threshold,
            )

        logger.info(
            f"[{call_id}] operator_silence result",
            extra={"silence_result": silence_result}
        )

        return silence_result

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

        for path in chunk_paths:
            if os.path.exists(path):
                os.remove(path)

        try:
            chunks_dir = Path(f"temp_audio/chunks_{call_id}")
            if chunks_dir.exists():
                chunks_dir.rmdir()
        except Exception as e:
            logger.warning(f"[{call_id}] Could not remove chunks directory: {e}")


@app.post("/pipeline/behavior")
async def pipeline_behavior(file: UploadFile = File(...)):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None
    chunk_paths: List[str] = []

    logger.info(f"[{call_id}] Started behavior pipeline.")

    try:
        main_audio_path, duration, segments, chunk_paths = await run_transcription_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No transcript segments found. Returning empty result.")
            return {"call_id": call_id, "result": None, "segments": []}

        role_counts = {"operator": 0, "customer": 0, "empty": 0, "other": 0}
        for s in segments:
            r = (s.get("role") or "").strip().lower()
            if r == "operator":
                role_counts["operator"] += 1
            elif r == "customer":
                role_counts["customer"] += 1
            elif r == "":
                role_counts["empty"] += 1
            else:
                role_counts["other"] += 1

        logger.info(
            f"[{call_id}] Prepared segments for behavior.",
            extra={"segment_count": len(segments), "role_counts": role_counts}
        )

        behavior_payload = {
            "transcript": [
                {
                    "speaker": (seg.get("role") or seg.get("speaker") or ""),
                    "text": seg.get("text", ""),
                    "start_time": float(seg["start"]),
                    "end_time": float(seg["end"]),
                }
                for seg in segments
                if (seg.get("text") or "").strip()
            ]
        }

        logger.info(
            f"[{call_id}] Sending data to Behavior Detection service...",
            extra={"transcript_count": len(behavior_payload["transcript"]), "behavior_url": settings.behavior_url}
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            result = await clients.fetch_behaviors(
                client=client,
                transcript=behavior_payload["transcript"]
            )

        logger.info(f"[{call_id}] Behavior pipeline completed successfully.")

        if isinstance(result, dict):
            return {"call_id": call_id, **result}

        return {"call_id": call_id, "result": result}

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

        for path in chunk_paths:
            if os.path.exists(path):
                os.remove(path)

        try:
            chunks_dir = Path(f"temp_audio/chunks_{call_id}")
            if chunks_dir.exists():
                chunks_dir.rmdir()
        except Exception as e:
            logger.warning(f"[{call_id}] Could not remove chunks directory: {e}")


@app.post("/pipeline/sentiment")
async def pipeline_sentiment(file: UploadFile = File(...)):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None
    chunk_paths: List[str] = []

    logger.info(f"[{call_id}] Started sentiment pipeline.")

    try:
        main_audio_path, duration, segments, chunk_paths = await run_transcription_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No transcript segments found. Returning empty sentiment result.")
            return {"call_id": call_id, "sentiment": None, "error": "empty transcript"}

        customer_texts = []
        for seg in segments:
            role = (seg.get("role") or "").strip().lower()
            text = (seg.get("text") or "").strip()
            
            if role == "customer" and text:
                customer_texts.append(text)

        conversation = "\n".join(customer_texts)

        if not conversation.strip():
            logger.warning(f"[{call_id}] No customer utterances found after transcript normalization.")
            return {"call_id": call_id, "sentiment": None, "error": "no customer conversation found"}

        logger.info(f"[{call_id}] Sending customer conversation to Sentiment service...")

        async with httpx.AsyncClient() as client:
            result = await clients.fetch_sentiment(client, conversation)

        logger.info(f"[{call_id}] Sentiment pipeline completed successfully.")

        if isinstance(result, dict):
            return {"call_id": call_id, **result}

        return {"call_id": call_id, "sentiment": None, "error": "invalid sentiment response"}

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

        for path in chunk_paths:
            if os.path.exists(path):
                os.remove(path)

        try:
            chunks_dir = Path(f"temp_audio/chunks_{call_id}")
            if chunks_dir.exists():
                chunks_dir.rmdir()
        except Exception as e:
            logger.warning(f"[{call_id}] Could not remove chunks directory: {e}")


@app.post("/pipeline/operator-score")
async def pipeline_operator_score(file: UploadFile = File(...)):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None
    chunk_paths: List[str] = []

    logger.info(f"[{call_id}] Started operator scoring pipeline.")

    try:
        main_audio_path, duration, segments, chunk_paths = await run_transcription_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No transcript segments found.")
            return {"call_id": call_id, "error": "empty transcript"}

        utterances = build_operator_score_utterances(segments)

        if len(utterances) < 2:
            logger.warning(f"[{call_id}] Conversation too short for operator scoring.")
            return {"call_id": call_id, "error": "conversation is too short for evaluation"}

        logger.info(f"[{call_id}] Sending normalized utterances to Operator Scoring service...")

        async with httpx.AsyncClient(timeout=100.0) as client:
            result = await clients.fetch_operator_score(
                client=client,
                conversation_id=call_id,
                utterances=utterances
            )

        logger.info(f"[{call_id}] Operator scoring pipeline completed successfully.")

        if isinstance(result, dict):
            return {"call_id": call_id, **result}

        return {"call_id": call_id, "error": "invalid scoring response"}

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

        for path in chunk_paths:
            if os.path.exists(path):
                os.remove(path)

        try:
            chunks_dir = Path(f"temp_audio/chunks_{call_id}")
            if chunks_dir.exists():
                chunks_dir.rmdir()
        except Exception as e:
            logger.warning(f"[{call_id}] Could not remove chunks directory: {e}")


@app.post("/pipeline/overlap")
async def pipeline_overlap(file: UploadFile = File(...)):
    call_id = str(uuid.uuid4())[:8]
    main_audio_path = None

    logger.info(f"[{call_id}] Started overlap pipeline.")

    try:
        main_audio_path, duration, segments = await run_base_pipeline(file, call_id)

        if not segments:
            logger.warning(f"[{call_id}] No segments found. Returning empty metrics.")
            return {"call_id": call_id, "metrics": None, "overlap_blocks": []}

        overlap_payload = {
            "call_id": call_id,
            "audio_duration_sec": duration,
            "segments": [
                {
                    "start_sec": float(seg["start"]),
                    "end_sec": float(seg["end"]),
                    "speaker": seg.get("role", "customer")
                } for seg in segments
            ]
        }

        logger.info(f"[{call_id}] Sending data to Overlap service...")

        async with httpx.AsyncClient() as client:
            result = await clients._safe_request(
                client,
                "POST",
                settings.overlap_url,
                "OverlapAnalysis",
                json=overlap_payload
            )

        logger.info(f"[{call_id}] Overlap pipeline completed successfully.")
        return result

    finally:
        if main_audio_path and os.path.exists(main_audio_path):
            os.remove(main_audio_path)

# --- Admin Endpoints ---
@app.delete("/admin/logs/purge")
async def purge_database_logs_endpoint(request: Request, days: int = 30, x_api_key: str | None = Header(None)):
    """
    Purges database logs older than the specified number of days and reclaims disk space.
    Secured by x-api-key header matching the ADMIN_SECRET_KEY environment variable.
    """
    if not x_api_key or x_api_key != settings.admin_secret_key:
        request.state.error_message = "Unauthorized: Invalid API Key"
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
        
    deleted_count = purge_logs(days)
    
    if deleted_count == -1:
        request.state.error_message = "Failed to purge logs due to internal DB error"
        raise HTTPException(status_code=500, detail="Failed to purge logs due to an internal error.")
        
    return {"message": f"Successfully purged {deleted_count} logs older than {days} days."}