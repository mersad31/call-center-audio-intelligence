# main.py
import os
import traceback
from fastapi import FastAPI, Request, Security, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security.api_key import APIKeyHeader

from app.api.v1.detect import router as detect_router
from app.core.logging import logger
from app.core.errors import ErrorCode
from app.utils.request_id import RequestIDMiddleware
from app.core.database_logger import purge_logs
from app.llm.client import LLMClient
from app.core.config import settings



api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

#ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

app = FastAPI(
    title="Operator Behavior Detection Service",
    version="1.0.0",
)

# -----------------------------
# Middleware
# -----------------------------
app.add_middleware(RequestIDMiddleware)

# -----------------------------
# Routers
# -----------------------------
app.include_router(detect_router, prefix="/api/v1")


# -----------------------------
# Global Exception Handlers
# -----------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    
    # ارسال جزئیات خطا به state برای ثبت در دیتابیس
    request.state.error_message = traceback.format_exc()

    logger.exception(
        "Unhandled exception",
        extra={"request_id": request_id},
    )

    return JSONResponse(
        status_code=500,
        content={
            "status": "failed",
            "error": {
                "code": ErrorCode.INTERNAL_SERVER_ERROR,
                "message": "Internal server error",
            },
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # ثبت ارورهای اعتبارسنجی ورودی کاربر
    request.state.error_message = str(exc.errors())
    
    return JSONResponse(
        status_code=422,
        content={
            "status": "failed",
            "error": {
                "code": "VALIDATION_ERROR",
                "message": exc.errors(),
            },
        },
    )

# -----------------------------
# Admin Logs Endpoint
# -----------------------------
api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

def get_admin_api_key(api_key: str = Security(api_key_header)):
    # مقدار ADMIN_SECRET_KEY باید در فایل .env قرار گیرد
    admin_key = os.getenv("ADMIN_SECRET_KEY", "default_admin_secret_123")
    if api_key != admin_key:
        raise HTTPException(
            status_code=403, 
            detail="Could not validate admin credentials"
        )
    return api_key


# -----------------------------
# Health Checks
# -----------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/health/llm")
async def llm_health():
    try:
        client = LLMClient()
        await client.detect("ping")
        return {"status": "ok"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
        )


# --------------------------------------------------
# Admin Log Purge Endpoint
# --------------------------------------------------
@app.delete("/admin/logs/purge")
async def purge_database_logs_endpoint(days: int = 30, x_api_key: str = Header(None)):
    """
    Purges database logs older than the specified number of days and reclaims disk space.
    Secured by x-api-key header matching the admin_secret_key environment variable.
    """
    if x_api_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
        
    deleted_count = purge_logs(days)
    
    if deleted_count == -1:
        raise HTTPException(status_code=500, detail="Failed to purge logs due to an internal error.")
        
    return {"message": f"Successfully purged {deleted_count} logs older than {days} days."}