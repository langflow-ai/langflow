import asyncio
import contextlib
import json
import os
from pathlib import Path
from shutil import copy2
from typing import Any, Literal

import orjson
import yaml
from aiofile import async_open
from loguru import logger
from pydantic import Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)
from typing_extensions import override

from langflow.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT
from langflow.utils.util_strings import is_valid_database_url

# BASE_COMPONENTS_PATH = str(Path(__file__).parent / "components")
BASE_COMPONENTS_PATH = str(Path(__file__).parent.parent.parent / "components")


def is_list_of_any(field: FieldInfo) -> bool:
    """Check if the given field is a list or an optional list of any type.

    Args:
        field (FieldInfo): The field to be checked.

    Returns:
        bool: True if the field is a list or a list of any type, False otherwise.
    """
    if field.annotation is None:
        return False
    try:
        union_args = field.annotation.__args__ if hasattr(field.annotation, "__args__") else []

        return field.annotation.__origin__ is list or any(
            arg.__origin__ is list for arg in union_args if hasattr(arg, "__origin__")
        )
    except AttributeError:
        return False


class MyCustomSource(EnvSettingsSource):
    @override
    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:  # type: ignore[misc]
        # allow comma-separated list parsing

        # fieldInfo contains the annotation of the field
        if is_list_of_any(field):
            if isinstance(value, str):
                value = value.split(",")
            if isinstance(value, list):
                return value

        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    # Define the default LANGFLOW_DIR
    config_dir: str | None = None
    # Define if langflow db should be saved in config dir or
    # in the langflow directory
    save_db_in_config_dir: bool = False
    """Define if langflow database should be saved in LANGFLOW_CONFIG_DIR or in the langflow directory
    (i.e. in the package directory)."""

    dev: bool = False
    """If True, Langflow will run in development mode."""
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

    # sqlite configuration
    sqlite_pragmas: dict | None = {"synchronous": "NORMAL", "journal_mode": "WAL"}
    """SQLite pragmas to use when connecting to the database."""

    db_driver_connection_settings: dict | None = None
    """Database driver connection settings."""

    db_connection_settings: dict | None = {
        "pool_size": 20,  # Match the pool_size above
        "max_overflow": 30,  # Match the max_overflow above
        "pool_timeout": 30,  # Seconds to wait for a connection from pool
        "pool_pre_ping": True,  # Check connection validity before using
        "pool_recycle": 1800,  # Recycle connections after 30 minutes
        "echo": False,  # Set to True for debugging only
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

    # cache configuration
    cache_type: Literal["async", "redis", "memory", "disk"] = "async"
    """The cache type can be 'async' or 'redis'."""
    cache_expire: int = 3600
    """The cache expire in seconds."""
    variable_store: str = "db"
    """The store can be 'db' or 'kubernetes'."""

    prometheus_enabled: bool = False
    """If set to True, Langflow will expose Prometheus metrics."""
    prometheus_port: int = 9090
    """The port on which Langflow will expose Prometheus metrics. 9090 is the default port."""

    disable_track_apikey_usage: bool = False
    remove_api_keys: bool = False
    components_path: list[str] = []
    langchain_cache: str = "InMemoryCache"
    load_flows_path: str | None = None
    bundle_urls: list[str] = []

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_cache_expire: int = 3600

    # Sentry
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float | None = 1.0
    sentry_profiles_sample_rate: float | None = 1.0

    store: bool | None = True
    store_url: str | None = "https://api.langflow.store"
    download_webhook_url: str | None = "https://api.langflow.store/flows/trigger/ec611a61-8460-4438-b187-a4f65e5559d4"
    like_webhook_url: str | None = "https://api.langflow.store/flows/trigger/64275852-ec00-45c1-984e-3bff814732da"

    storage_type: str = "local"

    celery_enabled: bool = False

    fallback_to_env_var: bool = True
    """If set to True, Global Variables set in the UI will fallback to a environment variable
    with the same name in case Langflow fails to retrieve the variable value."""

    store_environment_variables: bool = True
    """Whether to store environment variables as Global Variables in the database."""
    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    """List of environment variables to get from the environment and store in the database."""
    worker_timeout: int = 300
    """Timeout for the API calls in seconds."""
    frontend_timeout: int = 0
    """Timeout for the frontend API calls in seconds."""
    user_agent: str = "langflow"
    """User agent for the API calls."""
    backend_only: bool = False
    """If set to True, Langflow will not serve the frontend."""

    # Telemetry
    do_not_track: bool = False
    """If set to True, Langflow will not track telemetry."""
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"
    transactions_storage_enabled: bool = True
    """If set to True, Langflow will track transactions between flows."""
    vertex_builds_storage_enabled: bool = True
    """If set to True, Langflow will keep track of each vertex builds (outputs) in the UI for any flow."""

    # Config
    host: str = "localhost"
    """The host on which Langflow will run."""
    port: int = 7860
    """The port on which Langflow will run."""
    workers: int = 1
    """The number of workers to run."""
    log_level: str = "critical"
    """The log level for Langflow."""
    log_file: str | None = "logs/langflow.log"
    """The path to log file for Langflow."""
    alembic_log_file: str = "alembic/alembic.log"
    """The path to log file for Alembic for SQLAlchemy."""
    frontend_path: str | None = None
    """The path to the frontend directory containing build files. This is for development purposes only.."""
    open_browser: bool = False
    """If set to True, Langflow will open the browser on startup."""
    auto_saving: bool = True
    """If set to True, Langflow will auto save flows."""
    auto_saving_interval: int = 1000
    """The interval in ms at which Langflow will auto save flows."""
    health_check_max_retries: int = 5
    """The maximum number of retries for the health check."""
    max_file_size_upload: int = 100
    """The maximum file size for the upload in MB."""
    deactivate_tracing: bool = False
    """If set to True, tracing will be deactivated."""
    max_transactions_to_keep: int = 3000
    """The maximum number of transactions to keep in the database."""
    max_vertex_builds_to_keep: int = 3000
    """The maximum number of vertex builds to keep in the database."""
    max_vertex_builds_per_vertex: int = 2
    """The maximum number of builds to keep per vertex. Older builds will be deleted."""
    webhook_polling_interval: int = 5000
    """The polling interval for the webhook in ms."""
    fs_flows_polling_interval: int = 10000
    """The polling interval in milliseconds for synchronizing flows from the file system."""
    ssl_cert_file: str | None = None
    """Path to the SSL certificate file on the local system."""
    ssl_key_file: str | None = None
    """Path to the SSL key file on the local system."""

    # MCP Server
    mcp_server_enabled: bool = True
    """If set to False, Langflow will not enable the MCP server."""
    mcp_server_enable_progress_notifications: bool = False
    """If set to False, Langflow will not send progress notifications in the MCP server."""

    # Public Flow Settings
    public_flow_cleanup_interval: int = Field(default=3600, gt=600)
    """The interval in seconds at which public temporary flows will be cleaned up.
    Default is 1 hour (3600 seconds). Minimum is 600 seconds (10 minutes)."""
    public_flow_expiration: int = Field(default=86400, gt=600)
    """The time in seconds after which a public temporary flow will be considered expired and eligible for cleanup.
    Default is 24 hours (86400 seconds). Minimum is 600 seconds (10 minutes)."""
    event_delivery: Literal["polling", "streaming", "direct"] = "streaming"
    """How to deliver build events to the frontend. Can be 'polling', 'streaming' or 'direct'."""
    lazy_load_components: bool = False
    """If set to True, Langflow will only partially load components at startup and fully load them on demand.
    This significantly reduces startup time but may cause a slight delay when a component is first used."""

    @field_validator("event_delivery", mode="before")
    @classmethod
    def set_event_delivery(cls, value, info):
        # If workers > 1, we need to use direct delivery
        # because polling and streaming are not supported
        # in multi-worker environments
        if info.data.get("workers", 1) > 1:
            logger.warning("Multi-worker environment detected, using direct event delivery")
            return "direct"
        return value

    @field_validator("dev")
    @classmethod
    def set_dev(cls, value):
        from langflow.settings import set_dev

        set_dev(value)
        return value

    @field_validator("user_agent", mode="after")
    @classmethod
    def set_user_agent(cls, value):
        if not value:
            value = "Langflow"
        import os

        os.environ["USER_AGENT"] = value
        logger.debug(f"Setting user agent to {value}")
        return value

    @field_validator("variables_to_get_from_environment", mode="before")
    @classmethod
    def set_variables_to_get_from_environment(cls, value):
        if isinstance(value, str):
            value = value.split(",")
        return list(set(VARIABLES_TO_GET_FROM_ENVIRONMENT + value))

    @field_validator("log_file", mode="before")
    @classmethod
    def set_log_file(cls, value):
        if isinstance(value, Path):
            value = str(value)
        return value

    @field_validator("config_dir", mode="before")
    @classmethod
    def set_langflow_dir(cls, value):
        if not value:
            from platformdirs import user_cache_dir

            # Define the app name and author
            app_name = "langflow"
            app_author = "langflow"

            # Get the cache directory for the application
            cache_dir = user_cache_dir(app_name, app_author)

            # Create a .langflow directory inside the cache directory
            value = Path(cache_dir)
            value.mkdir(parents=True, exist_ok=True)

        if isinstance(value, str):
            value = Path(value)
        if not value.exists():
            value.mkdir(parents=True, exist_ok=True)

        return str(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def set_database_url(cls, value, info):
        if value and not is_valid_database_url(value):
            msg = f"Invalid database_url provided: '{value}'"
            raise ValueError(msg)

        logger.debug("No database_url provided, trying LANGFLOW_DATABASE_URL env variable")
        if langflow_database_url := os.getenv("LANGFLOW_DATABASE_URL"):
            value = langflow_database_url
            logger.debug("Using LANGFLOW_DATABASE_URL env variable.")
        else:
            logger.debug("No database_url env variable, using sqlite database")
            # Originally, we used sqlite:///./langflow.db
            # so we need to migrate to the new format
            # if there is a database in that location
            if not info.data["config_dir"]:
                msg = "config_dir not set, please set it or provide a database_url"
                raise ValueError(msg)

            from langflow.utils.version import get_version_info
            from langflow.utils.version import is_pre_release as langflow_is_pre_release

            version = get_version_info()["version"]
            is_pre_release = langflow_is_pre_release(version)

            if info.data["save_db_in_config_dir"]:
                database_dir = info.data["config_dir"]
                logger.debug(f"Saving database to config_dir: {database_dir}")
            else:
                database_dir = Path(__file__).parent.parent.parent.resolve()
                logger.debug(f"Saving database to langflow directory: {database_dir}")

            pre_db_file_name = "langflow-pre.db"
            db_file_name = "langflow.db"
            new_pre_path = f"{database_dir}/{pre_db_file_name}"
            new_path = f"{database_dir}/{db_file_name}"
            final_path = None
            if is_pre_release:
                if Path(new_pre_path).exists():
                    final_path = new_pre_path
                elif Path(new_path).exists() and info.data["save_db_in_config_dir"]:
                    # We need to copy the current db to the new location
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
                logger.debug(f"Database already exists at {new_path}, using it")
                final_path = new_path
            elif Path(f"./{db_file_name}").exists():
                try:
                    logger.debug("Copying existing database to new location")
                    copy2(f"./{db_file_name}", new_path)
                    logger.debug(f"Copied existing database to {new_path}")
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to copy database, using default path")
                    new_path = f"./{db_file_name}"
            else:
                final_path = new_path

            if final_path is None:
                final_path = new_pre_path if is_pre_release else new_path

            value = f"sqlite:///{final_path}"

        return value

    @field_validator("components_path", mode="before")
    @classmethod
    def set_components_path(cls, value):
        """Processes and updates the components path list, incorporating environment variable overrides.

        If the `LANGFLOW_COMPONENTS_PATH` environment variable is set and points to an existing path, it is
        appended to the provided list if not already present. If the input list is empty or missing, it is
        set to an empty list.
        """
        if os.getenv("LANGFLOW_COMPONENTS_PATH"):
            logger.debug("Adding LANGFLOW_COMPONENTS_PATH to components_path")
            langflow_component_path = os.getenv("LANGFLOW_COMPONENTS_PATH")
            if Path(langflow_component_path).exists() and langflow_component_path not in value:
                if isinstance(langflow_component_path, list):
                    for path in langflow_component_path:
                        if path not in value:
                            value.append(path)
                    logger.debug(f"Extending {langflow_component_path} to components_path")
                elif langflow_component_path not in value:
                    value.append(langflow_component_path)
                    logger.debug(f"Appending {langflow_component_path} to components_path")

        if not value:
            value = [BASE_COMPONENTS_PATH]
            logger.debug("Setting default components path to components_path")
        else:
            if isinstance(value, Path):
                value = [str(value)]
            elif isinstance(value, list):
                value = [str(p) if isinstance(p, Path) else p for p in value]
            logger.debug("Adding default components path to components_path")

        logger.debug(f"Components path: {value}")
        return value

    model_config = SettingsConfigDict(validate_assignment=True, extra="ignore", env_prefix="LANGFLOW_")

    async def update_from_yaml(self, file_path: str, *, dev: bool = False) -> None:
        new_settings = await load_settings_from_yaml(file_path)
        self.components_path = new_settings.components_path or []
        self.dev = dev

    def update_settings(self, **kwargs) -> None:
        logger.debug("Updating settings")
        for key, value in kwargs.items():
            # value may contain sensitive information, so we don't want to log it
            if not hasattr(self, key):
                logger.debug(f"Key {key} not found in settings")
                continue
            logger.debug(f"Updating {key}")
            if isinstance(getattr(self, key), list):
                # value might be a '[something]' string
                value_ = value
                with contextlib.suppress(json.decoder.JSONDecodeError):
                    value_ = orjson.loads(str(value))
                if isinstance(value_, list):
                    for item in value_:
                        item_ = str(item) if isinstance(item, Path) else item
                        if item_ not in getattr(self, key):
                            getattr(self, key).append(item_)
                    logger.debug(f"Extended {key}")
                else:
                    value_ = str(value_) if isinstance(value_, Path) else value_
                    if value_ not in getattr(self, key):
                        getattr(self, key).append(value_)
                        logger.debug(f"Appended {key}")

            else:
                setattr(self, key, value)
                logger.debug(f"Updated {key}")
            logger.debug(f"{key}: {getattr(self, key)}")

    @classmethod
    @override
    def settings_customise_sources(  # type: ignore[misc]
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (MyCustomSource(settings_cls),)


def save_settings_to_yaml(settings: Settings, file_path: str) -> None:
    with Path(file_path).open("w", encoding="utf-8") as f:
        settings_dict = settings.model_dump()
        yaml.dump(settings_dict, f)


async def load_settings_from_yaml(file_path: str) -> Settings:
    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = Path(__file__).resolve().parent
        file_path_ = Path(current_path) / file_path
    else:
        file_path_ = Path(file_path)

    async with async_open(file_path_.name, encoding="utf-8") as f:
        content = await f.read()
        settings_dict = yaml.safe_load(content)
        settings_dict = {k.upper(): v for k, v in settings_dict.items()}

        for key in settings_dict:
            if key not in Settings.model_fields:
                msg = f"Key {key} not found in settings"
                raise KeyError(msg)
            logger.debug(f"Loading {len(settings_dict[key])} {key} from {file_path}")

    return await asyncio.to_thread(Settings, **settings_dict)
