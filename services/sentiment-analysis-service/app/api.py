# api.py
import time
import json
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Header, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

from .preprocessing import preprocess_conversation
from .rules import validate_input, validate_emotional_content
from .sentiment_model import SentimentModel
from .scoring import score_messages, map_final_sentiment
from .database_logger import db_logger
from .request_id import generate_new_id, set_request_id, get_request_id
from .config import settings



app = FastAPI(title="Persian Sentiment Service", version="1.0.0")

#ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

class AnalyzeRequest(BaseModel):
    conversation: str

class AnalyzeResponse(BaseModel):
    sentiment: str | None = None
    error: dict | None = None
    request_id: str | None = None  # اضافه شدن شناسه به خروجی لاگ وب

model = SentimentModel()

# =========================
# System Middlewares
# =========================
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        request_time = datetime.utcnow().isoformat()
        
        # ۱. تولید شناسه و ذخیره آن در کانتکست جاری درخواست
        current_id = generate_new_id()
        set_request_id(current_id)
        
        body_bytes = await request.body()
        async def receive():
            return {"type": "http.request", "body": body_bytes}
        request._receive = receive
        
        content_type = request.headers.get("content-type", "")
        input_data_str = None
        
        if "multipart/form-data" in content_type:
            input_data_str = json.dumps({
                "type": "binary/multipart",
                "size_mb": round(len(body_bytes) / (1024 * 1024), 4),
                "metadata": "File stream skipped"
            })
        elif "application/json" in content_type:
            try:
                input_data_str = body_bytes.decode('utf-8')
            except Exception:
                input_data_str = json.dumps({"error": "un-decodable json body"})
        else:
            input_data_str = json.dumps({
                "content_type": content_type,
                "size_mb": round(len(body_bytes) / (1024 * 1024), 4)
            })

        status_code = 500
        error_message = None
        log_level = "INFO"
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error_message = f"Unhandled Exception: {str(e)}"
            log_level = "ERROR"
            raise e
        finally:
            response_time_sec = time.perf_counter() - start_time
            
            state_error = getattr(request.state, "error_message", None)
            if state_error:
                error_message = state_error
            elif status_code >= 400 and not error_message:
                error_message = f"HTTP Error {status_code}"
                
            if status_code >= 400:
                log_level = "ERROR"
            
            # ۲. ارسال شناسه فعالِ کانتکست به دیتابیس لاگر
            db_logger.log(
                request_id=get_request_id(),
                endpoint=str(request.url.path),
                method=request.method,
                status_code=status_code,
                request_time=request_time,
                response_time_sec=response_time_sec,
                input_data=input_data_str,
                output_data=None, 
                error_message=error_message,
                log_level=log_level
            )
            
        return response

app.add_middleware(LoggingMiddleware)

# =========================
# Exception Handlers
# =========================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request.state.error_message = f"Validation Error: {str(exc.errors())}"
    return JSONResponse(
        status_code=422, 
        content={"detail": exc.errors(), "request_id": get_request_id()}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request.state.error_message = f"HTTP Exception: {exc.detail}"
    return JSONResponse(
        status_code=exc.status_code, 
        content={"detail": exc.detail, "request_id": get_request_id()}
    )


# =========================
# Core Logic Endpoints
# =========================
@app.post("/sentiment-analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    # گرفتن شناسه درخواست بدون دستکاری منطق توابع داخلی
    current_req_id = get_request_id()
    
    raw = req.conversation
    messages = preprocess_conversation(raw)

    err = validate_input(raw, messages)
    if err:
        return AnalyzeResponse(error=err["error"], request_id=current_req_id)

    labels = model.predict(messages)

    err = validate_emotional_content(messages, labels)
    if err:
        return AnalyzeResponse(error=err["error"], request_id=current_req_id)

    score = score_messages(messages, labels)
    sentiment = map_final_sentiment(score)

    return AnalyzeResponse(sentiment=sentiment, request_id=current_req_id)

# =========================
# Admin Endpoints
# =========================
@app.delete("/admin/logs/purge")
def purge_logs(days: int = 30, x_api_key: Optional[str] = Header(None, alias="x-api-key")):

    if x_api_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
    
    deleted_rows = db_logger.purge_logs(days)
    return {
        "message": "Logs purged successfully.", 
        "deleted_records": deleted_rows,
        "request_id": get_request_id()
    }