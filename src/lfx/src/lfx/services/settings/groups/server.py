import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from lfx.log.logger import logger


class ServerSettings(BaseModel):
    """ASGI server, process, and logging settings."""

    host: str = "localhost"
    """The host on which Langflow will run."""
    port: int = 7860
    """The port on which Langflow will run."""
    runtime_port: int | None = Field(default=None, exclude=True)
    """TEMPORARY: The port detected at runtime after checking for conflicts.
    This field is system-managed only and will be removed in future versions
    when strict port enforcement is implemented (errors will be raised if port unavailable)."""
    workers: int = 1
    """The number of workers to run."""
    log_level: str = "critical"
    """The log level for Langflow."""
    log_file: str | None = "logs/langflow.log"
    """The path to log file for Langflow."""
    alembic_log_file: str = "alembic/alembic.log"
    """The path to log file for Alembic for SQLAlchemy."""
    alembic_log_to_stdout: bool = False
    """If set to True, the log file will be ignored and Alembic will log to stdout."""
    frontend_path: str | None = None
    """The path to the frontend directory containing build files. This is for development purposes only."""
    open_browser: bool = False
    """If set to True, Langflow will open the browser on startup."""
    backend_only: bool = False
    """If set to True, Langflow will not serve the frontend."""
    ssl_cert_file: str | None = None
    """Path to the SSL certificate file on the local system."""
    ssl_key_file: str | None = None
    """Path to the SSL key file on the local system."""
    root_path: str = ""
    """ASGI root_path for deployments behind a reverse proxy that strips a URL
    prefix (e.g. '/langflow').  When set, the MCP SSE transport includes this
    prefix in the POST-back URL so clients can reach the correct endpoint.
    Can also be set via the LANGFLOW_ROOT_PATH environment variable."""
    user_agent: str = "langflow"
    """User agent for the API calls."""

    @field_validator("root_path", mode="before")
    @classmethod
    def validate_root_path(cls, value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            msg = "root_path must be a string"
            raise TypeError(msg)

        value = value.strip()
        if not value or value == "/":
            return ""

        if "://" in value or "?" in value or "#" in value:
            msg = "root_path must be an ASGI path prefix only, without scheme, query string, or fragment"
            raise ValueError(msg)

        if not value.startswith("/"):
            value = f"/{value}"

        return value.rstrip("/")

    @field_validator("runtime_port", mode="before")
    @classmethod
    def validate_runtime_port(cls, value):
        """Parse port from Kubernetes service discovery env vars.

        Kubernetes auto-creates env vars like LANGFLOW_RUNTIME_PORT=tcp://<ip>:<port>
        for services, which collides with the LANGFLOW_ env prefix. Extract the port
        number from URL-like values instead of failing.
        """
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            if value.isdigit():
                return int(value)
            if "://" in value:
                try:
                    parsed_port = urlparse(value).port
                except ValueError:
                    return None
                if parsed_port is not None:
                    return parsed_port
        return None

    @field_validator("log_file", mode="before")
    @classmethod
    def set_log_file(cls, value):
        if isinstance(value, Path):
            value = str(value)
        return value

    @field_validator("user_agent", mode="after")
    @classmethod
    def set_user_agent(cls, value):
        if not value:
            value = "Langflow"
        os.environ["USER_AGENT"] = value
        logger.debug(f"Setting user agent to {value}")
        return value
