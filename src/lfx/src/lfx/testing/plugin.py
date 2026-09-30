"""pytest plugin hooks, fixtures, and marker registration for lfx.testing."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

try:
    import pytest
except ImportError as exc:
    msg = "pytest is required for lfx.testing. Install it with: pip install pytest  (or pip install 'lfx[dev]')"
    raise ImportError(msg) from exc

from lfx.testing.runners import (
    AsyncLocalFlowRunner,
    AsyncRemoteFlowRunner,
    LocalFlowRunner,
    RemoteFlowRunner,
)

# ---------------------------------------------------------------------------
# pytest plugin hooks
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register lfx-specific CLI options."""
    group = parser.getgroup("lfx", "lfx local flow execution options")
    group.addoption(
        "--lfx-env-file",
        dest="lfx_env_file",
        default=None,
        metavar="PATH",
        help="Path to a .env file loaded before each flow execution.",
    )
    group.addoption(
        "--lfx-timeout",
        dest="lfx_timeout",
        default=None,
        type=float,
        metavar="SECONDS",
        help="Default timeout in seconds for flow execution (0 = no limit).",
    )
    group.addoption(
        "--lfx-flow-dir",
        dest="lfx_flow_dir",
        default=None,
        metavar="DIR",
        help="Base directory for resolving relative flow paths (default: cwd).",
    )

    # Guard against duplicate registration when langflow-sdk[testing] is also installed.
    # Both plugins expose the same --langflow-* options; only register them once.
    remote = parser.getgroup("langflow", "Langflow remote integration testing options")
    _remote_opts = {
        "--langflow-env": {
            "dest": "langflow_env",
            "default": None,
            "metavar": "NAME",
            "help": (
                "Named environment from .lfx/environments.yaml or langflow-environments.toml. "
                "When set, flow_runner targets the remote instance instead of running locally."
            ),
        },
        "--langflow-url": {
            "dest": "langflow_url",
            "default": None,
            "metavar": "URL",
            "help": "Base URL of the remote Langflow instance (overrides --langflow-env).",
        },
        "--langflow-api-key": {
            "dest": "langflow_api_key",
            "default": None,
            "metavar": "KEY",
            "help": "API key for the remote Langflow instance.",
        },
        "--langflow-environments-file": {
            "dest": "langflow_environments_file",
            "default": None,
            "metavar": "PATH",
            "help": "Path to environments config file (.yaml or .toml; overrides default lookup).",
        },
    }
    for flag, kwargs in _remote_opts.items():
        with contextlib.suppress(ValueError):
            remote.addoption(flag, **kwargs)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so pytest --strict-markers does not reject them."""
    config.addinivalue_line(
        "markers",
        "lfx_env_file(path): path to a .env file loaded before this test's flow execution",
    )
    config.addinivalue_line(
        "markers",
        "lfx_timeout(seconds): timeout in seconds for this test's flow execution",
    )
    config.addinivalue_line(
        "markers",
        "integration: integration test that requires a live Langflow instance",
    )


_SKIP_NO_REMOTE = (
    "No remote Langflow connection configured. "
    "Pass --langflow-url <URL> or --langflow-env <NAME> to run against a live instance."
)


def _resolve_remote_client(request: pytest.FixtureRequest) -> Any | None:
    """Return a sync SDK client if remote options are configured, else ``None``.

    Priority:
    1. ``--langflow-url`` / ``LANGFLOW_URL`` -- direct URL (with optional ``--langflow-api-key``)
    2. ``--langflow-env`` / ``LANGFLOW_ENV`` -- named environment from TOML/YAML file
    """
    url: str | None = request.config.getoption("langflow_url", default=None) or os.environ.get("LANGFLOW_URL")
    env_name: str | None = request.config.getoption("langflow_env", default=None) or os.environ.get("LANGFLOW_ENV")

    if not url and not env_name:
        return None

    try:
        import langflow_sdk  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("langflow-sdk is required for remote testing. Install: pip install langflow-sdk")

    if url:
        api_key: str | None = request.config.getoption("langflow_api_key", default=None) or os.environ.get(
            "LANGFLOW_API_KEY"
        )
        return langflow_sdk.Client(base_url=url, api_key=api_key)

    # Named environment
    env_file: str | None = request.config.getoption("langflow_environments_file", default=None) or os.environ.get(
        "LANGFLOW_ENVIRONMENTS_FILE"
    )
    try:
        from pathlib import Path as _Path

        from langflow_sdk.environments import get_client  # type: ignore[import-untyped]

        return get_client(env_name, config_file=_Path(env_file) if env_file else None)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Could not configure Langflow environment {env_name!r}: {exc}")


def _resolve_async_remote_client(request: pytest.FixtureRequest) -> Any | None:
    """Return an async SDK client if remote options are configured, else ``None``."""
    url: str | None = request.config.getoption("langflow_url", default=None) or os.environ.get("LANGFLOW_URL")
    env_name: str | None = request.config.getoption("langflow_env", default=None) or os.environ.get("LANGFLOW_ENV")

    if not url and not env_name:
        return None

    try:
        import langflow_sdk  # type: ignore[import-untyped]
    except ImportError:
        pytest.skip("langflow-sdk is required for remote testing. Install: pip install langflow-sdk")

    if url:
        api_key: str | None = request.config.getoption("langflow_api_key", default=None) or os.environ.get(
            "LANGFLOW_API_KEY"
        )
        return langflow_sdk.AsyncClient(base_url=url, api_key=api_key)

    env_file: str | None = request.config.getoption("langflow_environments_file", default=None) or os.environ.get(
        "LANGFLOW_ENVIRONMENTS_FILE"
    )
    try:
        from pathlib import Path as _Path

        from langflow_sdk.environments import get_async_client  # type: ignore[import-untyped]

        return get_async_client(env_name, config_file=_Path(env_file) if env_file else None)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Could not configure Langflow environment {env_name!r}: {exc}")


def _get_marker_arg(request: pytest.FixtureRequest, name: str) -> Any:
    """Return the first positional argument of marker *name*, or ``None``."""
    marker = request.node.get_closest_marker(name)
    return marker.args[0] if marker and marker.args else None


def _resolve_runner_config(
    request: pytest.FixtureRequest,
) -> tuple[str | None, float | None, Path | None]:
    """Return ``(env_file, timeout, base_dir)`` with marker > CLI > env-var precedence."""
    # env_file: marker > --lfx-env-file > LFX_ENV_FILE
    env_file: str | None = (
        _get_marker_arg(request, "lfx_env_file")
        or request.config.getoption("lfx_env_file", default=None)
        or os.environ.get("LFX_ENV_FILE")
    )

    # timeout: marker > --lfx-timeout > LFX_TIMEOUT
    timeout: float | None = _get_marker_arg(request, "lfx_timeout")
    if timeout is None:
        raw_t = request.config.getoption("lfx_timeout", default=None) or os.environ.get("LFX_TIMEOUT")
        if raw_t is not None:
            with contextlib.suppress(TypeError, ValueError):
                timeout = float(raw_t)

    # base_dir: --lfx-flow-dir > LFX_FLOW_DIR > None (defaults to cwd in runner)
    dir_str: str | None = request.config.getoption("lfx_flow_dir", default=None) or os.environ.get("LFX_FLOW_DIR")
    base_dir: Path | None = Path(dir_str) if dir_str else None

    return env_file, timeout, base_dir


@pytest.fixture
def flow_runner(
    request: pytest.FixtureRequest,
) -> LocalFlowRunner | RemoteFlowRunner:
    """Fixture providing a sync flow runner -- local or remote depending on CLI options.

    **Local mode** (default)
        Runs the flow in-process.  Configure with:

        * ``@pytest.mark.lfx_env_file(path)`` / ``@pytest.mark.lfx_timeout(seconds)``
        * ``--lfx-env-file`` / ``--lfx-timeout`` / ``--lfx-flow-dir``
        * ``LFX_ENV_FILE`` / ``LFX_TIMEOUT`` / ``LFX_FLOW_DIR``

    **Remote mode** (when ``--langflow-env`` or ``--langflow-url`` is supplied)
        Calls the live Langflow API.  Requires ``langflow-sdk``.

        * ``--langflow-env <NAME>`` -- named environment from ``.lfx/environments.yaml``
        * ``--langflow-url <URL>`` -- direct URL
        * ``--langflow-api-key <KEY>`` / ``LANGFLOW_API_KEY``
        * ``--langflow-environments-file <PATH>`` / ``LANGFLOW_ENVIRONMENTS_FILE``
        * ``LANGFLOW_ENV`` / ``LANGFLOW_URL``

    Example (local)::

        def test_greeting(flow_runner):
            result = flow_runner("flows/greeting.json", input_value="Hello")
            assert result.ok

    Example (remote -- run with ``pytest --langflow-env staging``)::

        @pytest.mark.integration
        def test_greeting(flow_runner):
            result = flow_runner("greeting-endpoint", "Hello!")
            assert result.first_text_output() is not None
    """
    client = _resolve_remote_client(request)
    if client is not None:
        return RemoteFlowRunner(client)

    env_file, timeout, base_dir = _resolve_runner_config(request)
    return LocalFlowRunner(
        default_env_file=env_file,
        default_timeout=timeout,
        base_dir=base_dir,
    )


@pytest.fixture
def async_flow_runner(
    request: pytest.FixtureRequest,
) -> AsyncLocalFlowRunner | AsyncRemoteFlowRunner:
    """Fixture providing an async flow runner -- local or remote depending on CLI options.

    Same mode-selection logic as :func:`flow_runner`.

    Example (local)::

        async def test_greeting(async_flow_runner):
            result = await async_flow_runner("flows/greeting.json", input_value="Hi")
            assert result.ok

    Example (remote)::

        @pytest.mark.integration
        async def test_greeting(async_flow_runner):
            result = await async_flow_runner("greeting-endpoint", "Hi!")
            assert result.first_text_output() is not None
    """
    client = _resolve_async_remote_client(request)
    if client is not None:
        return AsyncRemoteFlowRunner(client)

    env_file, timeout, base_dir = _resolve_runner_config(request)
    return AsyncLocalFlowRunner(
        default_env_file=env_file,
        default_timeout=timeout,
        base_dir=base_dir,
    )
