import logging
from pathlib import Path

from rich.logging import RichHandler

logger = logging.getLogger("langflow")


def configure(log_level: str = "INFO", log_file: Path = None):  # type: ignore
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    log_level_value = getattr(logging, log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level_value,
        format=log_format,
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    logger.info(f"Logger set up with log level: {log_level_value}({log_level})")
    if log_file:
        logger.info(f"Log file: {log_file}")
