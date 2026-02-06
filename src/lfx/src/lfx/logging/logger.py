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

# Expose logger methods at module level for backwards compatibility
# This is needed because lfx.logging.logger (this module) shadows the logger object
# in lfx.logging.__init__, so code doing `from lfx.logging import logger` gets this module.
info = logger.info
debug = logger.debug
warning = logger.warning
error = logger.error
critical = logger.critical
exception = logger.exception

# Expose async logger methods at module level
aerror = logger.aerror
ainfo = logger.ainfo
adebug = logger.adebug
awarning = logger.awarning
acritical = logger.acritical
aexception = logger.aexception

__all__ = [
    "InterceptHandler",
    "LogConfig",
    "acritical",
    "adebug",
    "aerror",
    "aexception",
    "ainfo",
    "awarning",
    "configure",
    "critical",
    "debug",
    "error",
    "exception",
    "info",
    "logger",
    "setup_gunicorn_logger",
    "setup_uvicorn_logger",
    "warning",
]
