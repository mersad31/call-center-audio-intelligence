import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str = "calculate_silence_api") -> logging.Logger:
    """
    Create and configure a logger for the silence calculation service.
    This logger writes both to console and to a rotating log file.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    os.makedirs("logs", exist_ok=True)
    log_file = os.path.join("logs", "calculate_silence_api.log")

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
