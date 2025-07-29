"""Settings constants for lfx package."""

import os

# Development mode flag - can be overridden by environment variable
DEV = os.getenv("LANGFLOW_DEV", "false").lower() == "true"


def _set_dev(value) -> None:
    global DEV  # noqa: PLW0603
    DEV = value


def set_dev(value) -> None:
    _set_dev(value)
