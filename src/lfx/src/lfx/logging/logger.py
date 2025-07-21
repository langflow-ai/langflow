import asyncio
import json
import logging
import os
import sys
from collections import deque
from pathlib import Path
from threading import Lock, Semaphore
from typing import TypedDict

import orjson
from loguru import _defaults, logger
from loguru._error_interceptor import ErrorInterceptor
from loguru._file_sink import FileSink
from loguru._simple_sinks import AsyncSink
from platformdirs import user_cache_dir
from rich.logging import RichHandler
from typing_extensions import NotRequired, override

VALID_LOG_LEVELS = ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
# Human-readable
DEFAULT_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> - <level>{level: <8}</level> - {module} - <level>{message}</level>"
)

# Use LANGFLOW environment variables to maintain compatibility
LOGGER_NAMESPACE = "langflow"
CACHE_DIR_NAME = "langflow"


class SizedLogBuffer:
    def __init__(
        self,
        max_readers: int = 20,  # max number of concurrent readers for the buffer
    ):
        """A buffer for storing log messages for the log retrieval API.

        The buffer can be overwritten by an env variable LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE
        because the logger is initialized before any settings are loaded.
        """
        self.buffer: deque = deque()

        self._max_readers = max_readers
        self._wlock = Lock()
        self._rsemaphore = Semaphore(max_readers)
        self._max = 0

    def get_write_lock(self) -> Lock:
        return self._wlock

    def write(self, message: str) -> None:
        record = json.loads(message)
        log_entry = record["text"]
        epoch = int(record["record"]["time"]["timestamp"] * 1000)
        with self._wlock:
            if len(self.buffer) >= self.max:
                for _ in range(len(self.buffer) - self.max + 1):
                    self.buffer.popleft()
            self.buffer.append((epoch, log_entry))

    def __len__(self) -> int:
        return len(self.buffer)

    def get_after_timestamp(self, timestamp: int, lines: int = 5) -> dict[int, str]:
        rc = {}

        self._rsemaphore.acquire()
        try:
            with self._wlock:
                for ts, msg in self.buffer:
                    if lines == 0:
                        break
                    if ts >= timestamp and lines > 0:
                        rc[ts] = msg
                        lines -= 1
        finally:
            self._rsemaphore.release()

        return rc

    def get_before_timestamp(self, timestamp: int, lines: int = 5) -> dict[int, str]:
        self._rsemaphore.acquire()
        try:
            with self._wlock:
                as_list = list(self.buffer)
            max_index = -1
            for i, (ts, _) in enumerate(as_list):
                if ts >= timestamp:
                    max_index = i
                    break
            if max_index == -1:
                return self.get_last_n(lines)
            rc = {}
            start_from = max(max_index - lines, 0)
            for i, (ts, msg) in enumerate(as_list):
                if start_from <= i < max_index:
                    rc[ts] = msg
            return rc
        finally:
            self._rsemaphore.release()

    def get_last_n(self, last_idx: int) -> dict[int, str]:
        self._rsemaphore.acquire()
        try:
            with self._wlock:
                as_list = list(self.buffer)
            return dict(as_list[-last_idx:])
        finally:
            self._rsemaphore.release()

    @property
    def max(self) -> int:
        # Get it dynamically to allow for env variable changes
        if self._max == 0:
            env_buffer_size = os.getenv("LANGFLOW_LOG_RETRIEVER_BUFFER_SIZE", "0")
            if env_buffer_size.isdigit():
                self._max = int(env_buffer_size)
        return self._max

    @max.setter
    def max(self, value: int) -> None:
        self._max = value

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


def patching(record) -> None:
    record["extra"]["serialized"] = serialize_log(record)
    # Default to development mode behavior unless specified otherwise
    # Check lfx DEV setting which already handles env var fallback
    from lfx.settings import DEV

    dev_mode = DEV
    if not dev_mode:
        record.pop("exception", None)


class LogConfig(TypedDict):
    log_level: NotRequired[str]
    log_file: NotRequired[Path]
    disable: NotRequired[bool]
    log_env: NotRequired[str]
    log_format: NotRequired[str]


class AsyncFileSink(AsyncSink):
    def __init__(self, file):
        self._sink = FileSink(
            path=file,
            rotation="10 MB",  # Log rotation based on file size
            delay=True,
        )
        super().__init__(self.write_async, None, ErrorInterceptor(_defaults.LOGURU_CATCH, -1))

    async def complete(self):
        await asyncio.to_thread(self._sink.stop)
        for task in self._tasks:
            await self._complete_task(task)

    async def write_async(self, message):
        await asyncio.to_thread(self._sink.write, message)


def is_valid_log_format(format_string) -> bool:
    """Validates a logging format string by attempting to format it with a dummy LogRecord.

    Args:
        format_string (str): The format string to validate.

    Returns:
        bool: True if the format string is valid, False otherwise.
    """
    record = logging.LogRecord(
        name="dummy", level=logging.INFO, pathname="dummy_path", lineno=0, msg="dummy message", args=None, exc_info=None
    )

    formatter = logging.Formatter(format_string)

    try:
        # Attempt to format the record
        formatter.format(record)
    except (KeyError, ValueError, TypeError):
        logger.error("Invalid log format string passed, fallback to default")
        return False
    return True


def configure(
    *,
    log_level: str | None = None,
    log_file: Path | None = None,
    disable: bool | None = False,
    log_env: str | None = None,
    log_format: str | None = None,
    async_file: bool = False,
) -> None:
    """Configure the logger using LANGFLOW environment variables."""
    if disable and log_level is None and log_file is None:
        logger.disable(LOGGER_NAMESPACE)

    if os.getenv("LANGFLOW_LOG_LEVEL", "").upper() in VALID_LOG_LEVELS and log_level is None:
        log_level = os.getenv("LANGFLOW_LOG_LEVEL")
    if log_level is None:
        log_level = "ERROR"

    if log_file is None:
        env_log_file = os.getenv("LANGFLOW_LOG_FILE", "")
        log_file = Path(env_log_file) if env_log_file else None

    if log_env is None:
        log_env = os.getenv("LANGFLOW_LOG_ENV", "")

    logger.remove()  # Remove default handlers
    logger.patch(patching)

    if log_env.lower() == "container" or log_env.lower() == "container_json":
        logger.add(sys.stdout, format="{message}", serialize=True)
    elif log_env.lower() == "container_csv":
        logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss.SSS} {level} {file} {line} {function} {message}")
    else:
        if os.getenv("LANGFLOW_LOG_FORMAT") and log_format is None:
            log_format = os.getenv("LANGFLOW_LOG_FORMAT")

        if log_format is None or not is_valid_log_format(log_format):
            log_format = DEFAULT_LOG_FORMAT

        # pretty print to rich stdout development-friendly but poor performance, It's better for debugger.
        # suggest directly print to stdout in production
        log_stdout_pretty = os.getenv("LANGFLOW_PRETTY_LOGS", "true").lower() == "true"
        if log_stdout_pretty:
            logger.configure(
                handlers=[
                    {
                        "sink": RichHandler(rich_tracebacks=True, markup=True),
                        "format": log_format,
                        "level": log_level.upper(),
                    }
                ]
            )
        else:
            logger.add(sys.stdout, level=log_level.upper(), format=log_format, backtrace=True, diagnose=True)

        if not log_file:
            cache_dir = Path(user_cache_dir(CACHE_DIR_NAME))
            logger.debug(f"Cache directory: {cache_dir}")
            log_file = cache_dir / f"{CACHE_DIR_NAME}.log"
            logger.debug(f"Log file: {log_file}")
        try:
            logger.add(
                sink=AsyncFileSink(log_file) if async_file else log_file,
                level=log_level.upper(),
                format=log_format,
                serialize=True,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Error setting up log file")

    if log_buffer.enabled():
        logger.add(sink=log_buffer.write, format="{time} {level} {message}", serialize=True)

    logger.debug(f"Logger set up with log level: {log_level}")

    setup_uvicorn_logger()
    setup_gunicorn_logger()


def setup_uvicorn_logger() -> None:
    loggers = (logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith("uvicorn."))
    for uvicorn_logger in loggers:
        uvicorn_logger.handlers = []
    logging.getLogger("uvicorn").handlers = [InterceptHandler()]


def setup_gunicorn_logger() -> None:
    logging.getLogger("gunicorn.error").handlers = [InterceptHandler()]
    logging.getLogger("gunicorn.access").handlers = [InterceptHandler()]


class InterceptHandler(logging.Handler):
    """Default handler from examples in loguru documentation.

    See https://loguru.readthedocs.io/en/stable/overview.html#entirely-compatible-with-standard-logging.
    """

    @override
    def emit(self, record) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__ and frame.f_back:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
