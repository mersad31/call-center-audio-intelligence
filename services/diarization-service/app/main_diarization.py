import os
os.environ["SPEECHBRAIN_SKIP_K2"] = "1"
os.environ["K2_IS_AVAILABLE"] = "0"

import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

import aiofiles
from fastapi import (
    FastAPI,
    File,
    Form,
    UploadFile,
    HTTPException,
    Request,
    Header,
    status
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from dotenv import load_dotenv
from starlette.concurrency import iterate_in_threadpool

from app.diarization.model_loader import load_diarization_model
from app.diarization.service import DiarizationService
from app.logger import setup_logger
from app.database_logger import init_db, log_to_sqlite, purge_logs

# ---------------------------------------------------------------------
# Environment & Application setup
# ---------------------------------------------------------------------

logger = setup_logger("diarization_api")
load_dotenv()

AUDIO_DIR = Path("audio")
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a"}
MAX_FILE_SIZE_MB = 500

_service: Optional[DiarizationService] = None


# ---------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------

def api_error(status: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "status": "error",
            "code": status,
            "error": message,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


def is_allowed_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def seconds_to_mmss(seconds: float) -> str:
    if seconds is None or seconds < 0:
        seconds = 0.0
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------
# Application lifecycle (startup / shutdown)
# ---------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _service

    logger.info("=" * 60)
    logger.info("Starting Diarization API")
    logger.info("=" * 60)

    AUDIO_DIR.mkdir(exist_ok=True)
    
    # راه‌اندازی دیتابیس لاگ‌ها در هنگام استارت آپ برنامه
    init_db()

    try:
        load_diarization_model()
        _service = DiarizationService()
        logger.info("Diarization model loaded successfully")
    except Exception:
        logger.error("Failed to load diarization model", exc_info=True)

    yield

    logger.info("Diarization API shutdown complete")


# ---------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------

class SegmentResult(BaseModel):
    speaker: str
    start: str  
    end: str    


class DiarizationResponse(BaseModel):
    segments: List[SegmentResult]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


# ---------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------

app = FastAPI(
    title="Persian Speaker Diarization API",
    version="2.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------
# Middleware: هوشمندترین بخش برای ثبت دقیق لاگ در SQLite
# ---------------------------------------------------------------------

@app.middleware("http")
async def sqlite_logger_middleware(request: Request, call_next):
    # ایجاد یک رکوئست آی‌دی منحصر به فرد در ابتدای ورود درخواست
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id
    
    # مقادیر پیش‌فرض برای ذخیره‌سازی داده‌های شخصی‌سازی شده در طول متدها
    request.state.custom_input = {}
    request.state.custom_error = None
    
    start_time = datetime.utcnow()
    
    fallback_input = {
        "query_params": dict(request.query_params),
        "url_path": request.url.path
    }
    
    status_code = 500
    response_body = ""
    error_message = None
    
    try:
        response = await call_next(request)
        status_code = response.status_code
        
        # استخراج پاسخ به صورت متنی فقط برای فرمت‌های JSON (جلوگیری از خواندن استریم‌های حجیم احتمالی)
        if "application/json" in response.headers.get("content-type", ""):
            res_body_bytes = b""
            async for chunk in response.body_iterator:
                res_body_bytes += chunk
            response.body_iterator = iterate_in_threadpool(iter([res_body_bytes]))
            response_body = res_body_bytes.decode("utf-8", errors="ignore")
        else:
            response_body = f"[Non-JSON Response: {response.headers.get('content-type')}]"
            
    except Exception as e:
        status_code = 500
        error_message = f"{type(e).__name__}: {str(e)}"
        response_body = json.dumps({"status": "error", "message": "Internal Server Error"})
        raise e
    finally:
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        # انتخاب بهترین دیتا برای ورودی و خطاهای رخ داده
        final_input = request.state.custom_input if request.state.custom_input else fallback_input
        final_error = error_message or request.state.custom_error
        
        # مشخص کردن سطح اهمیت لاگ
        log_level = "INFO"
        if status_code >= 500:
            log_level = "ERROR"
        elif status_code >= 400:
            log_level = "WARNING"
            
        log_record = {
            "request_id": request_id,
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": status_code,
            "request_time": start_time.isoformat(),
            "response_time_sec": duration,
            "input_data": json.dumps(final_input, ensure_ascii=False),
            "output_data": response_body,
            "error_message": final_error,
            "log_level": log_level
        }
        
        # ارسال لاگ به بک‌گراند ترد تسک جهت حفظ سرعت پاسخگویی سرور
        asyncio.create_task(log_to_sqlite(log_record))
        
    return response


# ---------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="ready" if _service else "degraded",
        model_loaded=_service is not None,
    )


# ---------------------------------------------------------------------
# Diarization endpoint
# ---------------------------------------------------------------------

@app.post("/diarize", response_model=DiarizationResponse)
async def diarize_audio(
    request: Request,
    audio_file: UploadFile = File(..., description="Main audio file"),
    speaker_count: int = Form(2, ge=1, le=20),
):
    # استفاده از Request ID تولید شده توسط سیستم Middleware
    request_id = request.state.request_id
    
    # پر کردن اطلاعات ورودی ساختار یافته برای لاگ دیتابیس
    request.state.custom_input = {
        "filename": audio_file.filename,
        "speaker_count": speaker_count,
        "speaker_samples_count": 0
    }

    # رفع خطای منطقی ۱: در صورت آماده نبودن مدل، خطا در دیتابیس هم به درستی ست می‌شود.
    if _service is None:
        request.state.custom_error = "Service is not ready (model loading)"
        raise HTTPException(
            status_code=503,
            detail="Service is not ready (model loading)",
        )

    logger.info(
        f"[{request_id}] Diarization request | file={audio_file.filename} | speakers={speaker_count}"
    )

    # رفع خطای منطقی ۲: اگر نام فایل صوتی خالی بود ارور لاگ ثبت شود.
    if not audio_file.filename:
        request.state.custom_error = "Audio file name is missing"
        return api_error(400, "Audio file name is missing")

    # رفع خطای منطقی ۳: فرمت غیرمجاز صوتی
    if not is_allowed_audio(audio_file.filename):
        request.state.custom_error = f"Unsupported audio format: {audio_file.filename}"
        return api_error(400, "Unsupported audio format")

    audio_bytes = await audio_file.read()
    file_size_mb = len(audio_bytes) / (1024 * 1024)
    request.state.custom_input["file_size_mb"] = round(file_size_mb, 2)

    # رفع خطای منطقی ۴: خالی بودن فایل
    if file_size_mb == 0:
        request.state.custom_error = "Audio file is empty"
        return api_error(400, "Audio file is empty")

    if file_size_mb > MAX_FILE_SIZE_MB:
        request.state.custom_error = f"File size ({round(file_size_mb,1)}MB) exceeds limit"
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {MAX_FILE_SIZE_MB}MB limit",
        )

    main_audio_path = AUDIO_DIR / f"{request_id}{Path(audio_file.filename).suffix}"
    sample_paths: List[str] = []

    try:
        async with aiofiles.open(main_audio_path, "wb") as f:
            await f.write(audio_bytes)

        form = await request.form()
        raw_samples = form.getlist("speaker_samples")

        for i, item in enumerate(raw_samples):
            if not isinstance(item, UploadFile) or not item.filename or not is_allowed_audio(item.filename):
                continue

            data = await item.read()
            if not data:
                continue

            path = AUDIO_DIR / f"{request_id}_sample_{i}{Path(item.filename).suffix}"
            async with aiofiles.open(path, "wb") as sf:
                await sf.write(data)

            sample_paths.append(str(path))
            
        # بروزرسانی تعداد نمونه اسپیکرها در دیتابیس لاگ
        request.state.custom_input["speaker_samples_count"] = len(sample_paths)

        segments, _ = await _service.process(
            audio_path=str(main_audio_path),
            num_speakers=speaker_count,
            speaker_sample_paths=sample_paths or None,
        )

        return DiarizationResponse(
            segments=[
                SegmentResult(
                    speaker=seg["speaker"],
                    start=seconds_to_mmss(seg["start"]),
                    end=seconds_to_mmss(seg["end"]),
                )
                for seg in segments
            ]
        )

    finally:
        for path in [main_audio_path, *map(Path, sample_paths)]:
            if path.exists():
                path.unlink()

# ---------------------------------------------------------------------
# Delete DataBase Logs
# ---------------------------------------------------------------------
ADMIN_SECRET = os.getenv("ADMIN_SECRET_KEY")

@app.delete("/admin/logs/purge")
async def clear_database_logs(
    days: int = 30, 
    x_api_key: str = Header(..., description="رمز عبور ادمین برای دسترسی")
):
    """
    حذف لاگ‌های قدیمی دیتابیس با تایید هویت از طریق هدر امنیتی
    """
    # بررسی صحت پسورد ارسال شده در هدر
    if x_api_key != ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="شما دسترسی لازم برای این عملیات را ندارید."
        )
    
    # اجرای متد حذف در صورت درست بودن پسورد
    loop = asyncio.get_event_loop()
    deleted_count = await loop.run_in_executor(None, purge_logs, days)
    
    return {
        "status": "success",
        "message": f"Successfully deleted {deleted_count} log records.",
        "scope": f"Older than {days} days" if days > 0 else "All logs"
    }


# ---------------------------------------------------------------------
# Global error handlers
# ---------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.error("Validation error: %s", exc.errors())
    if hasattr(request, "state"):
        request.state.custom_error = f"Validation Error: {str(exc.errors())}"
    return api_error(400, "Invalid request parameters")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if hasattr(request, "state"):
        request.state.custom_error = f"HTTP Error {exc.status_code}: {exc.detail}"
    return api_error(exc.status_code, exc.detail)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=True)
    if hasattr(request, "state"):
        request.state.custom_error = f"Unhandled Unexpected Exception: {str(exc)}"
    return api_error(500, "Unexpected server error")