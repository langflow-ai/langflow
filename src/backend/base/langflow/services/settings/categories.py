from typing import Literal

from pydantic import Field

from langflow.serialization.constants import MAX_ITEMS_LENGTH, MAX_TEXT_LENGTH
from langflow.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT

from .common import LangflowBaseSettings


class DatabaseSettings(LangflowBaseSettings):
    """Database related configuration."""

    config_dir: str | None = None
    save_db_in_config_dir: bool = False
    dev: bool = False
    database_url: str | None = None
    database_connection_retry: bool = False
    pool_size: int = 20
    max_overflow: int = 30
    db_connect_timeout: int = 30
    mcp_server_timeout: int = 20
    sqlite_pragmas: dict | None = {"synchronous": "NORMAL", "journal_mode": "WAL"}
    db_driver_connection_settings: dict | None = None
    db_connection_settings: dict | None = {
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "echo": False,
    }


class RedisSettings(LangflowBaseSettings):
    """Redis connection configuration."""

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_url: str | None = None
    redis_cache_expire: int = 3600


class TelemetrySettings(LangflowBaseSettings):
    """Telemetry and analytics configuration."""

    do_not_track: bool = False
    telemetry_base_url: str = "https://langflow.gateway.scarf.sh"
    transactions_storage_enabled: bool = True
    vertex_builds_storage_enabled: bool = True


class ServerSettings(LangflowBaseSettings):
    """Web server related configuration."""

    host: str = "localhost"
    port: int = 7860
    workers: int = 1
    log_level: str = "critical"
    log_file: str | None = "logs/langflow.log"
    alembic_log_file: str = "alembic/alembic.log"
    frontend_path: str | None = None
    open_browser: bool = False
    auto_saving: bool = True
    auto_saving_interval: int = 1000
    health_check_max_retries: int = 5
    max_file_size_upload: int = 100
    deactivate_tracing: bool = False
    max_transactions_to_keep: int = 3000
    max_vertex_builds_to_keep: int = 3000
    max_vertex_builds_per_vertex: int = 2
    webhook_polling_interval: int = 5000
    fs_flows_polling_interval: int = 10000
    ssl_cert_file: str | None = None
    ssl_key_file: str | None = None
    max_text_length: int = MAX_TEXT_LENGTH
    max_items_length: int = MAX_ITEMS_LENGTH
    public_flow_cleanup_interval: int = Field(default=3600, gt=600)
    public_flow_expiration: int = Field(default=86400, gt=600)
    event_delivery: Literal["polling", "streaming", "direct"] = "streaming"
    lazy_load_components: bool = False
    create_starter_projects: bool = True
    update_starter_projects: bool = True
    backend_only: bool = False
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    cache_type: Literal["async", "redis", "memory", "disk"] = "async"
    cache_expire: int = 3600
    variable_store: str = "db"
    disable_track_apikey_usage: bool = False
    remove_api_keys: bool = False
    components_path: list[str] = []
    langchain_cache: str = "InMemoryCache"
    load_flows_path: str | None = None
    bundle_urls: list[str] = []
    store: bool | None = True
    store_url: str | None = "https://api.langflow.store"
    download_webhook_url: str | None = "https://api.langflow.store/flows/trigger/ec611a61-8460-4438-b187-a4f65e5559d4"
    like_webhook_url: str | None = "https://api.langflow.store/flows/trigger/64275852-ec00-45c1-984e-3bff814732da"
    storage_type: str = "local"
    celery_enabled: bool = False
    fallback_to_env_var: bool = True
    store_environment_variables: bool = True
    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    worker_timeout: int = 300
    frontend_timeout: int = 0
    user_agent: str = "langflow"
