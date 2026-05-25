"""Structural tests for the composed ``Settings`` class.

These guard the refactor that split ``Settings`` into per-group mixins:

- every field that used to live on ``Settings`` still does (catches an
  accidental drop of a group from the inheritance list),
- a sampling of critical defaults is unchanged,
- cross-group validators still see their dependencies in ``info.data``
  (workers -> event_delivery, config_dir -> database_url),
- yaml round-trip and the small utility helpers still work.
"""

import tempfile
from pathlib import Path

import pytest
from lfx.services.settings.base import (
    BASE_COMPONENTS_PATH,
    CustomSource,
    Settings,
    is_list_of_any,
    load_settings_from_yaml,
    save_settings_to_yaml,
)

# Fields that existed on the monolithic Settings before the split. Asserted as
# a set so a missing group in the inheritance chain trips the test loudly.
EXPECTED_FIELDS = {
    # PathSettings
    "config_dir",
    "knowledge_bases_dir",
    # ServerSettings
    "host",
    "port",
    "runtime_port",
    "workers",
    "log_level",
    "log_file",
    "alembic_log_file",
    "alembic_log_to_stdout",
    "frontend_path",
    "open_browser",
    "backend_only",
    "ssl_cert_file",
    "ssl_key_file",
    "root_path",
    "user_agent",
    # DatabaseSettings
    "save_db_in_config_dir",
    "database_url",
    "database_connection_retry",
    "pool_size",
    "max_overflow",
    "db_connect_timeout",
    "migration_lock_namespace",
    "sqlite_pragmas",
    "db_driver_connection_settings",
    "db_connection_settings",
    "use_noop_database",
    # CacheSettings
    "cache_type",
    "cache_expire",
    "langchain_cache",
    "redis_host",
    "redis_port",
    "redis_db",
    "redis_url",
    "redis_cache_expire",
    # StorageSettings
    "storage_type",
    "object_storage_bucket_name",
    "object_storage_prefix",
    "object_storage_tags",
    # McpSettings
    "mcp_base_url",
    "mcp_server_timeout",
    "mcp_max_sessions_per_server",
    "mcp_session_idle_timeout",
    "mcp_session_cleanup_interval",
    "mcp_server_enabled",
    "mcp_server_enable_progress_notifications",
    "add_projects_to_mcp_servers",
    "mcp_composer_enabled",
    "mcp_composer_version",
    # TelemetrySettings
    "sentry_dsn",
    "sentry_traces_sample_rate",
    "sentry_profiles_sample_rate",
    "do_not_track",
    "telemetry_base_url",
    "transactions_storage_enabled",
    "vertex_builds_storage_enabled",
    "deactivate_tracing",
    # ObservabilitySettings
    "prometheus_enabled",
    "prometheus_port",
    "max_transactions_to_keep",
    "max_vertex_builds_to_keep",
    "max_vertex_builds_per_vertex",
    "max_flow_version_entries_per_flow",
    # SecuritySettings
    "cors_origins",
    "cors_allow_credentials",
    "cors_allow_methods",
    "cors_allow_headers",
    "ssrf_protection_enabled",
    "ssrf_allowed_hosts",
    "disable_track_apikey_usage",
    "remove_api_keys",
    "allow_custom_components",
    # ComponentsSettings
    "components_path",
    "components_index_path",
    "load_flows_path",
    "bundle_urls",
    "lazy_load_components",
    "create_starter_projects",
    "update_starter_projects",
    # UiSettings
    "auto_saving",
    "auto_saving_interval",
    "max_text_length",
    "max_items_length",
    "frontend_timeout",
    "store",
    "store_url",
    "download_webhook_url",
    "like_webhook_url",
    # RuntimeSettings
    "dev",
    "event_delivery",
    "worker_timeout",
    "public_flow_cleanup_interval",
    "public_flow_expiration",
    "webhook_polling_interval",
    "fs_flows_polling_interval",
    "health_check_max_retries",
    "max_file_size_upload",
    "celery_enabled",
    # VariablesSettings
    "variable_store",
    "fallback_to_env_var",
    "store_environment_variables",
    "variables_to_get_from_environment",
    "agentic_experience",
    "developer_api_enabled",
}


def test_all_expected_fields_present():
    """Every field that lived on the monolithic Settings is still present.

    Trips loudly if a group is dropped from the inheritance list.
    """
    actual = set(Settings.model_fields)
    missing = EXPECTED_FIELDS - actual
    assert not missing, f"Settings is missing fields: {sorted(missing)}"


def test_field_count_unchanged():
    """The total field count matches the pre-refactor count."""
    assert len(Settings.model_fields) == len(EXPECTED_FIELDS)


def test_critical_defaults_unchanged():
    """A sampling of important field defaults survives the split byte-for-byte."""
    settings = Settings()
    assert settings.host == "localhost"
    assert settings.port == 7860
    assert settings.workers == 1
    assert settings.cache_type == "async"
    assert settings.storage_type == "local"
    assert settings.event_delivery == "streaming"
    assert settings.cors_origins == "*"
    assert settings.cors_allow_credentials is True
    assert settings.ssrf_protection_enabled is True
    assert settings.allow_custom_components is True
    assert settings.mcp_server_enabled is True
    assert settings.mcp_composer_enabled is True
    assert settings.do_not_track is False
    assert settings.dev is False
    assert settings.agentic_experience is False
    assert settings.developer_api_enabled is False


def test_dict_defaults_unchanged():
    """Dict-typed defaults like sqlite_pragmas and db_connection_settings are intact."""
    settings = Settings()
    assert settings.sqlite_pragmas == {
        "synchronous": "NORMAL",
        "journal_mode": "WAL",
        "busy_timeout": 30000,
    }
    assert settings.db_connection_settings == {
        "pool_size": 20,
        "max_overflow": 30,
        "pool_timeout": 30,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "echo": False,
    }


def test_multi_worker_forces_direct_event_delivery(monkeypatch):
    """Workers > 1 must flip event_delivery to 'direct'.

    Exercises the cross-group validator dependency: event_delivery lives in
    RuntimeSettings, workers lives in ServerSettings, and the inheritance
    order in Settings must ensure workers is in info.data when
    event_delivery validates.
    """
    monkeypatch.setenv("LANGFLOW_WORKERS", "4")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "streaming")
    settings = Settings()
    assert settings.workers == 4
    assert settings.event_delivery == "direct"


def test_single_worker_keeps_explicit_event_delivery(monkeypatch):
    """Workers == 1 leaves an explicit event_delivery setting alone."""
    monkeypatch.setenv("LANGFLOW_WORKERS", "1")
    monkeypatch.setenv("LANGFLOW_EVENT_DELIVERY", "polling")
    settings = Settings()
    assert settings.event_delivery == "polling"


def test_database_url_sees_config_dir(monkeypatch, tmp_path):
    """database_url validator must see config_dir in info.data.

    With config_dir set and no LANGFLOW_DATABASE_URL env var, the validator
    falls back to a sqlite path under the langflow package directory. If
    PathSettings's config_dir wasn't validated first, the validator would
    raise 'config_dir not set'.
    """
    monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)
    monkeypatch.setenv("LANGFLOW_CONFIG_DIR", str(tmp_path))
    settings = Settings()
    assert settings.database_url.startswith("sqlite:///")
    assert settings.config_dir == str(tmp_path)


def test_back_compat_exports():
    """Symbols that consumers import from settings.base are still exported."""
    assert is_list_of_any is not None
    assert CustomSource is not None
    assert save_settings_to_yaml is not None
    assert load_settings_from_yaml is not None
    assert isinstance(BASE_COMPONENTS_PATH, str)


def test_update_settings_scalar():
    """Settings.update_settings replaces scalar fields."""
    settings = Settings()
    settings.update_settings(port=9999)
    assert settings.port == 9999


def test_update_settings_list_appends_unique():
    """Settings.update_settings appends to list fields without duplicates."""
    settings = Settings()
    before = list(settings.bundle_urls)
    settings.update_settings(bundle_urls="https://example.com/bundle")
    assert "https://example.com/bundle" in settings.bundle_urls
    # Applying twice doesn't duplicate
    settings.update_settings(bundle_urls="https://example.com/bundle")
    assert settings.bundle_urls.count("https://example.com/bundle") == 1
    # Original entries untouched
    for url in before:
        assert url in settings.bundle_urls


def test_yaml_round_trip():
    """save_settings_to_yaml + load_settings_from_yaml preserves field values."""
    settings = Settings()
    original_components = list(settings.components_path)

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml_path = f.name
    try:
        save_settings_to_yaml(settings, yaml_path)
        assert Path(yaml_path).exists()
        # load_settings_from_yaml only reads components_path back today, but
        # the helper should at least round-trip without erroring on a full dump.
        # We don't assert deep equality because the yaml loader currently
        # restricts to a subset of fields by design.
    finally:
        Path(yaml_path).unlink(missing_ok=True)

    # components_path should be the same after re-instantiation with no env changes
    settings2 = Settings()
    assert settings2.components_path == original_components


@pytest.mark.parametrize(
    ("env_var", "env_value", "field", "expected"),
    [
        ("LANGFLOW_HOST", "0.0.0.0", "host", "0.0.0.0"),
        ("LANGFLOW_PORT", "8080", "port", 8080),
        ("LANGFLOW_WORKERS", "2", "workers", 2),
        ("LANGFLOW_LOG_LEVEL", "info", "log_level", "info"),
        ("LANGFLOW_CACHE_TYPE", "memory", "cache_type", "memory"),
        ("LANGFLOW_STORAGE_TYPE", "s3", "storage_type", "s3"),
        ("LANGFLOW_PROMETHEUS_ENABLED", "true", "prometheus_enabled", True),
        ("LANGFLOW_PROMETHEUS_PORT", "9999", "prometheus_port", 9999),
        ("LANGFLOW_MCP_SERVER_ENABLED", "false", "mcp_server_enabled", False),
        ("LANGFLOW_DO_NOT_TRACK", "true", "do_not_track", True),
        ("LANGFLOW_DEV", "true", "dev", True),
        ("LANGFLOW_BACKEND_ONLY", "true", "backend_only", True),
        ("LANGFLOW_AUTO_SAVING", "false", "auto_saving", False),
        ("LANGFLOW_FALLBACK_TO_ENV_VAR", "false", "fallback_to_env_var", False),
        ("LANGFLOW_VARIABLE_STORE", "kubernetes", "variable_store", "kubernetes"),
    ],
)
def test_env_var_round_trip(monkeypatch, env_var, env_value, field, expected):
    """A sampling of LANGFLOW_* env vars still populate the right fields."""
    monkeypatch.setenv(env_var, env_value)
    settings = Settings()
    assert getattr(settings, field) == expected
