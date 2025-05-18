import logging

def configure_logger(log_level="INFO"):
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )

logger = logging.getLogger("langflow-execution")
