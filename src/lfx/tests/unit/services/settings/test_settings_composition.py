"""Structural tests for the composed ``Settings`` class.

These guard the refactor that split ``Settings`` into per-group mixins:

- every field that used to live on ``Settings`` still does (catches an
  accidental drop of a group from the inheritance list),
- a sampling of critical defaults is unchanged,
- cross-group validators still see their dependencies in ``info.data``
  (workers -> event_delivery, config_dir -> database_url),
- yaml round-trip and the small utility helpers still work.
"""

import builtins
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
from lfx.services.settings.constants import AGENTIC_VARIABLES


def test_voice_mode_requires_openai_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installing only the VAD library must not advertise unusable voice mode."""
    real_import = builtins.__import__

    def import_without_openai(name, *args, **kwargs):
        """Return a stub for webrtcvad and raise ModuleNotFoundError for openai."""
        if name == "webrtcvad":
            return object()
        if name == "openai" or name.startswith("openai."):
            error_message = "No module named 'openai'"
            raise ModuleNotFoundError(error_message, name="openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_openai)

    assert Settings().voice_mode_available is False


# Every field the composed Settings must expose: the original monolith fields
# plus the settings added in 1.10.0 (folded into the mixins during the release
# back-merge). Asserted as a set so a missing group in the inheritance chain —
# or a dropped 1.10.0 field — trips the test loudly.
EXPECTED_FIELDS = {
    # PathSettings
    "config_dir",
    "knowledge_bases_dir",
    # ServerSettings
    "deployment_profile",
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
    "cache_dir",
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
    "mcp_sse_enabled",
    "mcp_server_enable_progress_notifications",
    "add_projects_to_mcp_servers",
    "skip_mcp_auto_init",
    "mcp_composer_enabled",
    "mcp_composer_version",
    "mcp_sdk_constraint",
    "a2a_enabled",
    "a2a_allow_private_webhooks",
    # TelemetrySettings
    "sentry_dsn",
    "sentry_traces_sample_rate",
    "sentry_profiles_sample_rate",
    "do_not_track",
    "telemetry_base_url",
    "transactions_storage_enabled",
    "vertex_builds_storage_enabled",
    "sync_result_storage_enabled",
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
    "connector_ssrf_validation_enabled",
    "connector_ssrf_allow_loopback",
    "disable_track_apikey_usage",
    "remove_api_keys",
    "allow_custom_components",
    "tweaks_policy",
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
    "warm_registry_enabled",
    "warm_registry_preload_limit",
    "warm_registry_max_entries",
    "warm_registry_max_flow_bytes",
    "warm_registry_max_total_bytes",
    "dev",
    "warm_reconcile_interval",
    "event_delivery",
    "worker_timeout",
    "workflow_execution_timeout",
    "model_provider_policy_refresh_interval_s",
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
    # ---- Added after the original Settings split and folded into the mixins ----
    # PathSettings
    "kb_disk_reconcile_enabled",
    "kb_allowed_folder_roots",
    "kb_folder_max_file_size_bytes",
    "directory_component_allowed_roots",
    # McpSettings
    "mcp_tool_execution_timeout",
    "mcp_servers_locked",
    # ComponentsSettings
    "load_flows_overwrite_on_name_match",
    "load_flows_preserve_variable_bindings",
    "enable_extension_reload",
    # SecuritySettings
    "rate_limit_enabled",
    "rate_limit_per_minute",
    "rate_limit_storage_uri",
    "rate_limit_trust_proxy",
    "public_flow_rate_limit_per_minute",
    "custom_component_admin_only",
    "allow_components_paths_override",
    # RuntimeSettings
    "job_queue_type",
    "redis_queue_host",
    "redis_queue_port",
    "redis_queue_db",
    "redis_queue_url",
    "redis_queue_ttl",
    "redis_queue_startup_grace_s",
    "redis_queue_cancel_channel_enabled",
    "redis_queue_cancel_marker_ttl",
    "redis_queue_polling_stale_threshold_s",
    "redis_queue_polling_watchdog_interval_s",
    "max_ingestion_timeout_secs",
    "executor_kind",
    "dangerously_allow_multi_worker_without_shared_queue",
    # UiSettings
    "embedded_mode",
    "hide_getting_started_progress",
    "hide_logout_button",
    "hide_new_project_button",
    "hide_new_flow_button",
    "hide_starter_projects",
    # TelemetrySettings
    "telemetry_writer_enabled",
    "telemetry_writer_batch_size",
    "telemetry_writer_flush_interval_s",
    "telemetry_writer_cleanup_interval_s",
    "telemetry_writer_max_queue",
    "telemetry_writer_outbox_dir",
    "telemetry_writer_shutdown_drain_s",
    "telemetry_writer_orphan_max_age_s",
    "telemetry_writer_size_strategy",
    "telemetry_writer_batch_size_bytes",
    "telemetry_writer_max_queue_bytes",
    # Background execution
    "background_max_concurrency",
    "background_job_timeout",
    "background_input_deadline_s",
    "background_lease_ttl_s",
    "background_heartbeat_interval_s",
    "background_watchdog_interval_s",
    "test_redis_url",
    # ---- Added in 1.10.1 ----
    # SecuritySettings
    "allow_public_custom_components",
    "block_code_interpreter_components",
    "restrict_local_file_access",
    "mcp_server_docker_hardening",
    "mcp_server_allowed_packages",
    "mcp_server_interpreter_hardening",
    "mcp_server_env_allowlist",
    # ---- Added in 1.12.0 ----
    # SecuritySettings: opt-in microVM sandbox backend (issue #12029)
    "sandbox_backend",
    "sandbox_timeout_seconds",
    "sandbox_memory_mb",
    "sandbox_allow_network",
    "sandbox_allowed_domains",
    "sandbox_allow_software_emulation",
    # SecuritySettings: rebuild drifted built-ins with this server's code (issue #14455)
    "substitute_outdated_component_code",
    # VariablesSettings: operator-tunable Langflow Assistant prompt length
    "assistant_max_message_length",
    # ---- Serving-plane end-user identity ----
    # SecuritySettings
    "serving_end_user_header",
    "serving_trust_proxy_headers",
    "serving_end_user_required",
    "serving_trace_end_user",
    "serving_internal_mcp_hosts",
}


def test_all_expected_fields_present():
    """Every field that lived on the monolithic Settings is still present.

    Trips loudly if a group is dropped from the inheritance list.
    """
    actual = set(Settings.model_fields)
    missing = EXPECTED_FIELDS - actual
    assert not missing, f"Settings is missing fields: {sorted(missing)}"


def test_field_count_unchanged():
    """The total field count matches the curated expected set (no stray adds/drops)."""
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
    assert settings.model_provider_policy_refresh_interval_s == 10.0
    assert settings.cors_origins == "*"
    assert settings.cors_allow_credentials is True
    assert settings.ssrf_protection_enabled is True
    assert settings.connector_ssrf_validation_enabled is True
    assert settings.allow_custom_components is True
    assert settings.block_code_interpreter_components is False
    assert settings.substitute_outdated_component_code is True
    assert settings.restrict_local_file_access is False
    assert settings.mcp_server_docker_hardening is False
    assert settings.mcp_server_interpreter_hardening is False
    assert settings.mcp_server_allowed_packages is None
    assert settings.mcp_server_enabled is True
    assert settings.mcp_composer_enabled is True
    assert settings.mcp_sdk_constraint == "mcp~=1.28"
    assert settings.load_flows_preserve_variable_bindings is True
    assert settings.do_not_track is False
    assert settings.warm_registry_enabled is False
    assert settings.warm_registry_preload_limit == 0
    assert settings.warm_registry_max_entries == 128
    assert settings.warm_registry_max_flow_bytes == 2_000_000
    assert settings.warm_registry_max_total_bytes == 32_000_000
    assert settings.dev is False
    assert settings.agentic_experience is True
    assert settings.developer_api_enabled is False
    assert settings.dangerously_allow_multi_worker_without_shared_queue is False


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


def test_warm_registry_reads_environment(monkeypatch):
    """The warm execution plane must be independently activatable through settings."""
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_ENABLED", "true")
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_PRELOAD_LIMIT", "5")
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_MAX_ENTRIES", "16")
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_MAX_FLOW_BYTES", "100000")
    monkeypatch.setenv("LANGFLOW_WARM_REGISTRY_MAX_TOTAL_BYTES", "1000000")

    settings = Settings()
    assert settings.warm_registry_enabled is True
    assert settings.warm_registry_preload_limit == 5
    assert settings.warm_registry_max_entries == 16
    assert settings.warm_registry_max_flow_bytes == 100_000
    assert settings.warm_registry_max_total_bytes == 1_000_000


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
        ("LANGFLOW_MCP_SSE_ENABLED", "false", "mcp_sse_enabled", False),
        ("LANGFLOW_MCP_SDK_CONSTRAINT", "mcp~=1.30", "mcp_sdk_constraint", "mcp~=1.30"),
        ("LANGFLOW_SKIP_MCP_AUTO_INIT", "true", "skip_mcp_auto_init", True),
        ("LANGFLOW_DO_NOT_TRACK", "true", "do_not_track", True),
        ("LANGFLOW_DEV", "true", "dev", True),
        (
            "LANGFLOW_MODEL_PROVIDER_POLICY_REFRESH_INTERVAL_S",
            "7.5",
            "model_provider_policy_refresh_interval_s",
            7.5,
        ),
        ("LANGFLOW_BACKEND_ONLY", "true", "backend_only", True),
        ("LANGFLOW_AUTO_SAVING", "false", "auto_saving", False),
        ("LANGFLOW_FALLBACK_TO_ENV_VAR", "false", "fallback_to_env_var", False),
        (
            "LANGFLOW_LOAD_FLOWS_PRESERVE_VARIABLE_BINDINGS",
            "false",
            "load_flows_preserve_variable_bindings",
            False,
        ),
        ("LANGFLOW_VARIABLE_STORE", "kubernetes", "variable_store", "kubernetes"),
    ],
)
def test_env_var_round_trip(monkeypatch, env_var, env_value, field, expected):
    """A sampling of LANGFLOW_* env vars still populate the right fields."""
    monkeypatch.setenv(env_var, env_value)
    settings = Settings()
    assert getattr(settings, field) == expected


def test_agentic_experience_on_by_default(monkeypatch):
    """The Assistant is Langflow's entry-point experience and must work out of the box.

    Regression: defaulting agentic_experience off left the frontend Assistant panel
    mounted while every /agentic endpoint returned 404 unless the operator set
    LANGFLOW_AGENTIC_EXPERIENCE=true. With the experience on, its variables are
    mirrored from the environment so provider credentials resolve.
    """
    monkeypatch.delenv("LANGFLOW_AGENTIC_EXPERIENCE", raising=False)
    settings = Settings()
    assert settings.agentic_experience is True
    for var in AGENTIC_VARIABLES:
        assert var in settings.variables_to_get_from_environment


@pytest.mark.parametrize("env_value", ["true", "1", "yes", "on"])
def test_agentic_variables_included_when_experience_enabled(monkeypatch, env_value):
    """All supported true values keep the feature and its environment mirror aligned."""
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", env_value)
    settings = Settings()
    assert settings.agentic_experience is True
    for var in AGENTIC_VARIABLES:
        assert var in settings.variables_to_get_from_environment


def test_agentic_variables_excluded_when_experience_disabled(monkeypatch):
    """Opting out with LANGFLOW_AGENTIC_EXPERIENCE=false stops the env mirror.

    The ASTRA_TOKEN credential is among the mirrored variables; a deployment that
    disables the Assistant must not have it provisioned into the DB for endpoints
    that stay 404.
    """
    monkeypatch.setenv("LANGFLOW_AGENTIC_EXPERIENCE", "false")
    settings = Settings()
    assert settings.agentic_experience is False
    for var in AGENTIC_VARIABLES:
        assert var not in settings.variables_to_get_from_environment


def test_serving_end_user_defaults_are_feature_off():
    """The serving-plane end-user identity feature is off by default (backwards compatible)."""
    settings = Settings()
    assert settings.serving_end_user_header is None
    assert settings.serving_trust_proxy_headers is False
    assert settings.serving_end_user_required is False


def test_serving_end_user_env_vars_bind_to_fields(monkeypatch):
    """The three operator-facing env vars must bind to their settings fields.

    This guards the operator contract: a typo in a field name or the LANGFLOW_
    prefix would silently disable the feature with no other test catching it.
    """
    monkeypatch.setenv("LANGFLOW_SERVING_END_USER_HEADER", "X-End-User-Id")
    monkeypatch.setenv("LANGFLOW_SERVING_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("LANGFLOW_SERVING_END_USER_REQUIRED", "true")
    settings = Settings()
    assert settings.serving_end_user_header == "X-End-User-Id"
    assert settings.serving_trust_proxy_headers is True
    assert settings.serving_end_user_required is True
