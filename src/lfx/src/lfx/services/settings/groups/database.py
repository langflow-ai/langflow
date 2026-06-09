import os
from pathlib import Path
from shutil import copy2

from pydantic import BaseModel, field_validator

from lfx.log.logger import logger
from lfx.utils.util_strings import is_valid_database_url, sanitize_database_url


class DatabaseSettings(BaseModel):
    """Database connection, pooling, and migration settings.

    Note: ``database_url`` is validated at the :class:`Settings` level because
    it reads ``config_dir`` from :class:`PathSettings`.
    """

    save_db_in_config_dir: bool = False
    """Define if langflow database should be saved in LANGFLOW_CONFIG_DIR or in the langflow directory
    (i.e. in the package directory)."""

    database_url: str | None = None
    """Database URL for Langflow. If not provided, Langflow will use a SQLite database.
    The driver shall be an async one like `sqlite+aiosqlite` (`sqlite` and `postgresql`
    will be automatically converted to the async drivers `sqlite+aiosqlite` and
    `postgresql+psycopg` respectively)."""

    database_connection_retry: bool = False
    """If True, Langflow will retry to connect to the database if it fails."""

    pool_size: int = 20
    """The number of connections to keep open in the connection pool.
    For high load scenarios, this should be increased based on expected concurrent users."""

    max_overflow: int = 30
    """The number of connections to allow that can be opened beyond the pool size.
    Should be 2x the pool_size for optimal performance under load."""

    db_connect_timeout: int = 30
    """The number of seconds to wait before giving up on a lock to released or establishing a connection to the
    database."""

    migration_lock_namespace: str | None = None
    """Optional namespace identifier for PostgreSQL advisory lock during migrations.
    If not provided, a hash of the database URL will be used. Useful when multiple Langflow
    instances share the same database and need coordinated migration locking."""

    sqlite_pragmas: dict | None = {"synchronous": "NORMAL", "journal_mode": "WAL", "busy_timeout": 30000}
    """SQLite pragmas to use when connecting to the database."""

    db_driver_connection_settings: dict | None = None
    """Database driver connection settings."""

    db_connection_settings: dict | None = {
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "echo": False,
    }
    """Database connection settings optimized for high load scenarios.
    Note: These settings are most effective with PostgreSQL. For SQLite:
    - Reduce pool_size and max_overflow if experiencing lock contention
    - SQLite has limited concurrent write capability even with WAL mode
    - Best for read-heavy or moderate write workloads

    Settings:
    - pool_size: Number of connections to maintain (increase for higher concurrency)
    - max_overflow: Additional connections allowed beyond pool_size
    - pool_timeout: Seconds to wait for an available connection
    - pool_pre_ping: Validates connections before use to prevent stale connections
    - pool_recycle: Seconds before connections are recycled (prevents timeouts)
    - echo: Enable SQL query logging (development only)
    """

    use_noop_database: bool = False
    """If True, disables all database operations and uses a no-op session.
    Controlled by LANGFLOW_USE_NOOP_DATABASE env variable."""

    @field_validator("use_noop_database", mode="before")
    @classmethod
    def set_use_noop_database(cls, value):
        if value:
            logger.info("Running with NOOP database session. All DB operations are disabled.")
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def set_database_url(cls, value, info):
        if value and not is_valid_database_url(value):
            sanitized = sanitize_database_url(value)
            msg = f"Invalid database_url provided: '{sanitized}'"
            raise ValueError(msg)

        if langflow_database_url := os.getenv("LANGFLOW_DATABASE_URL"):
            value = langflow_database_url
            logger.debug("Using LANGFLOW_DATABASE_URL env variable")
        else:
            if not info.data.get("config_dir"):
                msg = "config_dir not set, please set it or provide a database_url"
                raise ValueError(msg)

            from lfx.utils.version import get_version_info
            from lfx.utils.version import is_pre_release as langflow_is_pre_release

            version = get_version_info()["version"]
            is_pre_release = langflow_is_pre_release(version)

            if info.data["save_db_in_config_dir"]:
                database_dir = info.data["config_dir"]
            else:
                try:
                    import langflow

                    database_dir = Path(langflow.__file__).parent.resolve()
                except ImportError:
                    database_dir = Path(__file__).parent.parent.parent.parent.resolve()

            pre_db_file_name = "langflow-pre.db"
            db_file_name = "langflow.db"
            new_pre_path = f"{database_dir}/{pre_db_file_name}"
            new_path = f"{database_dir}/{db_file_name}"
            final_path = None
            if is_pre_release:
                if Path(new_pre_path).exists():
                    final_path = new_pre_path
                elif Path(new_path).exists() and info.data["save_db_in_config_dir"]:
                    logger.debug("Copying existing database to new location")
                    copy2(new_path, new_pre_path)
                    logger.debug(f"Copied existing database to {new_pre_path}")
                elif Path(f"./{db_file_name}").exists() and info.data["save_db_in_config_dir"]:
                    logger.debug("Copying existing database to new location")
                    copy2(f"./{db_file_name}", new_pre_path)
                    logger.debug(f"Copied existing database to {new_pre_path}")
                else:
                    logger.debug(f"Creating new database at {new_pre_path}")
                    final_path = new_pre_path
            elif Path(new_path).exists():
                final_path = new_path
            elif Path(f"./{db_file_name}").exists():
                try:
                    logger.debug("Copying existing database to new location")
                    copy2(f"./{db_file_name}", new_path)
                    logger.debug(f"Copied existing database to {new_path}")
                except OSError:
                    logger.exception("Failed to copy database, using default path")
                    new_path = f"./{db_file_name}"
            else:
                final_path = new_path

            if final_path is None:
                final_path = new_pre_path if is_pre_release else new_path

            value = f"sqlite:///{final_path}"

        return value
