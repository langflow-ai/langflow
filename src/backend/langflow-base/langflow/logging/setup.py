from loguru import logger

LOGGING_CONFIGURED = False


def disable_logging():
    global LOGGING_CONFIGURED
    if not LOGGING_CONFIGURED:
        logger.disable("langflow")
        LOGGING_CONFIGURED = True


def enable_logging():
    global LOGGING_CONFIGURED
    logger.enable("langflow")
    LOGGING_CONFIGURED = True
