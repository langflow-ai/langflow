"""Worker CLI logging uses the same settings precedence as the API command."""

from __future__ import annotations

import os
import subprocess
import sys
from textwrap import dedent

import pytest

_WORKER_SCRIPT = dedent(
    """
    import asyncio
    import os
    import signal
    import sys
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    import langflow.__main__ as cli
    from langflow.services import deps
    from langflow.services.background_execution import worker
    from langflow.services.background_execution.service import RequestOverridesUnavailableError
    from lfx.log.logger import logger

    class Backend:
        def __init__(self):
            self.claims = 0
            self.stop_event = None

        async def requeue_lost(self, **kwargs):
            return []

        async def claim(self, **kwargs):
            self.claims += 1
            if self.claims == 1:
                raise ConnectionError("scripted claim failure")
            if self.claims == 2:
                return "00000000-0000-0000-0000-000000000001"
            self.stop_event.set()
            return None

    class Runner:
        async def run(self, job_id):
            raise RequestOverridesUnavailableError()

    async def initialize_services():
        await logger.adebug("worker service initialization debug message")
        await logger.ainfo("worker service initialization info message")

    async def teardown():
        print("WORKER_TEARDOWN", flush=True)

    async def build_worker(**kwargs):
        return Backend(), Runner(), teardown

    real_loop = worker.run_worker_loop

    async def run_worker_loop(backend, runner, **kwargs):
        print("WORKER_LOOP_ENTERED", flush=True)
        if mode == "loop_failure":
            raise RuntimeError("worker loop failed")
        backend.stop_event = kwargs["stop_event"]
        await real_loop(backend, runner, **kwargs)

    from langflow.services.deployment_artifacts import activation

    @asynccontextmanager
    async def first_extension():
        try:
            yield
        finally:
            print("FIRST_EXTENSION_CLOSED", flush=True)

    @asynccontextmanager
    async def extension():
        if mode == "signal_on_start":
            os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.Event().wait()
        try:
            yield
        except RuntimeError:
            print("EXTENSION_SAW_WORKER_ERROR", flush=True)
            raise
        if mode == "exit_failure":
            raise RuntimeError("extension shutdown failed")

    mode = os.environ.get("WORKER_TEST_MODE")
    if mode:
        activation.register_worker_lifespan(first_extension)
        activation.register_worker_lifespan(extension)
    activation.load_activation_extensions = lambda: print("ACTIVATION_EXTENSIONS_LOADED", flush=True)
    cli.initialize_services = initialize_services
    def get_settings_service():
        print("SETTINGS_SERVICE_ASKED", flush=True)
        return SimpleNamespace(settings=SimpleNamespace(
            background_backend_is_scaled=True,
            background_lease_ttl_s=45.0,
            background_watchdog_interval_s=None,
        ))

    cli.get_settings_service = get_settings_service
    deps.get_job_service = lambda: None
    worker.build_worker = build_worker
    worker.run_worker_loop = run_worker_loop
    cli.app(args=sys.argv[1:])
    """
)


@pytest.mark.parametrize(
    ("environment_level", "file_level", "cli_level", "show_info", "show_debug"),
    [
        pytest.param(None, None, None, True, False, id="default-info"),
        pytest.param("", None, None, True, False, id="empty-environment-default-info"),
        pytest.param("info", None, None, True, False, id="environment-info"),
        pytest.param("error", None, None, False, False, id="environment-error"),
        pytest.param("error", "DeBuG", None, True, True, id="env-file-overrides-environment"),
        pytest.param("error", None, "INFO", True, False, id="cli-overrides-environment"),
        pytest.param("debug", "info", "error", False, False, id="cli-overrides-env-file"),
        pytest.param("error", "error", "DEBUG", True, True, id="cli-debug-overrides-both"),
    ],
)
def test_worker_cli_logs_startup_and_failures(
    tmp_path, environment_level, file_level, cli_level, show_info, show_debug
):
    env = {key: value for key, value in os.environ.items() if not key.startswith("LANGFLOW_LOG")}
    env["LANGFLOW_CONFIG_DIR"] = str(tmp_path)
    env["LANGFLOW_PRETTY_LOGS"] = "false"
    if environment_level is not None:
        env["LANGFLOW_LOG_LEVEL"] = environment_level
    args = ["worker", "--idle-block-ms", "1"]
    if file_level is not None:
        env_file = tmp_path / "worker.env"
        env_file.write_text(f"LANGFLOW_LOG_LEVEL={file_level}\n", encoding="utf-8")
        args.extend(["--env-file", str(env_file)])
    if cli_level is not None:
        args.extend(["--log-level", cli_level])

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _WORKER_SCRIPT, *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert ("Langflow worker started" in output) is show_info
    assert ("worker service initialization info message" in output) is show_info
    assert ("worker service initialization debug message" in output) is show_debug
    assert "Worker: claim failed" in output
    assert "Worker: runner failed" in output
    assert "Worker: could not decrypt this job's stored request" in output
    assert "Check that every worker shares the API's LANGFLOW_SECRET_KEY." in output


def test_worker_loads_the_activation_extensions_before_it_claims_a_job(tmp_path):
    """A plane's run-time hooks reach a worker only through the activation extension: it must load at startup."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("LANGFLOW_LOG")}
    env["LANGFLOW_CONFIG_DIR"] = str(tmp_path)
    env["LANGFLOW_PRETTY_LOGS"] = "false"

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _WORKER_SCRIPT, "worker", "--idle-block-ms", "1"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert output.index("ACTIVATION_EXTENSIONS_LOADED") < output.index("Worker: claim failed")


def test_worker_creates_the_settings_service_before_any_other_service(tmp_path):
    """Plugin discovery reads lfx.toml from the settings' config directory: settings must exist first."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("LANGFLOW_LOG")}
    env["LANGFLOW_CONFIG_DIR"] = str(tmp_path)
    env["LANGFLOW_PRETTY_LOGS"] = "false"

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _WORKER_SCRIPT, "worker", "--idle-block-ms", "1"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert output.index("SETTINGS_SERVICE_ASKED") < output.index("worker service initialization info message")


@pytest.mark.parametrize(
    ("mode", "error", "loop_entered"),
    [
        pytest.param(
            "signal_on_start",
            None,
            False,
            marks=pytest.mark.skipif(sys.platform == "win32", reason="Unix signals"),
        ),
        ("exit_failure", "extension shutdown failed", True),
        ("loop_failure", "worker loop failed", True),
    ],
)
def test_worker_unwinds_lifespans_and_tears_down(tmp_path, mode, error, loop_entered):
    env = {key: value for key, value in os.environ.items() if not key.startswith("LANGFLOW_LOG")}
    env["LANGFLOW_CONFIG_DIR"] = str(tmp_path)
    env["LANGFLOW_PRETTY_LOGS"] = "false"
    env["WORKER_TEST_MODE"] = mode

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _WORKER_SCRIPT, "worker", "--idle-block-ms", "1"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    output = result.stdout + result.stderr
    assert (result.returncode == 0) is (error is None), output
    assert ("WORKER_LOOP_ENTERED" in output) is loop_entered
    assert output.index("FIRST_EXTENSION_CLOSED") < output.index("WORKER_TEARDOWN")
    assert ("EXTENSION_SAW_WORKER_ERROR" in output) is (mode == "loop_failure")
    if error is not None:
        assert error in output
