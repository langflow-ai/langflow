import json
import logging
import os
import sys
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path
from typing import Any, Dict, Deque, Optional

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
        self.buffer: Deque[str] = deque(maxlen=self.max)
        self._lock = threading.Lock()
        self.page_size: int = 100
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout: timedelta = timedelta(minutes=5)

    def write(self, message: str):
        record = json.loads(message)
        log_entry = record["text"]
        with self._lock:
            self.buffer.append(log_entry)

    def readlines(self) -> list[str]:
        return list(self.buffer)

    def enabled(self) -> bool:
        return self.max > 0

    def max_size(self) -> int:
        return self.max

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created": datetime.now(),
            "last_access": datetime.now(),
            "snapshot": list(self.buffer),
        }
        return session_id

    def get_page(self, session_id: str, page: int) -> Dict[str, Any]:
        self.cleanup_sessions()

        if session_id not in self.sessions:
            return {"error": "Invalid or expired session ID"}

        session = self.sessions[session_id]
        session["last_accessed"] = datetime.now()
        logs = session["snapshot"]

        total_logs = len(logs)
        total_pages = ceil(total_logs / self.page_size)

        if page < 1 or page > total_pages:
            return {
                "logs": [],
                "page": page,
                "total_pages": total_pages,
                "total_logs": total_logs,
                "session_id": session_id,
            }

        start_index = (page - 1) * self.page_size
        end_index = min(start_index + self.page_size, total_logs)

        return {
            "logs": logs[start_index:end_index],
            "page": page,
            "total_pages": total_pages,
            "total_logs": total_logs,
            "session_id": session_id,
        }

    def cleanup_sessions(self) -> None:
        current_time = datetime.now()
        expired_sessions = [
            sid
            for sid, session in self.sessions.items()
            if current_time - session["last_accessed"] > self.session_timeout
        ]
        for sid in expired_sessions:
            del self.sessions[sid]


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
