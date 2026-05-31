import sys
import json
from pathlib import Path
from loguru import logger
from app.config import settings
from app.request_context import request_id_ctx_var

Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)


def patch_record(record):
    record["extra"]["request_id"] = request_id_ctx_var.get()


def json_sink(message):
    record = message.record
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "request_id": record["extra"].get("request_id", "-"),
        "extra": {
            k: v for k, v in record["extra"].items() if k != "request_id"
        },
    }
    with open(settings.LOG_FILE_JSON, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


logger.remove()
logger = logger.patch(patch_record)

# لاگ در ترمینال
logger.add(
    sys.stdout,
    level="INFO",
    colorize=True,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level}</level> | "
        "request_id={extra[request_id]} | "
        "{message} | extra={extra}"
    ),
)

# لاگ در فایل JSONL
logger.add(json_sink, level="INFO")

app_logger = logger
