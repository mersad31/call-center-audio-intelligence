# request_id.py
import uuid
import hashlib
from contextvars import ContextVar
from typing import Optional

# ایجاد یک کانتکست متغیر ایمن برای درخواست‌های همزمان (Thread/Async Safe)
_request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

def generate_new_id() -> str:

    raw_id = str(uuid.uuid4()).encode()
    return hashlib.sha256(raw_id).hexdigest()[:8]

def set_request_id(request_id: str) -> None:

    _request_id_ctx_var.set(request_id)

def get_request_id() -> str:

    req_id = _request_id_ctx_var.get()
    return req_id if req_id is not None else "system"