import logging
import logging.handlers
from queue import Queue
from pythonjsonlogger import jsonlogger
import orjson
import os
from pathlib import Path


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/app.log.json")


class OrjsonFormatter(jsonlogger.JsonFormatter):
    def json_dumps(self, obj, *args, **kwargs):
        return orjson.dumps(obj).decode()


def setup_logging():
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    log_queue = Queue(-1)

    queue_handler = logging.handlers.QueueHandler(log_queue)
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(queue_handler)

    file_handler = logging.FileHandler(LOG_FILE)
    formatter = OrjsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"
    )
    file_handler.setFormatter(formatter)

    listener = logging.handlers.QueueListener(
        log_queue,
        file_handler,
        respect_handler_level=True,
    )
    listener.start()
