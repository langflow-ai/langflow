import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi import FastAPI
from langflow.main import configure_prometheus_settings, create_app, initialize_worker_observability, setup_sentry
from langflow.server import LangflowApplication


def _build_mock_settings_service():
    settings_service = MagicMock()
    settings_service.settings.cors_origins = ["https://app.example.com"]
    settings_service.settings.cors_allow_credentials = True
    settings_service.settings.cors_allow_methods = ["GET", "POST"]
    settings_service.settings.cors_allow_headers = ["Content-Type"]
    settings_service.settings.mcp_server_enabled = False
    settings_service.settings.prometheus_enabled = False
    settings_service.settings.prometheus_port = 9090
    settings_service.settings.root_path = ""
    settings_service.settings.sentry_dsn = None
    settings_service.settings.sentry_traces_sample_rate = 0.5
    settings_service.settings.sentry_profiles_sample_rate = 0.25
    return settings_service


def test_configure_prometheus_settings_applies_valid_port_override():
    settings = SimpleNamespace(prometheus_enabled=False, prometheus_port=9090)

    with patch.dict(os.environ, {"LANGFLOW_PROMETHEUS_PORT": "9100"}):
        configure_prometheus_settings(settings)

    assert settings.prometheus_enabled is True
    assert settings.prometheus_port == 9100


def test_configure_prometheus_settings_rejects_invalid_port():
    settings = SimpleNamespace(prometheus_enabled=False, prometheus_port=9090)

    with (
        patch.dict(os.environ, {"LANGFLOW_PROMETHEUS_PORT": "70000"}),
        pytest.raises(ValueError, match="Invalid port number 70000"),
    ):
        configure_prometheus_settings(settings)


@patch("sentry_sdk.init")
@patch("langflow.main.get_settings_service")
def test_setup_sentry_only_registers_middleware(mock_get_settings, mock_sentry_init):
    settings_service = _build_mock_settings_service()
    settings_service.settings.sentry_dsn = "https://example.invalid/1"
    mock_get_settings.return_value = settings_service

    app = FastAPI()
    setup_sentry(app)

    mock_sentry_init.assert_not_called()
    assert any(middleware.cls.__name__ == "SentryAsgiMiddleware" for middleware in app.user_middleware)


@pytest.mark.asyncio
@patch("sentry_sdk.init")
@patch("langflow.main.get_settings_service")
async def test_initialize_worker_observability_initializes_sentry_after_fork(mock_get_settings, mock_sentry_init):
    settings_service = _build_mock_settings_service()
    settings_service.settings.sentry_dsn = "https://example.invalid/1"
    mock_get_settings.return_value = settings_service
    mock_logger = SimpleNamespace(adebug=AsyncMock(), awarning=AsyncMock())

    with patch("langflow.main.logger", mock_logger):
        await initialize_worker_observability()

    mock_sentry_init.assert_called_once_with(
        dsn="https://example.invalid/1",
        traces_sample_rate=0.5,
        profiles_sample_rate=0.25,
    )
    mock_logger.adebug.assert_awaited_once_with("Sentry SDK initialized in worker process")


@pytest.mark.asyncio
@patch("prometheus_client.start_http_server")
@patch("langflow.main.get_settings_service")
async def test_initialize_worker_observability_starts_prometheus_in_worker(mock_get_settings, mock_start_http_server):
    settings_service = _build_mock_settings_service()
    settings_service.settings.prometheus_enabled = True
    settings_service.settings.prometheus_port = 9101
    mock_get_settings.return_value = settings_service
    mock_logger = SimpleNamespace(adebug=AsyncMock(), awarning=AsyncMock())

    with patch("langflow.main.logger", mock_logger):
        await initialize_worker_observability()

    mock_start_http_server.assert_called_once_with(9101)
    mock_logger.adebug.assert_awaited_once_with("Prometheus metrics server started on port 9101")


@patch("prometheus_client.start_http_server")
@patch("langflow.main.setup_sentry")
@patch("langflow.main.get_settings_service")
def test_create_app_does_not_start_prometheus_in_master(mock_get_settings, mock_setup_sentry, mock_start_http_server):
    settings_service = _build_mock_settings_service()
    settings_service.settings.prometheus_enabled = True
    settings_service.settings.prometheus_port = 9102
    mock_get_settings.return_value = settings_service
    mock_setup_sentry.return_value = None

    create_app()

    mock_start_http_server.assert_not_called()


def test_langflow_application_loads_app_lazily_once():
    app_factory = Mock(return_value="app")
    application = LangflowApplication(app_factory, options={})

    assert application.application is None
    assert app_factory.call_count == 0

    first = application.load()
    second = application.load()

    assert first == "app"
    assert second == "app"
    app_factory.assert_called_once_with()


@patch("langflow.server.gc.freeze")
@patch("langflow.server.gc.collect")
def test_langflow_application_prefork_warns_about_ghost_state(mock_collect, mock_freeze):
    server = MagicMock()
    main_thread = object()
    ghost_thread = MagicMock()
    ghost_thread.is_alive.return_value = True
    ghost_thread.name = "telemetry-thread"
    listen_connection = SimpleNamespace(laddr=("127.0.0.1", 9090), raddr=(), status="LISTEN")
    ghost_connection = SimpleNamespace(
        laddr=("127.0.0.1", 50000),
        raddr=("127.0.0.1", 443),
        status="ESTABLISHED",
    )

    with (
        patch("langflow.server.threading.main_thread", return_value=main_thread),
        patch("langflow.server.threading.enumerate", return_value=[main_thread, ghost_thread]),
        patch("psutil.Process") as mock_process,
    ):
        mock_process.return_value.net_connections.return_value = [listen_connection, ghost_connection]
        LangflowApplication.pre_fork(server, None)

    server.log.warning.assert_any_call(
        "Ghost threads found before fork (these will be dead in workers): %s",
        ["telemetry-thread"],
    )
    server.log.warning.assert_any_call(
        "Ghost TCP connections found before fork (these will be dead in workers): %s",
        [(("127.0.0.1", 50000), ("127.0.0.1", 443), "ESTABLISHED")],
    )
    mock_collect.assert_called_once_with()
    mock_freeze.assert_called_once_with()
