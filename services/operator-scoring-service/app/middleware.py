import time
import uuid
import json
import hashlib
import asyncio
import traceback
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.database_logger import async_log_to_db

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 1. تولید شناسه درخواست ۸ کاراکتری بر پایه هش
        raw_uuid = str(uuid.uuid4()).encode()
        request_id = hashlib.sha256(raw_uuid).hexdigest()[:8]
        request.state.request_id = request_id

        status_code = 500
        error_message = None
        response = None

        # اعتبارسنجی هوشمند بادی ورودی برای جلوگیری از مصرف استریم یا فایل‌های احتمالی سنگین
        content_type = request.headers.get("content-type", "")
        input_data_str = "{}"
        
        if "multipart/form-data" in content_type or "application/octet-stream" in content_type:
            content_length = request.headers.get("content-length", "0")
            size_mb = round(int(content_length) / (1024 * 1024), 3) if content_length.isdigit() else 0.0
            input_data_str = json.dumps({
                "note": "Binary or streaming data detected; logging metadata only.",
                "content_type": content_type,
                "size_mb": size_mb
            })
        else:
            # مصرف امن ریپیت شونده ریکوئست بادی برای JSON بدون تداخل در کنترلرها
            body_bytes = await request.body()
            async def receive():
                return {"type": "http.request", "body": body_bytes, "more_body": False}
            request._receive = receive
            
            if body_bytes:
                try:
                    input_data_str = json.dumps(json.loads(body_bytes.decode("utf-8")), ensure_ascii=False)
                except Exception:
                    input_data_str = body_bytes.decode("utf-8", errors="ignore")[:2000]

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error_message = traceback.format_exc()
            raise e
        finally:
            response_time_sec = round(time.time() - start_time, 4)
            
            # خواندن پیام خطای ذخیره شده توسط Exception Handlerها
            if getattr(request.state, "error_message", None):
                error_message = request.state.error_message

            # تعیین سطح لاگ بر اساس وضعیت پاسخ
            log_level = "INFO"
            if status_code >= 500:
                log_level = "CRITICAL" if error_message else "ERROR"
            elif status_code >= 400:
                log_level = "WARNING"

            output_data_str = json.dumps({"status": "hidden_to_prevent_stream_consumption"})

            # ارسال تسک ثبت لاگ به Core Loop پایتون به صورت کاملاً Async و مستقل (به سبک نمونه دوم)
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

        response.headers["X-Request-ID"] = request_id
        return response