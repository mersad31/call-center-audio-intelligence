import time
import uuid
import hashlib
import json
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.request_context import request_id_ctx_var
from app.logger import app_logger
from app.database_logger import log_to_db
from datetime import datetime

async def set_body(request: Request, body: bytes):
    """Utility to prevent FastAPI from hanging when reading body in BaseHTTPMiddleware."""
    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Generate 8-character hashed request_id
        raw_uuid = str(uuid.uuid4()).encode('utf-8')
        request_id = hashlib.sha256(raw_uuid).hexdigest()[:8]
        token = request_id_ctx_var.set(request_id)
        
        # Share request_id with internal state to be accessible by exception handlers
        request.state.request_id = request_id

        start_time = time.time()
        request_time = datetime.utcnow().isoformat()
        
        # 2. Safely capture input metadata as JSON
        input_data = None
        try:
            body_bytes = await request.body()
            await set_body(request, body_bytes) # Inject body back for the actual endpoint
            if body_bytes and "application/json" in request.headers.get("content-type", ""):
                input_data = json.loads(body_bytes)
        except Exception:
            input_data = {"note": "Could not parse request body metadata"}

        status_code = 500
        error_message = None

        try:
            app_logger.info(
                "Request started",
                method=request.method,
                path=request.url.path,
                client=str(request.client.host) if request.client else None,
            )

            # Process the request
            response = await call_next(request)
            
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            
            # Extract error message if it was set by our exception handlers
            if hasattr(request.state, "error_message"):
                error_message = request.state.error_message

            process_time_sec = time.time() - start_time
            app_logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=round(process_time_sec * 1000, 2),
            )
            return response

        except Exception as e:
            process_time_sec = time.time() - start_time
            error_message = str(e)
            app_logger.exception(
                "Request failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(process_time_sec * 1000, 2),
                error=error_message,
            )
            raise
        finally:
            process_time_sec = time.time() - start_time
            log_level = "ERROR" if status_code >= 400 else "INFO"
            
            # 3. Async Database Logging via Queue (Non-blocking)
            log_to_db({
                "request_id": request_id,
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "request_time": request_time,
                "response_time_sec": round(process_time_sec, 4),
                "input_data": json.dumps(input_data, ensure_ascii=False) if input_data else None,
                "output_data": None, # Output data is not logged to avoid memory bloat with large streams
                "error_message": error_message,
                "log_level": log_level
            })
            
            request_id_ctx_var.reset(token)