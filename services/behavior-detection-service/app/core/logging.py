#app/core/logging.py
import os
import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Any, Dict


SERVICE_NAME = "operator-behavior-service"
LOG_FILE_PATH = "logs/service.log"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }

        # attach request_id if exists
        if hasattr(record, "request_id"):
            log_record["request_id"] = record.request_id

        # attach exception info
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # attach extra structured fields
        for key, value in record.__dict__.items():
            if key.startswith("_"):
                continue
            if key in (
                "name", "msg", "args", "levelname", "levelno",
                "pathname", "filename", "module", "exc_info",
                "exc_text", "stack_info", "lineno", "funcName",
                "created", "msecs", "relativeCreated", "thread",
                "threadName", "processName", "process"
            ):
                continue
            log_record[key] = value

        return json.dumps(log_record, ensure_ascii=False)


def setup_logger() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(SERVICE_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = JSONFormatter()

    # -------- Console (stdout) --------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # -------- File (rotating JSON log) --------
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=10 * 1024 * 1024,   # 10MB
        backupCount=10,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()
