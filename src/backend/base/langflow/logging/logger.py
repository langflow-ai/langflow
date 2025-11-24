from lfx.log.logger import configure, logger

# Expose logger methods at module level for backwards compatibility
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
    "warning",
]
