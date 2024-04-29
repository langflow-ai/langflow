import logging
import os
from pathlib import Path
from typing import Optional

import orjson
from loguru import logger
from platformdirs import user_cache_dir
from rich.logging import RichHandler

VALID_LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def serialize(record):
    subset = {
        "timestamp": record["time"].timestamp(),
        "message": record["message"],
        "level": record["level"].name,
        "module": record["module"],
    }
    return orjson.dumps(subset)


def patching(record):
    record["extra"]["serialized"] = serialize(record)


def configure(log_level: Optional[str] = None, log_file: Optional[Path] = None, disable: Optional[bool] = False):
    if disable and log_level is None and log_file is None:
        logger.disable("langflow")
    if os.getenv("LANGFLOW_LOG_LEVEL", "").upper() in VALID_LOG_LEVELS and log_level is None:
        log_level = os.getenv("LANGFLOW_LOG_LEVEL")
    if log_level is None:
        log_level = "ERROR"
    # Human-readable
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> - <level>"
        "{level: <8}</level> - {module} - <level>{message}</level>"
    )

    # log_format = log_format_dev if log_level.upper() == "DEBUG" else log_format_prod
    logger.remove()  # Remove default handlers
    logger.patch(patching)
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
