"""HTTP Middleware for request tracking and database logging."""

import time
import uuid
import hashlib
import json
import asyncio
import logging
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from overlap_analysis_service.database_logger import async_log_to_db

logger = logging.getLogger("overlap_analysis_service")

# متغیری برای محافظت از تسک‌ها در برابر Garbage Collector پایتون
_background_tasks = set()


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_time = datetime.utcnow().isoformat() + "Z"

        raw_uuid = str(uuid.uuid4()).encode()
        request_id = hashlib.sha256(raw_uuid).hexdigest()[:8]
        request.state.request_id = request_id

        # پیش‌فرض پیام ارور خالی است؛ در صورت بروز خطا توسط هندلرها پر می‌شود
        request.state.error_message = getattr(request.state, "error_message", "")

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

            # ثبت لاگ در دیتابیس به صورت غیرهمگام (Background Task)
            task = asyncio.create_task(async_log_to_db(
                request_id=request_id,
                endpoint=request.url.path,
                method=request.method,
                status_code=status_code,
                request_time=request_time,
                response_time_sec=response_time_sec,
                input_data=input_data_str,
                output_data=f"Status: {status_code}",
                error_message=request.state.error_message,
                log_level=log_level
            ))

            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return response