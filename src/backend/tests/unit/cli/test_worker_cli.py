"""Worker CLI logging uses the same settings precedence as the API command."""

from __future__ import annotations

import os
import subprocess
import sys
from textwrap import dedent

import pytest

_WORKER_SCRIPT = dedent(
    """
    import sys
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
        pass

    async def build_worker(**kwargs):
        return Backend(), Runner(), teardown

    real_loop = worker.run_worker_loop

    async def run_worker_loop(backend, runner, **kwargs):
        backend.stop_event = kwargs["stop_event"]
        await real_loop(backend, runner, **kwargs)

    cli.initialize_services = initialize_services
    cli.get_settings_service = lambda: SimpleNamespace(settings=SimpleNamespace(
        background_backend_is_scaled=True,
        background_lease_ttl_s=45.0,
        background_watchdog_interval_s=None,
    ))
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
