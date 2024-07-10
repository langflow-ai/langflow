import json
import logging
import os
import sys
import threading
from datetime import timedelta
from pathlib import Path
from collections import OrderedDict
from itertools import islice
from typing import Dict, Optional

import orjson
from loguru import logger
from platformdirs import user_cache_dir
from rich.logging import RichHandler

VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class SizedLogBuffer:
    def __init__(self):
        """
        a buffer for storing log messages for the log retrieval API
        the buffer can be overwritten by an env variable LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE
        because the logger is initialized before the settings_service are loaded
        """
        self.max: int = 0
        env_buffer_size = os.getenv("LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE", "0")
        if env_buffer_size.isdigit():
            self.max = int(env_buffer_size)

        self.buffer: OrderedDict[float, str] = OrderedDict()

        self._lock = threading.Lock()
        self.page_size: int = 100
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout: timedelta = timedelta(minutes=5)

    def write(self, message: str):
        record = json.loads(message)
        log_entry = record["text"]
        epoch = record["record"]["time"]["timestamp"]
        with self._lock:
            if len(self.buffer) >= self.max:
                # remove the oldest log entry if the buffer is full
                self.buffer.popitem(last=False)
            self.buffer[epoch] = log_entry

    def __len__(self):
        return len(self.buffer)

    def get_after_timestamp(self, timestamp: float, lines: int = 5) -> dict[float, str]:
        rc = dict()
        with self._lock:
            for ts, msg in self.buffer.items():
                if lines == 0:
                    break
                if ts >= timestamp and lines > 0:
                    rc[ts] = msg
                    lines -= 1
        return rc

    def get_before_timestamp(self, timestamp: float, lines: int = 5) -> dict[float, str]:
        rc = dict()
        with self._lock:
            for ts, msg in reversed(self.buffer.items()):
                if lines == 0:
                    break
                if ts < timestamp and lines > 0:
                    rc[ts] = msg
                    lines -= 1
        return rc

    def get_last_n(self, last_idx: int) -> dict[float, str]:
        with self._lock:
            return dict(islice(reversed(self.buffer.items()), last_idx))

    def enabled(self) -> bool:
        return self.max > 0

    def max_size(self) -> int:
        return self.max


# log buffer for capturing log messages
log_buffer = SizedLogBuffer()


def serialize_log(record):
    subset = {
        "timestamp": record["time"].timestamp(),
        "message": record["message"],
        "level": record["level"].name,
        "module": record["module"],
    }
    return orjson.dumps(subset)


def patching(record):
    record["extra"]["serialized"] = serialize_log(record)


def configure(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    disable: Optional[bool] = False,
    log_env: Optional[str] = None,
):
    if disable and log_level is None and log_file is None:
        logger.disable("langflow")
    if os.getenv("LANGFLOW_LOG_LEVEL", "").upper() in VALID_LOG_LEVELS and log_level is None:
        log_level = os.getenv("LANGFLOW_LOG_LEVEL")
    if log_level is None:
        log_level = "ERROR"

    if log_env is None:
        log_env = os.getenv("LANGFLOW_LOG_ENV", "")

    logger.remove()  # Remove default handlers
    logger.patch(patching)
    if log_env.lower() == "container" or log_env.lower() == "container_json":
        logger.add(sys.stdout, format="{message}", serialize=True)
    elif log_env.lower() == "container_csv":
        logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} {level} {file} {line} {function} {message}")
    else:
        # Human-readable
        log_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> - <level>"
            "{level: <8}</level> - {module} - <level>{message}</level>"
        )

        # Configure loguru to use RichHandler
        logger.configure(
            handlers=[
                {
                    "sink": RichHandler(rich_tracebacks=True, markup=True),
                    "format": log_format,
                    "level": log_level.upper(),
                }
            ]
        )

        if not log_file:
            cache_dir = Path(user_cache_dir("langflow"))
            logger.debug(f"Cache directory: {cache_dir}")
            log_file = cache_dir / "langflow.log"
            logger.debug(f"Log file: {log_file}")
        try:
            log_file = Path(log_file)
            log_file.parent.mkdir(parents=True, exist_ok=True)

            logger.add(
                sink=str(log_file),
                level=log_level.upper(),
                format=log_format,
                rotation="10 MB",  # Log rotation based on file size
                serialize=True,
            )
        except Exception as exc:
            logger.error(f"Error setting up log file: {exc}")

    if log_buffer.enabled():
        logger.add(sink=log_buffer.write, format="{time} {level} {message}", serialize=True)

    logger.debug(f"Logger set up with log level: {log_level}")

    setup_uvicorn_logger()
    setup_gunicorn_logger()


def setup_uvicorn_logger():
    loggers = (logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith("uvicorn."))
    for uvicorn_logger in loggers:
        uvicorn_logger.handlers = []
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]


def setup_gunicorn_logger():
    logging.getLogger("gunicorn.error").handlers = [InterceptHandler()]
    logging.getLogger("gunicorn.access").handlers = [InterceptHandler()]


class InterceptHandler(logging.Handler):
    """
    Default handler from examples in loguru documentaion.
    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging
    """

    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
