import os
import json
import logging
import traceback
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import setup_logging
from app.middleware import RequestContextMiddleware
from app.schemas import ConversationRequest, ScoreResponse
from app.scoring_prompt import build_prompt
from app.llm_client import call_gemini, LLMError
from app.config import settings
from app.database_logger import init_db, purge_logs

# راه‌اندازی دیتابیس در زمان Startup سرور
init_db()
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Operator Scoring Service", version="1.0.0")
app.add_middleware(RequestContextMiddleware)

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
# Service Core API Endpoints
# --------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "operator_scoring_service"}


@app.post("/score", response_model=ScoreResponse)
async def score_conversation(request: ConversationRequest, req: Request):
    request_id = getattr(req.state, "request_id", None)

    if len(request.utterances) < 2:
        raise HTTPException(
            status_code=400,
            detail="Conversation is too short for evaluation",
        )

    # تبدیل مدل‌های پیدانتیک به دیکشنری برای پرامپت نویسی بدون ایجاد تغییر در عملکرد روند بقیه جاها
    prompt = build_prompt([u.model_dump() if hasattr(u, "model_dump") else u.dict() for u in request.utterances])

    try:
        result = await call_gemini(prompt)
        
        if "error" in result:
            raise HTTPException(
                status_code=422,
                detail="Conversation insufficient for scoring",
            )

        return result

    except LLMError as exc:
        logger.error(f"LLM Error for request {request_id}: {exc}")
        raise HTTPException(
            status_code=502,
            detail="Upstream LLM service error",
        )


# --------------------------------------------------
# Admin Log Purge Endpoint (Exactly matching your preferred style)
# --------------------------------------------------
@app.delete("/admin/logs/purge")
async def purge_database_logs_endpoint(days: int = 30, x_api_key: str = Header(None)):
    """
    Purges database logs older than the specified number of days and reclaims disk space.
    Secured by x-api-key header matching the ADMIN_SECRET_KEY environment variable.
    """
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
    
    if x_api_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
        
    deleted_count = purge_logs(days)
    
    if deleted_count == -1:
        raise HTTPException(status_code=500, detail="Failed to purge logs due to an internal error.")
        
    return {"message": f"Successfully purged {deleted_count} logs older than {days} days."}