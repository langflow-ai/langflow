from typing import Optional
from loguru import logger
from pathlib import Path
from rich.logging import RichHandler
import os
import orjson
import appdirs


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


def configure(log_level: Optional[str] = None, log_file: Optional[Path] = None):
    if os.getenv("LANGFLOW_LOG_LEVEL") in VALID_LOG_LEVELS and log_level is None:
        log_level = os.getenv("LANGFLOW_LOG_LEVEL")
    if log_level is None:
        log_level = "INFO"
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
        cache_dir = Path(appdirs.user_cache_dir("langflow"))
        log_file = cache_dir / "langflow.log"

    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        sink=str(log_file),
        level=log_level.upper(),
        format=log_format,
        rotation="10 MB",  # Log rotation based on file size
        serialize=True,
    )

    logger.debug(f"Logger set up with log level: {log_level}")
    if log_file:
        logger.info(f"Log file: {log_file}")
