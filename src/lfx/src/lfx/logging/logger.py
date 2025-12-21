"""Backwards compatibility module for lfx.logging.logger.

This module provides backwards compatibility for code that imports from lfx.logging.logger.
All functionality has been moved to lfx.log.logger.
"""

# Ensure we maintain all the original exports
from lfx.log.logger import (
    InterceptHandler,
    LogConfig,
    configure,
    logger,
    setup_gunicorn_logger,
    setup_uvicorn_logger,
)

__all__ = [
    "InterceptHandler",
    "LogConfig",
    "configure",
    "logger",
    "setup_gunicorn_logger",
    "setup_uvicorn_logger",
]
