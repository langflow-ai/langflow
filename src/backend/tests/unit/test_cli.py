import json
import os
import select
import signal
import socket
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import typer
from langflow.__main__ import (
    DIRECT_UVICORN_PLATFORMS,
    MULTI_WORKER_BYPASS_ENV_VAR,
    CommandInterrupted,
    _create_superuser,
    api_key_banner,
    app,
    build_direct_uvicorn_kwargs,
    clamp_uvicorn_workers,
    ensure_multi_worker_safe,
    get_number_of_workers,
    interruption_reported,
    multi_worker_bypass_warning,
    use_direct_uvicorn,
)
from lfx.services import deps
from lfx.services.settings.service import SettingsService


@pytest.fixture(scope="module")
def default_settings():
    return [
        "--backend-only",
        "--no-open-browser",
    ]


def test_components_path(runner, default_settings, tmp_path):
    """Process CLI settings synchronously without leaving a server or capture thread running."""
    temp_dir = tmp_path / "components"
    temp_dir.mkdir(exist_ok=True)
    original_settings = deps.get_settings_service()
    settings_service = SettingsService(
        settings=original_settings.settings.model_copy(deep=True),
        auth_settings=original_settings.auth_settings.model_copy(deep=True),
    )
    # Stop at app setup, after the real CLI option handling has updated settings.
    # CliRunner replaces process-wide streams, so it must finish before another test starts.
    with (
        patch("langflow.__main__.get_settings_service", return_value=settings_service),
        patch("langflow.__main__.configure"),
        patch("langflow.__main__.use_direct_uvicorn", return_value=True),
        patch("langflow.__main__.setup_app", side_effect=typer.Exit(code=0)) as setup_app,
    ):
        result = runner.invoke(app, ["run", "--components-path", str(temp_dir), *default_settings])

    assert result.exit_code == 0, result.output
    setup_app.assert_called_once()
    assert str(temp_dir) in settings_service.settings.components_path


@pytest.mark.xdist_group(name="serial-superuser-tests")
class TestSuperuserCommand:
    """Deterministic tests for the superuser CLI command."""

    @pytest.mark.asyncio
    async def test_additional_superuser_requires_auth_production(self, client, active_super_user):  # noqa: ARG002
        """Test additional superuser creation requires authentication in production."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser without auth - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_additional_superuser_blocked_in_auto_login_mode(self, client, active_super_user):  # noqa: ARG002
        """Test additional superuser creation blocked when AUTO_LOGIN=true."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            # Configure settings for AUTO_LOGIN mode
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.asyncio
    async def test_cli_disabled_blocks_creation(self, client):  # noqa: ARG002
        """Test ENABLE_SUPERUSER_CLI=false blocks superuser creation."""
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
        ):
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": True, "ENABLE_SUPERUSER_CLI": False})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("admin", "password", None)

            assert exc_info.value.exit_code == 1

    @pytest.mark.skip(reason="Skip -- default superuser is created by initialize_services() function")
    @pytest.mark.asyncio
    async def test_auto_login_uses_bootstrap_superuser(self, client):
        """Test AUTO_LOGIN=true bootstraps the configured superuser."""
        # Since client fixture already creates default user, we need to test in a clean DB scenario
        # But that's why this test is skipped - the behavior is already handled by initialize_services

    @pytest.mark.asyncio
    async def test_failed_auth_token_validation(self, client, active_super_user):  # noqa: ARG002
        """Test failed superuser creation with invalid auth token."""
        # We already have active_super_user from the fixture, so we're not in first setup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_settings,
            patch("langflow.__main__.get_settings_service") as mock_settings2,
            patch("langflow.__main__.get_current_user_from_access_token", side_effect=Exception("Invalid token")),
            patch("langflow.__main__.check_key", return_value=None),
        ):
            # Configure settings for production mode (AUTO_LOGIN=False)
            mock_auth_settings = type("MockAuthSettings", (), {"AUTO_LOGIN": False, "ENABLE_SUPERUSER_CLI": True})()
            mock_settings.return_value.auth_settings = mock_auth_settings
            mock_settings2.return_value.auth_settings = mock_auth_settings

            # Try to create a superuser with invalid token - should fail
            with pytest.raises(typer.Exit) as exc_info:
                await _create_superuser("newuser", "newpass", "invalid-token")

            assert exc_info.value.exit_code == 1


def test_get_number_of_workers():
    """Test that get_number_of_workers uses cpu_count on Linux."""
    with (
        patch("langflow.__main__.platform.system", return_value="Linux"),
        patch("langflow.__main__.cpu_count", return_value=4),
    ):
        # Test default behavior (None)
        workers = get_number_of_workers(None)
        assert workers == (4 * 2) + 1  # 9 workers

        # Test explicit value is respected
        workers = get_number_of_workers(2)
        assert workers == 2


# ---------------------------------------------------------------------------
# Platform routing for `langflow run` startup.
#
# These tests pin the policy that on Windows and macOS we bypass Gunicorn and
# run uvicorn directly against a pre-built app object, while on Linux we use
# Gunicorn (which forks workers). Also pins the worker-clamp behaviour, which
# exists because uvicorn refuses to spawn multiple workers from an app object
# (it requires an import string).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Darwin", True),
        ("Windows", True),
        ("Linux", False),
        ("FreeBSD", False),
    ],
)
def test_use_direct_uvicorn_routes_by_platform(system, expected):
    assert use_direct_uvicorn(system=system) is expected


def test_direct_uvicorn_platforms_constant_is_stable():
    # Guards against accidental drift; the launch site relies on this exact set.
    assert DIRECT_UVICORN_PLATFORMS == ("Windows", "Darwin")


@pytest.mark.parametrize("system", ["Darwin", "Windows"])
def test_clamp_uvicorn_workers_caps_to_one_on_direct_uvicorn(system):
    """Workers > 1 must be clamped to 1 with a warning on direct-uvicorn platforms."""
    # langflow uses loguru, not stdlib logging — patch the logger method
    # directly rather than relying on caplog.
    with patch("langflow.__main__.logger") as mock_logger:
        assert clamp_uvicorn_workers(4, system=system) == 1
    mock_logger.warning.assert_called_once()
    # The warning should mention what we clamped and why, so users can
    # diagnose `langflow run --workers N` regressing to a single worker.
    fmt, *args = mock_logger.warning.call_args.args
    assert "workers > 1" in fmt, f"warning did not explain the clamp: {fmt!r}"
    assert system in args, f"warning did not mention platform={system}: args={args!r}"
    assert 4 in args, f"warning did not include the requested worker count: args={args!r}"


def test_clamp_uvicorn_workers_passes_through_on_linux():
    # Linux uses Gunicorn — no clamping should happen here.
    assert clamp_uvicorn_workers(4, system="Linux") == 4


@pytest.mark.parametrize("system", ["Darwin", "Windows", "Linux"])
def test_clamp_uvicorn_workers_one_is_noop(system):
    assert clamp_uvicorn_workers(1, system=system) == 1


# ---------------------------------------------------------------------------
# Direct-uvicorn kwargs shape.
#
# These pin the option set passed to ``uvicorn.run(app, **kwargs)`` on the
# Windows/macOS path. They exist because the previous inline call silently
# dropped TLS cert/key options, regressing HTTPS startup. Treat any field
# omission as a behaviour change and update the test deliberately.
# ---------------------------------------------------------------------------


def _kwargs(**overrides):
    """Build ``build_direct_uvicorn_kwargs`` arguments with sensible defaults."""
    base = {
        "host": "0.0.0.0",  # noqa: S104
        "port": 7860,
        "log_level": "info",
        "workers": 1,
        "loop": "asyncio",
        "ssl_cert_file_path": None,
        "ssl_key_file_path": None,
        "system": "Darwin",
    }
    base.update(overrides)
    return base


def test_build_direct_uvicorn_kwargs_forwards_tls_paths():
    """TLS cert/key must reach uvicorn under uvicorn's ``ssl_certfile``/``ssl_keyfile`` names."""
    result = build_direct_uvicorn_kwargs(
        **_kwargs(ssl_cert_file_path="/etc/cert.pem", ssl_key_file_path="/etc/key.pem")
    )
    assert result["ssl_certfile"] == "/etc/cert.pem"
    assert result["ssl_keyfile"] == "/etc/key.pem"


def test_build_direct_uvicorn_kwargs_starts_each_request_task_from_a_clean_context():
    """Direct-uvicorn startup must opt into uvicorn's per-request context reset.

    Same reason as ``LangflowUvicornWorker.CONFIG_KWARGS`` on the Gunicorn path: a pipelined
    request is started from inside the finishing request's task, and the copied context
    otherwise carries that request's ended server span into the new one, which OpenTelemetry
    reports as nesting. Kept on both paths so platform parity does not drift.

    Asserted through a real ``uvicorn.Config`` so a renamed or rejected option fails here.
    """
    import uvicorn

    config = uvicorn.Config("langflow.main:create_app", **build_direct_uvicorn_kwargs(**_kwargs()))

    assert config.reset_contextvars is True


def test_build_direct_uvicorn_kwargs_forwards_none_when_no_tls():
    # Plain HTTP startup: cert/key remain None so uvicorn doesn't try to load anything.
    result = build_direct_uvicorn_kwargs(**_kwargs())
    assert result["ssl_certfile"] is None
    assert result["ssl_keyfile"] is None


def test_build_direct_uvicorn_kwargs_clamps_workers_on_direct_platforms():
    result = build_direct_uvicorn_kwargs(**_kwargs(workers=4, system="Darwin"))
    assert result["workers"] == 1


def test_build_direct_uvicorn_kwargs_does_not_clamp_on_linux():
    # Defensive: the helper is only called from the direct-uvicorn branch, but
    # if it ever gets reused on Linux the clamp must remain a no-op there.
    result = build_direct_uvicorn_kwargs(**_kwargs(workers=4, system="Linux"))
    assert result["workers"] == 4


# ---------------------------------------------------------------------------
# api_key_banner: clipboard must be best-effort.
#
# Regression guard for #12341: pyperclip raises in headless/Docker/SSH
# environments because no clipboard mechanism is available. The banner must
# still print the API key (the only time it's ever shown) instead of crashing.
# ---------------------------------------------------------------------------


def test_api_key_banner_survives_pyperclip_failure(capsys):
    """Clipboard failure must not crash the banner — the key is the user's only copy."""
    api_key_obj = SimpleNamespace(api_key="lf-test-12341")

    with patch("pyperclip.copy", side_effect=Exception("Pyperclip could not find a copy/paste mechanism")):
        api_key_banner(api_key_obj)

    output = capsys.readouterr().out
    assert "lf-test-12341" in output, "API key must still be displayed when clipboard fails"
    assert "clipboard" not in output.lower(), "no clipboard hint should appear when copy failed"


def test_api_key_banner_shows_clipboard_hint_on_success(capsys):
    """Happy path: when clipboard copy succeeds, the paste hint is shown."""
    api_key_obj = SimpleNamespace(api_key="lf-test-ok")

    with patch("pyperclip.copy") as mock_copy:
        api_key_banner(api_key_obj)

    mock_copy.assert_called_once_with("lf-test-ok")
    output = capsys.readouterr().out
    assert "lf-test-ok" in output
    assert "clipboard" in output.lower()


def test_build_direct_uvicorn_kwargs_pins_full_shape():
    """Drift guard: the exact key set passed to uvicorn.run must stay stable."""
    result = build_direct_uvicorn_kwargs(**_kwargs())
    # If uvicorn options change deliberately, update this set explicitly so
    # reviewers see the diff.
    assert set(result.keys()) == {
        "host",
        "port",
        "log_level",
        "reload",
        "workers",
        "loop",
        "ssl_certfile",
        "ssl_keyfile",
        "forwarded_allow_ips",
        "reset_contextvars",
    }
    assert result["reload"] is False


# ---------------------------------------------------------------------------
# ensure_multi_worker_safe: refuse to boot with the in-memory queue and N>1
# workers. The bug is silent: ~45-66% of build polls return "Job not found"
# because Gunicorn round-robins the POST and the follow-up GET across workers,
# but the queue is worker-local.
# ---------------------------------------------------------------------------


def test_ensure_multi_worker_safe_allows_single_worker():
    """Single worker means no cross-worker routing; must not raise."""
    ensure_multi_worker_safe(num_workers=1)


def _settings_service_with_queue(queue_type: str, *, bypass: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(
            job_queue_type=queue_type,
            dangerously_allow_multi_worker_without_shared_queue=bypass,
        )
    )


def test_ensure_multi_worker_safe_refuses_multiple_workers():
    """Default in-memory queue + workers > 1 must refuse to start."""
    with (
        patch("langflow.__main__.get_settings_service", return_value=_settings_service_with_queue("asyncio")),
        pytest.raises(RuntimeError) as exc_info,
    ):
        ensure_multi_worker_safe(num_workers=3)

    msg = str(exc_info.value)
    assert "3 workers" in msg
    assert "in-memory job queue" in msg


def test_ensure_multi_worker_safe_error_lists_workarounds():
    """Error must point operators at concrete fixes, not just describe the bug."""
    with (
        patch("langflow.__main__.get_settings_service", return_value=_settings_service_with_queue("asyncio")),
        pytest.raises(RuntimeError) as exc_info,
    ):
        ensure_multi_worker_safe(num_workers=3)

    msg = str(exc_info.value)
    # Shared queue is the proper fix for any event_delivery mode.
    assert "LANGFLOW_JOB_QUEUE_TYPE=redis" in msg
    # Single worker sidesteps cross-worker routing entirely.
    assert "--workers 1" in msg
    # event_delivery=direct works but cannot be enforced at startup, so it's a
    # note, not a "pick one of" option — call that out explicitly.
    assert "event_delivery=direct" in msg


def test_ensure_multi_worker_safe_allows_redis_queue():
    """Redis-backed job queue shares state across workers; multi-worker is safe."""
    with patch("langflow.__main__.get_settings_service", return_value=_settings_service_with_queue("redis")):
        ensure_multi_worker_safe(num_workers=4)


# ---------------------------------------------------------------------------
# ensure_multi_worker_safe: LANGFLOW_DANGEROUSLY_ALLOW_MULTI_WORKER_WITHOUT_SHARED_QUEUE
# turns the refusal into a loud warning. The flag does not make multi-worker
# safe — it only lets a headless deployment that never touches the UI or MCP
# over SSE trade those features for worker throughput without standing up Redis.
# ---------------------------------------------------------------------------


def _capture_startup_warnings(monkeypatch) -> list[str]:
    """Record ``logger.warning`` calls made by ``langflow.__main__``.

    ``logger`` is a structlog BoundLogger that may be filtered out entirely at
    the configured level, so asserting on caplog would make the test depend on
    log configuration. Swapping the module-level symbol for a recorder captures
    exactly what the guard emits.
    """
    captured: list[str] = []

    class _Recorder:
        def warning(self, msg: str, *args: object, **_kwargs: object) -> None:
            captured.append(msg % args if args else msg)

        def __getattr__(self, _name: str):  # pragma: no cover - swallow other levels
            return lambda *_a, **_k: None

    import langflow.__main__ as langflow_main

    monkeypatch.setattr(langflow_main, "logger", _Recorder())
    return captured


def test_ensure_multi_worker_safe_bypass_allows_multiple_workers(monkeypatch):
    """The opt-in flag must let the in-memory queue boot with workers > 1."""
    _capture_startup_warnings(monkeypatch)
    with patch(
        "langflow.__main__.get_settings_service",
        return_value=_settings_service_with_queue("asyncio", bypass=True),
    ):
        ensure_multi_worker_safe(num_workers=4)


def test_ensure_multi_worker_safe_bypass_warns_about_ui_and_mcp_sse(monkeypatch):
    """Booting under the bypass must name the two features it breaks outright."""
    warnings = _capture_startup_warnings(monkeypatch)
    with patch(
        "langflow.__main__.get_settings_service",
        return_value=_settings_service_with_queue("asyncio", bypass=True),
    ):
        ensure_multi_worker_safe(num_workers=4)

    assert len(warnings) == 1
    msg = warnings[0]
    # The operator must be able to tie a broken editor/playground back to this flag.
    assert "/build" in msg
    assert "playground" in msg
    # MCP over SSE needs the stream and its POST endpoint in one process; the
    # warning has to point at the transport that does work.
    assert "SSE" in msg
    assert "Streamable HTTP" in msg
    # ...and it must still name the supported alternative.
    assert "LANGFLOW_JOB_QUEUE_TYPE=redis" in msg
    # The flag that caused this is named so the config is greppable.
    assert MULTI_WORKER_BYPASS_ENV_VAR in msg


def test_multi_worker_bypass_warning_lists_the_degraded_subsystems():
    """Every subsystem that silently degrades to per-worker must be spelled out.

    These are not startup failures — they are behaviors that quietly change
    meaning under multiple workers, so the boot warning is the only place an
    operator learns about them.
    """
    from langflow.services.background_execution.live_bus import _DURABLE_POLL_INTERVAL_S

    msg = multi_worker_bypass_warning(num_workers=4)

    # Reattach falls back to polling the durable log; quote the real interval so
    # the warning cannot drift from the constant the bus actually uses.
    assert str(_DURABLE_POLL_INTERVAL_S) in msg
    # Rate limits are counted per worker unless the storage URI is shared.
    assert "LANGFLOW_RATE_LIMIT_STORAGE_URI" in msg
    # The orphan-sweep lock is a file lock, so it is node-local, not cluster-wide.
    assert "orphan-sweep" in msg
    # Webhook UI feedback needs the browser and the request on the same worker.
    assert "Webhook" in msg
    assert "4 workers" in msg


def test_ensure_multi_worker_safe_redis_never_warns_even_with_bypass_set(monkeypatch):
    """A Redis queue is safe; a stale bypass flag must not produce scary output.

    Redis short-circuits before the bypass is consulted, so a correctly
    configured deployment that leaves the flag set in its environment sees
    nothing at all.
    """
    warnings = _capture_startup_warnings(monkeypatch)
    with patch(
        "langflow.__main__.get_settings_service",
        return_value=_settings_service_with_queue("redis", bypass=True),
    ):
        ensure_multi_worker_safe(num_workers=4)

    assert warnings == []


def test_ensure_multi_worker_safe_bypass_off_still_refuses(monkeypatch):
    """The flag is opt-in: the default must keep refusing to boot."""
    warnings = _capture_startup_warnings(monkeypatch)
    with (
        patch(
            "langflow.__main__.get_settings_service",
            return_value=_settings_service_with_queue("asyncio", bypass=False),
        ),
        pytest.raises(RuntimeError),
    ):
        ensure_multi_worker_safe(num_workers=4)

    assert warnings == []


def test_ensure_multi_worker_safe_error_points_at_the_bypass_flag():
    """The refusal must tell headless operators the escape hatch exists."""
    with (
        patch("langflow.__main__.get_settings_service", return_value=_settings_service_with_queue("asyncio")),
        pytest.raises(RuntimeError) as exc_info,
    ):
        ensure_multi_worker_safe(num_workers=3)

    assert MULTI_WORKER_BYPASS_ENV_VAR in str(exc_info.value)


def _stop_midway(tmp_path, command: str, *args: str, signum: int) -> subprocess.CompletedProcess:
    """Run a command until it waits on its database, signal it, and return how it ended.

    The database takes the connection and never answers, so the command is stopped mid-run every time.
    """
    pytest.importorskip("psycopg", reason="needs the postgresql extra")
    from langflow.services.database.sqlite_to_postgres import upgrade_to_head

    listener = socket.create_server(("127.0.0.1", 0))
    silent = f"postgresql://nobody@127.0.0.1:{listener.getsockname()[1]}/none"
    env = {**os.environ, "LANGFLOW_CONFIG_DIR": str(tmp_path)}
    if command == "convert-sqlite-to-postgres":
        source = f"sqlite:///{tmp_path / 'langflow.db'}"
        upgrade_to_head(source)
        args = (*args, "--source", source, "--target", silent)
    else:
        env["LANGFLOW_DATABASE_URL"] = silent
    child = subprocess.Popen(  # noqa: S603 - the interpreter running the tests, fixed arguments
        [sys.executable, "-m", "langflow", command, *args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 60
        while not select.select([listener], [], [], 0.1)[0]:
            if child.poll() is not None:
                out, err = child.communicate()
                pytest.fail(f"the command exited {child.returncode} before reaching its database\n{out}\n{err}")
            assert time.monotonic() < deadline, "the command never reached its database"
        child.send_signal(signum)
        out, err = child.communicate(timeout=120)
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=10)
        listener.close()
    return subprocess.CompletedProcess(child.args, child.returncode, out, err)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT and SIGTERM are POSIX signals")
@pytest.mark.parametrize(
    ("command", "args", "signum"),
    [
        ("relocate-files", ["--bucket", "unused"], signal.SIGTERM),
        ("relocate-kb", ["--to", "postgres"], signal.SIGINT),
        ("convert-sqlite-to-postgres", [], signal.SIGINT),
        ("check-integrity", [], signal.SIGTERM),
        ("migration-preflight", [], signal.SIGINT),
    ],
)
def test_a_migration_command_stopped_by_a_signal_ends_its_stream_with_an_error(tmp_path, command, args, signum):
    # Exit 0 and a stream that just stops read as a finished move to a script or a CI step.
    result = _stop_midway(tmp_path, command, *args, "--json", signum=signum)

    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 128 + signum, result.stderr
    assert events[-1]["event"] == "error"
    assert events[-1]["code"] == "interrupted"
    assert events[-1]["message"].startswith(f"Stopped by {signal.Signals(signum).name} before the end.")
    assert "report" not in [event["event"] for event in events]


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT and SIGTERM are POSIX signals")
def test_without_json_a_stopped_command_says_so_on_stderr(tmp_path):
    result = _stop_midway(tmp_path, "relocate-files", "--bucket", "unused", signum=signal.SIGINT)

    assert result.returncode == 130
    assert "Stopped by SIGINT before the end." in result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT and SIGTERM are POSIX signals")
@pytest.mark.parametrize("outcome", ["completed", "failed", "exited", signal.SIGINT, signal.SIGTERM])
def test_interruption_reporting_restores_previous_handlers(outcome):
    previous = {signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        if outcome == "completed":
            with interruption_reported("The copy did not finish.", as_json=False):
                pass
        elif outcome in ("failed", "exited"):
            failure = ValueError("copy failed") if outcome == "failed" else SystemExit(7)
            with (
                pytest.raises(type(failure)) as exc_info,
                interruption_reported("The copy did not finish.", as_json=False),
            ):
                raise failure
            assert exc_info.value is failure
        else:
            with (
                pytest.raises(CommandInterrupted) as exc_info,
                interruption_reported("The copy did not finish.", as_json=False),
            ):
                signal.raise_signal(outcome)
            assert exc_info.value.code == 128 + outcome
        assert {signum: signal.getsignal(signum) for signum in previous} == previous
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT and SIGTERM are POSIX signals")
@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_an_interruption_inside_a_task_group_keeps_its_exit_code_and_final_event(signum):
    code = """
import asyncio
import json
import signal
import sys

import anyio
from langflow.__main__ import interruption_reported

async def copy():
    try:
        async with anyio.create_task_group():
            async with anyio.create_task_group():
                signal.raise_signal(int(sys.argv[1]))
    finally:
        signal.raise_signal(signal.SIGTERM)
        print(json.dumps({"event": "cleanup"}), flush=True)

with interruption_reported("The copy did not finish.", as_json=True):
    asyncio.run(copy())
"""
    result = subprocess.run(  # noqa: S603 - fixed code in the interpreter running the tests
        [sys.executable, "-c", code, str(int(signum))], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 128 + signum, result.stderr
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [event["event"] for event in events] == ["cleanup", "error"]
    assert events[-1]["code"] == "interrupted"
    assert events[-1]["message"].startswith(f"Stopped by {signal.Signals(signum).name} before the end.")
    assert "Traceback" not in result.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="SIGINT and SIGTERM are POSIX signals")
def test_the_signal_helper_reports_a_child_that_exits_before_connecting(tmp_path):
    with pytest.raises(pytest.fail.Exception, match="before reaching its database") as exc_info:
        _stop_midway(tmp_path, "no-such-command", signum=signal.SIGTERM)

    assert "No such command" in str(exc_info.value)
