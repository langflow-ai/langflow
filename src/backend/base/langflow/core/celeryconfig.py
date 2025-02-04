"""Celery configuration module for Langflow.

This file configures the task broker and result backend based on the
environment variables. When using a database (such as SQLite) as the result
backend, Celery requires the URL to be prefixed with "db+", which is handled
in this configuration.
"""

import os
from pathlib import Path

from loguru import logger

# Environment variables for Redis and Database configuration
langflow_redis_host = os.environ.get("LANGFLOW_REDIS_HOST", "localhost")
langflow_redis_port = os.environ.get("LANGFLOW_REDIS_PORT", 6379)
langflow_database_url = os.environ.get("LANGFLOW_DATABASE_URL")

# =============================================================================
# Broker Configuration
# =============================================================================
# If Redis is configured, use it as broker; otherwise, fallback to RabbitMQ.
if langflow_redis_host and langflow_redis_port:
    broker_url = f"redis://{langflow_redis_host}:{langflow_redis_port}/0"
else:
    mq_user = os.environ.get("RABBITMQ_DEFAULT_USER", "langflow")
    mq_password = os.environ.get("RABBITMQ_DEFAULT_PASS", "langflow")
    broker_url = os.environ.get("BROKER_URL", f"amqp://{mq_user}:{mq_password}@localhost:5672//")

# =============================================================================
# Result Backend Configuration
# =============================================================================
# Celery's SQLAlchemy backend expects a URL that starts with "db+".
# If LANGFLOW_DATABASE_URL (e.g., "sqlite:///./localhost-celredis.db" or a PostgreSQL URL)
# does not start with "db+", this configuration prepares the URL for Celery's SQLAlchemy backend.
# For PostgreSQL URLs, it converts the scheme to "postgresql+psycopg2" and appends a "_celery"
# suffix to the database name to ensure separation from the main application's database.
if langflow_database_url:
    if not langflow_database_url.startswith("db+"):
        # Special handling for PostgreSQL URLs: convert to SQLAlchemy format and update the database name.
        if langflow_database_url.startswith("postgres://"):
            from urllib.parse import urlparse, urlunparse

            parsed_url = urlparse(langflow_database_url)
            # Extract the original database name from the path (e.g., "/postgres").
            original_db = parsed_url.path.lstrip("/")
            # Append '_celery' to the database name for celery-specific operations.
            celery_db = f"{original_db}_celery" if original_db else "celery_db"
            new_path = f"/{celery_db}"
            parsed_url = parsed_url._replace(scheme="postgresql+psycopg2", path=new_path)
            langflow_database_url = urlunparse(parsed_url)
        # Additional handling for SQLite: update the file name to use a separate database file for Celery results.
        elif langflow_database_url.startswith("sqlite:///"):
            # Extract the file path part of the SQLite URL.
            sqlite_path = langflow_database_url[len("sqlite:///") :]
            path = Path(sqlite_path)
            # Append '_celery' to create a distinct database file from Langflow's main DB.
            celery_sqlite_path = f"{path.parent / path.stem}_celery{path.suffix}"
            langflow_database_url = f"sqlite:///{celery_sqlite_path}"
        # Prepend the "db+" prefix so that Celery's SQLAlchemy backend interprets the URL correctly.
        result_backend = f"db+{langflow_database_url}"
    else:
        result_backend = langflow_database_url
else:
    # Fallback to Redis if no database URL is provided.
    result_backend = os.environ.get("RESULT_BACKEND", "redis://localhost:6379/0")

logger.info(f"Using {result_backend} as result backend")

# =============================================================================
# Celery Task Serialization and Timezone Settings
# =============================================================================
accept_content = ["json", "pickle"]  # Supported content types
task_serializer = "json"
result_serializer = "json"
timezone = "UTC"
enable_utc = True

# =============================================================================
# SQLAlchemy Database Backend Specific Settings
# =============================================================================
database_engine_options = {"echo": True}
database_short_lived_sessions = True
database_table_names = {
    "task": "celery_taskmeta",
    "group": "celery_groupmeta",
}

# =============================================================================
# Celery Imports
# =============================================================================
imports = ["langflow.services.task.consumer", "langflow.services.task_orchestration.service"]
