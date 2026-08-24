"""Unit tests for the opt-in microVM sandbox backend (issue #12029).

These tests never require exec-sandbox or QEMU: the exec_sandbox module is
stubbed into sys.modules so the routing, fail-closed, and result-mapping logic
is exercised everywhere CI runs.
"""

import importlib
import importlib.util
import os
import sys
import threading
import time
from types import SimpleNamespace

import pytest
from lfx.utils import sandbox as sandbox_module
from lfx.utils.sandbox import (
    SandboxExecutionError,
    SandboxUnavailableError,
    build_import_preamble,
    get_sandbox_backend,
    is_sandbox_enabled,
    run_code_in_sandbox,
    sanitize_code,
)
from lfx.utils.sandbox import base as base_module
from lfx.utils.sandbox import exec_sandbox as exec_module
from lfx.utils.sandbox import registry as registry_module


def _settings(backend, **extra):
    defaults = {
        "sandbox_backend": backend,
        "sandbox_timeout_seconds": 30,
        "sandbox_memory_mb": 192,
        "sandbox_allow_network": False,
        "sandbox_allowed_domains": [],
        "sandbox_allow_software_emulation": False,
    }
    defaults.update(extra)
    return SimpleNamespace(settings=SimpleNamespace(**defaults))


@pytest.fixture(autouse=True)
def fresh_executor(monkeypatch):
    """Give each test its own executor and tear down its loop thread afterwards."""
    import atexit

    executor = exec_module._ExecSandboxExecutor()
    monkeypatch.setitem(registry_module._instances, "exec-sandbox", executor)
    yield executor
    # Tear down so daemon loop threads and atexit hooks don't accumulate
    # across the test session.
    atexit.unregister(executor.shutdown)
    executor.shutdown()
    loop, thread = executor._loop, executor._thread
    if loop is not None and not loop.is_closed():
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)
        loop.close()


class _FakeExecutionResult:
    def __init__(self, stdout="", stderr="", exit_code=0, execution_time_ms=5):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms


class _FakeScheduler:
    """Stands in for exec_sandbox.Scheduler; records the kwargs run() received."""

    instances: list = []

    def __init__(self, config=None):
        self.config = config
        self.run_calls: list[dict] = []
        self.entered = False
        self.exited = False
        type(self).instances.append(self)

    async def __aenter__(self):
        # Yield control so concurrent first calls genuinely interleave here,
        # exercising the scheduler-creation lock.
        import asyncio

        await asyncio.sleep(0.02)
        self.entered = True
        return self

    async def __aexit__(self, *args):
        self.exited = True
        return False

    async def run(self, **kwargs):
        # Yield once so lifecycle transitions (e.g. a concurrent shutdown)
        # can interleave between scheduler acquisition and completion.
        import asyncio

        await asyncio.sleep(0)
        self.run_calls.append(kwargs)
        code = kwargs["code"]
        if "BOOM_INFRA" in code:
            msg = "vm exploded"
            raise RuntimeError(msg)
        if "FAIL_CODE" in code:
            return _FakeExecutionResult(stderr="NameError: nope", exit_code=1)
        if "TIMEOUT" in code:
            return _FakeExecutionResult(exit_code=-1)
        if "OOM_KILL" in code:
            return _FakeExecutionResult(exit_code=137)
        return _FakeExecutionResult(stdout="hello from vm\n")


class _FakeSchedulerConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def fake_exec_sandbox(monkeypatch):
    """See _install_fake_exec_sandbox; kept as a named fixture for value access."""
    return _install_fake_exec_sandbox(monkeypatch)


def _install_fake_exec_sandbox(monkeypatch):
    """Install a stub exec_sandbox module and return the fake Scheduler class.

    Also fakes hardware acceleration as available: CI runners have no
    /dev/kvm, and these tests exercise routing/mapping logic, not the
    TCG-refusal gate (which has its own dedicated tests).
    """
    _FakeScheduler.instances = []

    def _fake_upstream_settings():
        # Mirrors upstream: a pydantic bool field fed by EXEC_SANDBOX_FORCE_EMULATION.
        raw = os.environ.get("EXEC_SANDBOX_FORCE_EMULATION", "").strip().lower()
        return SimpleNamespace(force_emulation=raw in {"1", "true", "yes", "on", "y", "t"})

    async def _detect_accel_type(kvm_available=None, hvf_available=None, *, force_emulation=False):  # noqa: ARG001
        return "tcg" if force_emulation else "kvm"

    accel_type = SimpleNamespace(KVM="kvm", HVF="hvf", TCG="tcg")
    probes = SimpleNamespace(detect_accel_type=_detect_accel_type)
    settings_mod = SimpleNamespace(Settings=_fake_upstream_settings)
    vm_types = SimpleNamespace(AccelType=accel_type)
    module = SimpleNamespace(
        Scheduler=_FakeScheduler,
        SchedulerConfig=_FakeSchedulerConfig,
        system_probes=probes,
        settings=settings_mod,
        vm_types=vm_types,
    )
    monkeypatch.setitem(sys.modules, "exec_sandbox", module)
    monkeypatch.setitem(sys.modules, "exec_sandbox.system_probes", probes)
    monkeypatch.setitem(sys.modules, "exec_sandbox.settings", settings_mod)
    monkeypatch.setitem(sys.modules, "exec_sandbox.vm_types", vm_types)
    monkeypatch.setattr(exec_module, "_hardware_acceleration_available", lambda: True)
    return _FakeScheduler


class TestBackendSelection:
    def test_default_is_none(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))
        assert get_sandbox_backend() == "none"
        assert not is_sandbox_enabled()

    def test_exec_sandbox_enables(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        assert get_sandbox_backend() == "exec-sandbox"
        assert is_sandbox_enabled()

    # An unresolvable settings stack falls back to the environment, so these
    # three assert the "nothing is configured anywhere" case and have to clear
    # the variable. TestSettingsUnavailableFailsClosed covers the case where
    # the operator DID configure a backend and settings failed to build.
    def test_absent_services_layer_means_none(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.delattr("lfx.services.deps.get_settings_service")
        assert get_sandbox_backend() == "none"

    def test_none_settings_service_means_none(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        assert get_sandbox_backend() == "none"

    def test_settings_without_field_means_none(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace()),
        )
        assert get_sandbox_backend() == "none"


class TestImportPreamble:
    def test_string_input(self):
        assert build_import_preamble("math, json") == "import math\nimport json"

    def test_list_input(self):
        assert build_import_preamble(["math", "os.path"]) == "import math\nimport os.path"

    def test_empty(self):
        assert build_import_preamble("") == ""
        assert build_import_preamble([]) == ""

    def test_rejects_injection(self):
        with pytest.raises(ValueError, match="Invalid module name"):
            build_import_preamble("math; import os")
        with pytest.raises(ValueError, match="Invalid module name"):
            build_import_preamble("os\nimport subprocess")

    def test_rejects_non_string_types(self):
        with pytest.raises(TypeError):
            build_import_preamble(42)


class TestSanitizeCode:
    """Parity with PythonREPL.sanitize_input: markdown fences are stripped."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("print('hi')", "print('hi')"),
            ("```python\nprint('hi')\n```", "print('hi')"),
            ("```\nprint('hi')\n```", "print('hi')"),
            ("python\nprint('hi')", "print('hi')"),
            ("  print('hi')  ", "print('hi')"),
        ],
    )
    def test_strips_fences(self, raw, expected):
        assert sanitize_code(raw) == expected


class TestRunCodeInSandbox:
    def test_refuses_when_not_configured(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))
        with pytest.raises(SandboxExecutionError, match="no sandbox backend"):
            run_code_in_sandbox("print('hi')")

    def test_unknown_backend_fails_closed(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("firecracker"))
        with pytest.raises(SandboxUnavailableError, match="Unknown sandbox backend"):
            run_code_in_sandbox("print('hi')")

    def test_missing_package_fails_closed(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setitem(sys.modules, "exec_sandbox", None)  # import raises ImportError
        with pytest.raises(SandboxUnavailableError, match=r"exec-sandbox.*not installed"):
            run_code_in_sandbox("print('hi')")

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_success_maps_result(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("print('hello from vm')")
        assert result.success
        assert result.stdout == "hello from vm\n"
        assert result.exit_code == 0

    def test_global_imports_prepended(self, monkeypatch, fake_exec_sandbox):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        run_code_in_sandbox("print(math.pi)", global_imports="math, json")
        scheduler = fake_exec_sandbox.instances[-1]
        code = scheduler.run_calls[-1]["code"]
        assert code.startswith("import math\nimport json\n")
        assert code.endswith("print(math.pi)")

    def test_settings_forwarded_to_backend(self, monkeypatch, fake_exec_sandbox):
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings(
                "exec-sandbox",
                sandbox_timeout_seconds=77,
                sandbox_memory_mb=256,
                sandbox_allow_network=True,
                sandbox_allowed_domains=["api.example.com"],
            ),
        )
        run_code_in_sandbox("print('hi')")
        scheduler = fake_exec_sandbox.instances[-1]
        call = scheduler.run_calls[-1]
        assert call["timeout_seconds"] == 77
        assert call["memory_mb"] == 256
        assert call["allow_network"] is True
        assert call["allowed_domains"] == ["api.example.com"]
        # exec_sandbox's run() takes env_vars (not env)
        assert call["env_vars"] == {}
        # Warm pool is deliberately not configured (upstream pool contract
        # mismatch: per-language pools at fixed memory).
        assert scheduler.config.kwargs == {}

    def test_network_is_disabled_by_default(self, monkeypatch, fake_exec_sandbox):
        """Default settings must reach the backend as allow_network=False (offline VM)."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        run_code_in_sandbox("print('hi')")
        call = fake_exec_sandbox.instances[-1].run_calls[-1]
        assert call["allow_network"] is False
        # No allowed_domains configured -> None reaches the backend (which
        # then applies its package-registry-only default filter).
        assert call["allowed_domains"] is None

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_user_code_failure_is_result_not_exception(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("FAIL_CODE")
        assert not result.success
        assert result.exit_code == 1
        assert "NameError" in result.error_message()

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_timeout_exit_code_message(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("TIMEOUT")
        assert not result.success
        assert "timed out" in result.error_message()

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_infrastructure_error_wrapped(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        with pytest.raises(SandboxExecutionError, match="vm exploded"):
            run_code_in_sandbox("BOOM_INFRA")

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_oom_exit_code_message(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("OOM_KILL")
        assert not result.success
        assert "memory" in result.error_message()

    def test_blank_code_returns_empty_success(self, monkeypatch, fake_exec_sandbox):
        """Blank code is an empty result, matching the in-process interpreter.

        exec-sandbox rejects empty code outright, which would otherwise
        surface as an infrastructure error, so it must never be invoked.
        """
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("   \n  ")
        assert result.success
        assert result.stdout == ""
        assert not fake_exec_sandbox.instances

    def test_future_imports_stay_first(self, monkeypatch, fake_exec_sandbox):
        """The import preamble must not precede `from __future__ import ...`."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        code = '"""doc."""\nfrom __future__ import annotations\nprint(1)'
        run_code_in_sandbox(code, global_imports="math")
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        lines = sent.splitlines()
        assert lines[0] == '"""doc."""'
        assert lines[1] == "from __future__ import annotations"
        assert "import math" in lines[2]
        compile(sent, "<test>", "exec")  # composed code must be valid Python

    def test_deep_probe_refusal_overrides_shallow_pass(self, monkeypatch, fake_exec_sandbox):
        """Upstream's accelerator decision is authoritative over the shallow preflight.

        detect_accel_type is exec-sandbox's single source of truth; when it
        says TCG, a shallow pass must not permit execution.
        """
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))

        async def _tcg_accel(**_kwargs):
            return "tcg"

        monkeypatch.setattr(sys.modules["exec_sandbox.system_probes"], "detect_accel_type", _tcg_accel)
        with pytest.raises(SandboxUnavailableError, match="TCG"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    def test_fails_closed_when_accel_decision_unobtainable(self, monkeypatch, fake_exec_sandbox):
        """If upstream's decision API is missing, refuse — never guess via the shallow check."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))

        async def _boom(**_kwargs):
            msg = "probe API moved"
            raise RuntimeError(msg)

        monkeypatch.setattr(sys.modules["exec_sandbox.system_probes"], "detect_accel_type", _boom)
        with pytest.raises(SandboxUnavailableError, match="could not determine"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    @pytest.mark.parametrize("spelling", ["true", "on", "t", "Y"])
    def test_forced_emulation_env_refused(self, monkeypatch, fake_exec_sandbox, spelling):
        """Every pydantic-truthy spelling upstream accepts must be refused here too."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setenv("EXEC_SANDBOX_FORCE_EMULATION", spelling)
        with pytest.raises(SandboxUnavailableError, match="TCG"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    def test_shutdown_is_restartable(self, monkeypatch, fake_exec_sandbox):
        """Run -> shutdown_sandbox() -> run must create a fresh scheduler."""
        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        assert run_code_in_sandbox("print('hi')").success
        shutdown_sandbox()
        assert run_code_in_sandbox("print('hi')").success
        assert len(fake_exec_sandbox.instances) == 2

    def test_same_line_future_import_composes_correctly(self, monkeypatch, fake_exec_sandbox):
        """Semicolon-joined statements after a future import must run AFTER the preamble."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        code = "from __future__ import annotations; print(math.pi)"
        run_code_in_sandbox(code, global_imports="math")
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        compile(sent, "<test>", "exec")
        assert sent.index("import math") < sent.index("print(math.pi)")
        assert sent.index("from __future__") < sent.index("import math")

    def test_same_line_docstring_composes_correctly(self, monkeypatch, fake_exec_sandbox):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        code = '"""doc."""; print(math.pi)'
        run_code_in_sandbox(code, global_imports="math")
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        compile(sent, "<test>", "exec")
        assert sent.index("import math") < sent.index("print(math.pi)")

    def test_refuses_tcg_without_override(self, monkeypatch, fake_exec_sandbox):
        """No hardware hypervisor -> fail closed rather than silently run under TCG."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setattr(exec_module, "_hardware_acceleration_available", lambda: False)
        with pytest.raises(SandboxUnavailableError, match="hardware"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_software_emulation_override_allows_tcg(self, monkeypatch):
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("exec-sandbox", sandbox_allow_software_emulation=True),
        )
        monkeypatch.setattr(exec_module, "_hardware_acceleration_available", lambda: False)
        result = run_code_in_sandbox("print('hello from vm')")
        assert result.success

    def test_unicode_docstring_same_line_composes_correctly(self, monkeypatch, fake_exec_sandbox):
        """Ast col_offset is a UTF-8 byte offset; non-ASCII text must not shift the split."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        code = '"""caf\u00e9."""; print(math.pi)'
        run_code_in_sandbox(code, global_imports="math")
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        compile(sent, "<test>", "exec")
        assert "print(math.pi)" in sent
        assert sent.index("import math") < sent.index("print(math.pi)")

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_startup_grace_until_first_run_completes(self, monkeypatch, fresh_executor):
        """Readiness flips only after a run completes, not when the scheduler appears."""
        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        assert not fresh_executor._startup_complete
        run_code_in_sandbox("print('hi')")
        assert fresh_executor._startup_complete
        shutdown_sandbox()
        # A restarted sandbox needs the startup margin again.
        assert not fresh_executor._startup_complete

    def test_unknown_accelerator_refused(self, monkeypatch, fake_exec_sandbox):
        """Allowlist semantics: anything that is not exactly KVM/HVF fails closed."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))

        async def _novel_accel(**_kwargs):
            return "warp-drive"

        monkeypatch.setattr(sys.modules["exec_sandbox.system_probes"], "detect_accel_type", _novel_accel)
        with pytest.raises(SandboxUnavailableError, match="warp-drive"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    @pytest.mark.parametrize("separator", ["\u2028", "\u2029"])
    def test_unicode_line_separator_in_docstring_composes_correctly(self, monkeypatch, fake_exec_sandbox, separator):
        """U+2028/U+2029 are ordinary characters to the tokenizer, not line breaks.

        str.splitlines() would treat them as boundaries and shift every
        subsequent offset, dropping the preamble inside the docstring.
        """
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        code = f'"""a{separator}b"""; print(math.pi)'
        run_code_in_sandbox(code, global_imports="math")
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        compile(sent, "<test>", "exec")
        assert "print(math.pi)" in sent
        assert sent.index("import math") < sent.index("print(math.pi)")

    def test_shutdown_closes_run_submitted_before_loop_executed_it(
        self, monkeypatch, fresh_executor, fake_exec_sandbox
    ):
        """A run accepted before shutdown is closed even before its coroutine runs.

        The pre-creation-lock window: the loop is frozen so the submitted run
        coroutine cannot execute; the shutdown submitted afterwards must queue
        behind it and close the scheduler that run creates.
        """
        import threading
        import time

        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))

        # Create the loop, then freeze it so nothing submitted can execute.
        with fresh_executor._lock:
            loop = fresh_executor._ensure_loop_locked()
        release = threading.Event()
        frozen = threading.Event()

        def freeze():
            frozen.set()
            release.wait(timeout=5)

        loop.call_soon_threadsafe(freeze)
        assert frozen.wait(timeout=5)

        results = []
        worker = threading.Thread(target=lambda: results.append(run_code_in_sandbox("print('hi')")), daemon=True)
        worker.start()
        # Wait for the worker to have SUBMITTED (it then blocks in
        # future.result); the loop is still frozen, so no scheduler exists yet.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with fresh_executor._lock:
                submitted = fresh_executor._loop is loop and fresh_executor._scheduler_lock is not None
            if submitted and worker.is_alive():
                break
            time.sleep(0.001)
        assert not fake_exec_sandbox.instances

        shutdown_pathway = threading.Thread(target=shutdown_sandbox, daemon=True)
        shutdown_pathway.start()
        time.sleep(0.01)  # let shutdown submit its close behind the run
        release.set()
        worker.join(timeout=5)
        shutdown_pathway.join(timeout=5)
        assert not worker.is_alive()
        assert not shutdown_pathway.is_alive()
        # The run executed first (FIFO), created a scheduler, and the queued
        # close then closed it — nothing left open.
        assert fake_exec_sandbox.instances
        assert fake_exec_sandbox.instances[0].exited
        assert fresh_executor._scheduler is None
        assert not fresh_executor._startup_complete

    def test_run_after_shutdown_gets_startup_grace(self, monkeypatch, fake_exec_sandbox):
        """A cold start following a shutdown must run under the startup margin.

        Reproduces the compressed-margin scenario: with the steady-state
        grace squeezed to zero, a post-shutdown run only succeeds because it
        is classified as a first execution (startup grace), proving the
        readiness capture and shutdown are ordered.
        """
        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("exec-sandbox", sandbox_timeout_seconds=0),
        )
        monkeypatch.setattr(exec_module, "_RUN_GRACE_SECONDS", 0)
        monkeypatch.setattr(exec_module, "_STARTUP_GRACE_SECONDS", 5)
        # Cold start (creation sleeps 20ms): succeeds only under startup grace.
        assert run_code_in_sandbox("print('hi')").success
        shutdown_sandbox()
        # Post-shutdown run is another cold start and must again be
        # classified as first execution; with stale steady-state grace the
        # 0-second deadline would fail before creation completes.
        assert run_code_in_sandbox("print('hi')").success
        assert len(fake_exec_sandbox.instances) == 2

    def test_run_during_pending_shutdown_gets_startup_grace(self, monkeypatch, fresh_executor, fake_exec_sandbox):
        """A run accepted while a shutdown's close is queued must cold-start.

        The lifecycle transition (readiness clear + generation bump) happens
        synchronously in _shutdown() under the mutex, so even before the
        queued close coroutine executes, a newly accepted run classifies
        itself as a first execution and gets the startup grace — with stale
        warm state and the steady margin squeezed to zero it would time out
        before its fresh scheduler finishes creating.
        """
        import threading
        import time

        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("exec-sandbox", sandbox_timeout_seconds=0),
        )
        monkeypatch.setattr(exec_module, "_RUN_GRACE_SECONDS", 0)
        monkeypatch.setattr(exec_module, "_STARTUP_GRACE_SECONDS", 5)

        # Warm up (cold, startup grace), leaving readiness True.
        assert run_code_in_sandbox("print('hi')").success
        assert fresh_executor._startup_complete

        # Freeze the loop so the shutdown's queued close cannot execute.
        loop = fresh_executor._loop
        release = threading.Event()
        frozen = threading.Event()

        def freeze():
            frozen.set()
            release.wait(timeout=5)

        loop.call_soon_threadsafe(freeze)
        assert frozen.wait(timeout=5)

        # Shutdown submits its close (queued behind the freeze) and blocks
        # waiting for it; the lifecycle transition must already be visible.
        shutdown_thread = threading.Thread(target=shutdown_sandbox, daemon=True)
        shutdown_thread.start()
        deadline = time.monotonic() + 5
        while fresh_executor._startup_complete and time.monotonic() < deadline:
            time.sleep(0.001)
        assert not fresh_executor._startup_complete, "shutdown did not clear readiness synchronously"

        # Accept a run while the close is still pending: it must classify as
        # a first execution (startup grace) or the 0-second steady deadline
        # fails before its fresh scheduler finishes creating.
        results = []

        def call():
            results.append(run_code_in_sandbox("print('hi')"))

        run_thread = threading.Thread(target=call, daemon=True)
        run_thread.start()
        time.sleep(0.02)  # let it submit behind the queued close
        release.set()
        run_thread.join(timeout=5)
        shutdown_thread.join(timeout=5)
        assert not run_thread.is_alive()
        assert results
        assert results[0].success
        # Old scheduler closed by the pending shutdown; fresh one created.
        assert len(fake_exec_sandbox.instances) == 2
        assert fake_exec_sandbox.instances[0].exited
        # The post-shutdown run completed on the current epoch: readiness set.
        assert fresh_executor._startup_complete

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_fork_hook_replaces_held_mutex(self, monkeypatch, fresh_executor):
        """The after-fork hook must rebuild a mutex a dead parent thread held.

        Simulates the child side of a fork taken while another thread owned
        the executor mutex: the inherited lock is locked with no surviving
        owner, and without the hook the next run() would block forever before
        reaching the dead-loop recovery.
        """
        import threading

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        # Establish live state, then simulate the fork child: the mutex is
        # held by a thread that no longer exists.
        assert run_code_in_sandbox("print('hi')").success
        inherited_lock = fresh_executor._lock
        assert inherited_lock.acquire(blocking=False)  # now "held by a dead thread"
        old_generation = fresh_executor._generation

        sandbox_module._reinit_backends_after_fork()

        assert fresh_executor._lock is not inherited_lock
        assert fresh_executor._lock.acquire(blocking=False)
        fresh_executor._lock.release()
        assert fresh_executor._loop is None
        assert fresh_executor._thread is None
        assert fresh_executor._scheduler is None
        assert fresh_executor._scheduler_lock is None
        assert not fresh_executor._startup_complete
        assert fresh_executor._generation == old_generation + 1

        # A run in the "child" must complete instead of deadlocking on the
        # inherited mutex; bound it with a joined thread so a regression
        # fails the test rather than hanging the suite.
        results = []
        worker = threading.Thread(target=lambda: results.append(run_code_in_sandbox("print('hi')")), daemon=True)
        worker.start()
        worker.join(timeout=5)
        assert not worker.is_alive(), "run() deadlocked on the fork-inherited mutex"
        assert results
        assert results[0].success

    def test_shutdown_is_a_barrier_for_inflight_creation(self, monkeypatch, fresh_executor, fake_exec_sandbox):
        """A shutdown overlapping Scheduler.__aenter__ must wait and then close it.

        Also covers the generation guard: the overlapped run completes against
        the closed scheduler and must not mark the next generation's startup
        as complete.
        """
        import threading
        import time

        from lfx.utils.sandbox import shutdown_sandbox

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        results = []

        def call():
            results.append(run_code_in_sandbox("print('hi')"))

        worker = threading.Thread(target=call, daemon=True)
        worker.start()
        # Wait until Scheduler construction started (its __aenter__ is still
        # sleeping), then shut down mid-creation.
        deadline = time.monotonic() + 5
        while not fake_exec_sandbox.instances and time.monotonic() < deadline:
            time.sleep(0.001)
        assert fake_exec_sandbox.instances, "scheduler creation never started"
        shutdown_sandbox()
        worker.join(timeout=5)
        assert not worker.is_alive()
        # The barrier waited for creation and closed the new scheduler.
        assert fake_exec_sandbox.instances[0].exited
        # The overlapped run belongs to the closed generation: readiness for
        # the next scheduler must still be False.
        assert not fresh_executor._startup_complete

    def test_concurrent_first_calls_create_one_scheduler(self, monkeypatch, fake_exec_sandbox):
        """Two racing first executions must share one scheduler (no leaked VM pool).

        A barrier releases both threads together and the fake __aenter__ yields
        control (asyncio.sleep) so the two coroutines genuinely interleave at
        the creation await; without the creation lock this test fails.
        """
        import threading

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        errors = []
        start_barrier = threading.Barrier(2)

        def call():
            try:
                start_barrier.wait(timeout=5)
                run_code_in_sandbox("print('hi')")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call, daemon=True) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert all(not t.is_alive() for t in threads), "sandbox execution deadlocked"
        assert not errors
        assert len(fake_exec_sandbox.instances) == 1

    def test_scheduler_reused_across_calls(self, monkeypatch, fake_exec_sandbox):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        run_code_in_sandbox("print('one')")
        run_code_in_sandbox("print('two')")
        assert len(fake_exec_sandbox.instances) == 1
        assert fake_exec_sandbox.instances[0].entered
        assert len(fake_exec_sandbox.instances[0].run_calls) == 2


class TestComponentRouting:
    """The code-execution components route through the sandbox when enabled."""

    def test_python_interpreter_sandbox_strips_fences(self, monkeypatch, fake_exec_sandbox):
        """Fenced LLM tool-mode code is normalized before reaching the guest."""
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLComponent(global_imports="math", python_code="```python\nprint('hello from vm')\n```")
        data = component.run_python_repl()
        assert data.data == {"result": "hello from vm"}
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        assert "`" not in sent

    def test_python_interpreter_sandbox_path(self, monkeypatch, fake_exec_sandbox):
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLComponent(global_imports="math", python_code="print('hello from vm')")
        data = component.run_python_repl()
        assert data.data == {"result": "hello from vm"}
        # Sandbox mode must not exec in-process: the fake scheduler saw the code.
        assert fake_exec_sandbox.instances[-1].run_calls

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_python_interpreter_sandbox_error(self, monkeypatch):
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLComponent(global_imports="math", python_code="FAIL_CODE")
        data = component.run_python_repl()
        assert "NameError" in data.data["error"]

    def test_python_interpreter_fails_closed_without_package(self, monkeypatch):
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setitem(sys.modules, "exec_sandbox", None)
        component = PythonREPLComponent(global_imports="math", python_code="print('hi')")
        # Fail closed: the configured-but-unavailable sandbox surfaces as an
        # exception, never a silent in-process execution of the code.
        with pytest.raises(SandboxUnavailableError):
            component.run_python_repl()

    def test_python_interpreter_default_stays_in_process(self, monkeypatch, fake_exec_sandbox):
        """Backend "none" runs in-process and never touches the sandbox backend.

        langchain_experimental is stubbed so this regression test runs in the
        isolated lfx CI environment too (it is not installed there); the real
        library is exercised by the langflow-base component tests.
        """
        import io
        from contextlib import redirect_stdout

        from lfx.components.utilities import python_repl_core
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        class _FakePythonREPL:
            def __init__(self, _globals=None):
                self._globals = _globals or {}

            @staticmethod
            def sanitize_input(code):
                return code.strip()

            def run(self, code):
                out = io.StringIO()
                with redirect_stdout(out):
                    exec(code, self._globals)  # noqa: S102
                return out.getvalue()

        fake_utilities = SimpleNamespace(PythonREPL=_FakePythonREPL)
        monkeypatch.setitem(sys.modules, "langchain_experimental", SimpleNamespace(utilities=fake_utilities))
        monkeypatch.setitem(sys.modules, "langchain_experimental.utilities", fake_utilities)
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))

        # Belt and suspenders: the in-process path must not call the sandbox
        # entry point at all, regardless of what the fake backend would do.
        def _explode(*_args, **_kwargs):
            msg = "run_code_in_sandbox must not be called when backend is none"
            raise AssertionError(msg)

        monkeypatch.setattr(python_repl_core, "run_code_in_sandbox", _explode)

        component = PythonREPLComponent(global_imports="math", python_code="print(math.sqrt(4))")
        data = component.run_python_repl()
        assert data.data == {"result": "2.0"}
        # In-process path must never touch the sandbox backend.
        assert not fake_exec_sandbox.instances

    def test_repl_tool_user_error_returned_as_observation(self, monkeypatch, fake_exec_sandbox):
        """User-code errors come back as the tool observation, not ToolException.

        Parity with PythonREPL.run(), which returns error text so agents can
        read the traceback and self-correct. Exercises build_tool(), the path
        agents actually use (run_model has a pre-existing self.code collision).
        """
        from lfx.components.tools.python_repl import PythonREPLToolComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLToolComponent(name="python_repl", description="repl", global_imports="math")
        tool = component.build_tool()
        observation = tool.run("FAIL_CODE")
        assert "NameError" in observation
        assert fake_exec_sandbox.instances[-1].run_calls

    def test_repl_tool_sandbox_path(self, monkeypatch, fake_exec_sandbox):
        from lfx.components.tools.python_repl import PythonREPLToolComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLToolComponent(name="python_repl", description="repl", global_imports="math")
        tool = component.build_tool()
        observation = tool.run("print('hello from vm')")
        assert observation == "hello from vm\n"
        sent = fake_exec_sandbox.instances[-1].run_calls[-1]["code"]
        assert sent.endswith("print('hello from vm')")

    def test_repl_tool_default_stays_in_process(self, monkeypatch, fake_exec_sandbox):
        """Backend "none": the tool executes in-process and never touches the sandbox.

        langchain_experimental is stubbed (see the interpreter counterpart) so
        this runs in the isolated lfx CI environment.
        """
        import io
        from contextlib import redirect_stdout

        from lfx.components.tools import python_repl as python_repl_module
        from lfx.components.tools.python_repl import PythonREPLToolComponent

        class _FakePythonREPL:
            def __init__(self, _globals=None):
                self._globals = _globals or {}

            @staticmethod
            def sanitize_input(code):
                return code.strip()

            def run(self, code):
                out = io.StringIO()
                with redirect_stdout(out):
                    exec(code, self._globals)  # noqa: S102
                return out.getvalue()

        fake_utilities = SimpleNamespace(PythonREPL=_FakePythonREPL)
        monkeypatch.setitem(sys.modules, "langchain_experimental", SimpleNamespace(utilities=fake_utilities))
        monkeypatch.setitem(sys.modules, "langchain_experimental.utilities", fake_utilities)
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))

        def _explode(*_args, **_kwargs):
            msg = "run_code_in_sandbox must not be called when backend is none"
            raise AssertionError(msg)

        monkeypatch.setattr(python_repl_module, "run_code_in_sandbox", _explode)

        component = PythonREPLToolComponent(name="python_repl", description="repl", global_imports="math")
        tool = component.build_tool()
        observation = tool.run("print(math.sqrt(4))")
        assert observation == "2.0\n"
        assert not fake_exec_sandbox.instances

    def test_repl_tool_fails_closed_without_package(self, monkeypatch):
        """Configured-but-unavailable backend surfaces as ToolException, never local exec."""
        from langchain_core.tools import ToolException
        from lfx.components.tools.python_repl import PythonREPLToolComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setitem(sys.modules, "exec_sandbox", None)
        component = PythonREPLToolComponent(name="python_repl", description="repl", global_imports="math")
        tool = component.build_tool()
        with pytest.raises(ToolException, match=r"exec-sandbox.*not installed"):
            tool.run("print('hi')")


class TestSettingsValidation:
    def test_unknown_backend_rejected_at_settings_level(self):
        from lfx.services.settings.groups.security import SecuritySettings

        with pytest.raises(ValueError, match="sandbox_backend must be one of"):
            SecuritySettings(sandbox_backend="not-a-backend")

    def test_resource_bounds_enforced(self):
        """Documented ranges are enforced at startup, not deep inside exec-sandbox."""
        from lfx.services.settings.groups.security import SecuritySettings
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SecuritySettings(sandbox_timeout_seconds=0)
        with pytest.raises(ValidationError):
            SecuritySettings(sandbox_timeout_seconds=301)
        with pytest.raises(ValidationError):
            SecuritySettings(sandbox_memory_mb=64)

    def test_the_new_sandbox_knobs_are_bounded_too(self):
        """Both are guards, and an unbounded guard is not a guard.

        sandbox_max_artifact_bytes caps what a runaway or hostile program can
        pull into the Langflow process, base64-inflated and held in host
        memory. A zero or negative value disables it or inverts the
        comparison. sandbox_session_idle_seconds has no meaning at or below
        zero for an idle reaper.
        """
        from lfx.services.settings.groups.security import SecuritySettings
        from pydantic import ValidationError

        for value in (0, -1):
            with pytest.raises(ValidationError):
                SecuritySettings(sandbox_session_idle_seconds=value)
            with pytest.raises(ValidationError):
                SecuritySettings(sandbox_max_artifact_bytes=value)

        assert SecuritySettings(sandbox_session_idle_seconds=600).sandbox_session_idle_seconds == 600
        assert SecuritySettings(sandbox_max_artifact_bytes=1024).sandbox_max_artifact_bytes == 1024

    def test_allowed_domains_normalized(self):
        from lfx.services.settings.groups.security import SecuritySettings

        settings = SecuritySettings(sandbox_allowed_domains=["api.example.com", " files.pythonhosted.org ", ""])
        assert settings.sandbox_allowed_domains == ["api.example.com", "files.pythonhosted.org"]

    def test_allowed_domains_env_comma_space(self, monkeypatch):
        """The natural comma-and-space env spelling must reach the backend clean."""
        from lfx.services.settings.base import Settings

        monkeypatch.setenv("LANGFLOW_SANDBOX_ALLOWED_DOMAINS", "api.example.com, files.pythonhosted.org")
        settings = Settings()
        assert settings.sandbox_allowed_domains == ["api.example.com", "files.pythonhosted.org"]

    def test_backend_normalized(self):
        from lfx.services.settings.groups.security import SecuritySettings

        assert SecuritySettings(sandbox_backend="Exec-Sandbox").sandbox_backend == "exec-sandbox"
        assert SecuritySettings().sandbox_backend == "none"


_HAS_REAL_EXEC_SANDBOX = importlib.util.find_spec("exec_sandbox") is not None


_LIVE_TESTS_ENABLED = os.getenv("LANGFLOW_SANDBOX_LIVE_TESTS", "").strip().lower() in {"1", "true", "yes"}


@pytest.mark.qemu
@pytest.mark.skipif(not _HAS_REAL_EXEC_SANDBOX, reason="requires the exec-sandbox extra (Python >= 3.12)")
@pytest.mark.skipif(
    not _LIVE_TESTS_ENABLED,
    reason="live microVM test; set LANGFLOW_SANDBOX_LIVE_TESTS=1 on a host with QEMU 8+ to run",
)
class TestLiveExecSandbox:
    """Opt-in end-to-end test against the real exec-sandbox backend.

    Exercises the genuine Scheduler/SchedulerConfig API and a real guest
    execution so upstream API changes or scheduler lifecycle regressions are
    not hidden by the stubs above. Requires the sandbox extra, QEMU 8+, and
    network access for the one-time VM image download.
    """

    def test_real_guest_execution(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("print('sandbox ok')", global_imports="math")
        assert result.success
        assert result.stdout.strip() == "sandbox ok"

    def test_real_guest_user_error(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("this_name_does_not_exist")
        assert not result.success
        assert "NameError" in result.stderr


# ---------------------------------------------------------------------------
# Registry and the policy gate
# ---------------------------------------------------------------------------


class _StubBackend:
    """A minimal backend, used to prove the dispatcher decides and not the backend."""

    name = "stub"

    def __init__(self, capabilities=None):
        self._capabilities = capabilities or base_module.Capabilities(
            isolation="hardware-virtualized", supports_deny_all_egress=True, supports_domain_allowlist=True
        )
        self.runs: list[tuple[str, object]] = []

    def capabilities(self):
        return self._capabilities

    def run(self, code, *, env=None, session=None):  # noqa: ARG002
        self.runs.append((code, session))
        return base_module.SandboxResult(stdout="stub", stderr="", exit_code=0)

    def shutdown(self):
        pass

    def reset_after_fork(self):
        pass


@pytest.fixture
def stub_backend(monkeypatch):
    """Register a stub under its own name and return an installer for it."""

    def _install(capabilities=None):
        backend = _StubBackend(capabilities)
        monkeypatch.setitem(registry_module._factories, "stub", lambda: backend)
        monkeypatch.setitem(registry_module._instances, "stub", backend)
        return backend

    return _install


class TestRegistry:
    def test_in_tree_backends_are_registered(self):
        names = registry_module.known_sandbox_backends()
        assert "none" in names
        assert "exec-sandbox" in names
        assert "createos" in names

    def test_none_cannot_be_claimed_by_a_backend(self):
        with pytest.raises(ValueError, match="reserved"):
            registry_module.register_sandbox_backend("none", _StubBackend)

    def test_a_registered_backend_is_dispatched_to(self, monkeypatch, stub_backend):
        backend = stub_backend()
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        result = run_code_in_sandbox("print(1)")

        assert result.stdout == "stub"
        assert len(backend.runs) == 1

    def test_an_unregistered_backend_fails_closed(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("no-such-backend"))
        with pytest.raises(SandboxUnavailableError, match="Unknown sandbox backend"):
            run_code_in_sandbox("print(1)")

    def test_the_factory_is_called_once(self, monkeypatch):
        built = []

        def factory():
            built.append(1)
            return _StubBackend()

        monkeypatch.setitem(registry_module._factories, "counted", factory)
        monkeypatch.delitem(registry_module._instances, "counted", raising=False)

        first = registry_module.resolve_sandbox_backend("counted")
        second = registry_module.resolve_sandbox_backend("counted")

        assert first is second
        assert len(built) == 1

    def test_the_settings_validator_reads_the_same_list(self, monkeypatch, stub_backend):
        """D6: one source of truth, so a backend cannot be accepted by only one of them."""
        from lfx.services.settings.groups.security import SecuritySettings

        stub_backend()
        monkeypatch.setattr(registry_module, "_entry_points_loaded", True)
        assert SecuritySettings(sandbox_backend="stub").sandbox_backend == "stub"


class TestPolicyGate:
    """The backend declares; the dispatcher decides. Every branch fails closed."""

    def test_software_isolation_is_refused(self, monkeypatch, stub_backend):
        stub_backend(base_module.Capabilities(isolation="process", supports_deny_all_egress=True))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        with pytest.raises(SandboxUnavailableError, match="not a hardware-virtualized boundary"):
            run_code_in_sandbox("print(1)")

    def test_a_backend_that_cannot_deny_egress_is_refused(self, monkeypatch, stub_backend):
        stub_backend(base_module.Capabilities(isolation="hardware-virtualized", supports_deny_all_egress=False))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        with pytest.raises(SandboxUnavailableError, match="cannot block all egress"):
            run_code_in_sandbox("print(1)")

    def test_a_backend_without_domain_filtering_is_refused(self, monkeypatch, stub_backend):
        stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized", supports_deny_all_egress=True, supports_domain_allowlist=False
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("stub", sandbox_allow_network=True, sandbox_allowed_domains=["pypi.org"]),
        )

        with pytest.raises(SandboxUnavailableError, match="cannot restrict egress by domain"):
            run_code_in_sandbox("print(1)")

    def test_a_backend_without_artifacts_is_refused_when_they_are_requested(self, monkeypatch, stub_backend):
        stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_artifacts=False,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("stub", sandbox_collect_artifacts=True),
        )

        with pytest.raises(SandboxUnavailableError, match="cannot read files back out"):
            run_code_in_sandbox("print(1)")

    def test_a_timeout_above_the_backend_cap_is_refused(self, monkeypatch, stub_backend):
        stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                max_timeout_seconds=10,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("stub", sandbox_timeout_seconds=60),
        )

        with pytest.raises(SandboxUnavailableError, match="caps one execution at 10s"):
            run_code_in_sandbox("print(1)")


class TestSessionGate:
    """Reuse needs consent from the operator AND a claim from the backend."""

    def test_a_session_is_dropped_when_the_operator_left_sessions_off(self, monkeypatch, stub_backend):
        backend = stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_sessions=True,
            )
        )
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        run_code_in_sandbox("print(1)", session=base_module.SessionKey(flow_id="f", user_id="u"))

        assert backend.runs[0][1] is None

    def test_a_session_is_dropped_when_the_backend_cannot_hold_one(self, monkeypatch, stub_backend):
        backend = stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_sessions=False,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service", lambda: _settings("stub", sandbox_session_mode="flow")
        )

        run_code_in_sandbox("print(1)", session=base_module.SessionKey(flow_id="f", user_id="u"))

        assert backend.runs[0][1] is None

    def test_a_session_survives_when_both_gates_are_open(self, monkeypatch, stub_backend):
        backend = stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_sessions=True,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service", lambda: _settings("stub", sandbox_session_mode="flow")
        )
        session = base_module.SessionKey(flow_id="f", user_id="u")

        run_code_in_sandbox("print(1)", session=session)

        assert backend.runs[0][1] == session


class TestSessionKey:
    def test_the_token_hides_the_identity_it_was_built_from(self):
        key = base_module.SessionKey(flow_id="flow-123", user_id="user-456")
        token = key.token()
        assert "flow-123" not in token
        assert "user-456" not in token

    def test_the_token_is_stable(self):
        first = base_module.SessionKey(flow_id="f", user_id="u").token()
        second = base_module.SessionKey(flow_id="f", user_id="u").token()
        assert first == second

    def test_different_users_of_one_flow_never_share_a_guest(self):
        one = base_module.SessionKey(flow_id="f", user_id="alice").token()
        two = base_module.SessionKey(flow_id="f", user_id="bob").token()
        assert one != two

    def test_different_flows_never_share_a_guest(self):
        one = base_module.SessionKey(flow_id="flow-a", user_id="u").token()
        two = base_module.SessionKey(flow_id="flow-b", user_id="u").token()
        assert one != two

    def test_the_separator_cannot_be_forged(self):
        """A concatenated key would collide here; the hash input is delimited."""
        one = base_module.SessionKey(flow_id="a", user_id="bc").token()
        two = base_module.SessionKey(flow_id="ab", user_id="c").token()
        assert one != two


class TestSessionStateCarryOver:
    """Reusing a guest keeps its filesystem, not its Python process."""

    def test_the_preamble_loads_and_saves(self):
        composed = base_module.compose_session_code("print(1)")
        assert "_lf_state" in composed
        assert "atexit" in composed
        assert composed.endswith("print(1)")

    def test_future_imports_still_come_first(self):
        composed = base_module.compose_session_code("from __future__ import annotations\nprint(1)")
        assert composed.startswith("from __future__ import annotations")

    def test_a_module_docstring_still_comes_first(self):
        composed = base_module.compose_session_code('"""Doc."""\nprint(1)')
        assert composed.startswith('"""Doc."""')

    def test_its_own_names_are_never_carried(self):
        """The machinery must not leak into the next execution's namespace."""
        composed = base_module.compose_session_code("print(1)")
        assert '_lf_name.startswith("_lf_")' in composed

    def test_a_session_run_gets_the_preamble(self, monkeypatch, stub_backend):
        backend = stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_sessions=True,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service", lambda: _settings("stub", sandbox_session_mode="flow")
        )

        run_code_in_sandbox("print(1)", session=base_module.SessionKey(flow_id="f", user_id="u"))

        assert "_lf_save_state" in backend.runs[0][0]

    def test_a_cold_run_does_not(self, monkeypatch, stub_backend):
        backend = stub_backend()
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        run_code_in_sandbox("print(1)")

        assert "_lf_save_state" not in backend.runs[0][0]


class TestSessionStateSurvivesOneBadValue:
    """The preamble runs for real here: composed code, a real interpreter, twice.

    Mocking cannot reach this. The defect it guards against only appears when a
    SECOND fresh interpreter tries to load what the first one wrote.
    """

    @staticmethod
    def _run(code, state_file):
        import subprocess
        import sys

        composed = base_module.compose_session_code(code, state_path=str(state_file))
        return subprocess.run(  # noqa: S603
            [sys.executable, "-c", composed],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    def test_a_corrupt_state_file_says_so_on_stderr(self, tmp_path):
        """Losing every variable in silence is the case an operator most needs to see.

        The module comment promises that a name which cannot be carried is
        reported rather than dropped quietly. A truncated or corrupt state
        file took that whole promise down with it.
        """
        state = tmp_path / "session.pkl"
        state.write_bytes(b"this is not a pickle")

        run = self._run("print('ran anyway')\n", state)

        assert run.returncode == 0, run.stderr
        assert "ran anyway" in run.stdout
        assert "could not read the saved session state" in run.stderr

    def test_a_state_file_that_is_not_a_mapping_says_so_too(self, tmp_path):
        import pickle

        state = tmp_path / "session.pkl"
        state.write_bytes(pickle.dumps([1, 2, 3]))

        run = self._run("print('ran anyway')\n", state)

        assert run.returncode == 0, run.stderr
        assert "was not a mapping" in run.stderr

    def test_a_user_defined_function_does_not_erase_the_other_variables(self, tmp_path):
        """Pickling the namespace as one object loses everything to one bad entry."""
        state = tmp_path / "session.pkl"
        first = self._run("keep = 5\nalso = 'hello'\ndef helper():\n    return 1\n", state)
        assert first.returncode == 0, first.stderr

        second = self._run("print(keep)\nprint(also)\n", state)

        assert second.returncode == 0, second.stderr
        assert second.stdout.split() == ["5", "hello"]

    def test_the_uncarryable_name_is_reported_not_swallowed(self, tmp_path):
        state = tmp_path / "session.pkl"
        result = self._run("keep = 5\ndef helper():\n    return 1\n", state)

        assert "did not carry" in result.stderr
        assert "helper" in result.stderr

    def test_an_unpicklable_value_costs_only_itself(self, tmp_path):
        state = tmp_path / "session.pkl"
        first = self._run("keep = 7\nhandle = open(__file__ if False else '/dev/null')\n", state)
        assert first.returncode == 0, first.stderr

        second = self._run("print(keep)\nprint('handle' in dir())\n", state)

        assert second.returncode == 0, second.stderr
        assert second.stdout.split() == ["7", "False"]

    def test_ordinary_values_round_trip(self, tmp_path):
        state = tmp_path / "session.pkl"
        self._run("import json\nnumbers = [1, 2, 3]\nmapping = {'a': 1}\ntext = 'x'\n", state)

        result = self._run("print(numbers, mapping, text)\n", state)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[1, 2, 3] {'a': 1} x"

    def test_a_corrupt_state_file_does_not_break_the_run(self, tmp_path):
        state = tmp_path / "session.pkl"
        state.write_bytes(b"not a pickle at all")

        result = self._run("print('ran anyway')\n", state)

        assert result.returncode == 0, result.stderr
        assert "ran anyway" in result.stdout

    def test_an_oversized_value_is_dropped_and_reported(self, tmp_path):
        state = tmp_path / "session.pkl"
        first = self._run(f"small = 1\nbig = 'x' * {base_module._SESSION_MAX_VALUE_BYTES + 1024}\n", state)
        assert "did not carry" in first.stderr
        assert "big" in first.stderr

        second = self._run("print(small)\nprint('big' in dir())\n", state)

        assert second.stdout.split() == ["1", "False"]


class TestSessionStateWriteIsAtomic:
    """A session guest can be shared by workers, so a reader must never see a torn file."""

    @staticmethod
    def _run(code, state_file):
        import subprocess
        import sys

        composed = base_module.compose_session_code(code, state_path=str(state_file))
        return subprocess.Popen(  # noqa: S603
            [sys.executable, "-c", composed],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_concurrent_writers_never_leave_an_unreadable_state(self, tmp_path):
        import pickle

        state = tmp_path / "session.pkl"
        # Each writer stores a payload big enough that a non-atomic write would
        # span more than one block, which is what makes a torn read possible.
        writers = [self._run(f"value_{index} = 'x' * 200000\n", state) for index in range(12)]
        for writer in writers:
            writer.communicate(timeout=120)

        assert state.exists()
        # The file is written by the preamble under test, not by anything
        # untrusted; reading it back is the whole assertion.
        entries = pickle.loads(state.read_bytes())  # noqa: S301
        assert isinstance(entries, dict)
        for blob in entries.values():
            pickle.loads(blob)  # noqa: S301

    def test_no_temporary_file_is_left_behind(self, tmp_path):
        state = tmp_path / "session.pkl"
        self._run("kept = 1\n", state).communicate(timeout=60)

        leftovers = [path.name for path in tmp_path.iterdir() if path.name != state.name]
        assert leftovers == []

    def test_a_later_run_reads_a_whole_state(self, tmp_path):
        state = tmp_path / "session.pkl"
        self._run("payload = 'y' * 300000\n", state).communicate(timeout=60)

        reader = self._run("print(len(payload))\n", state)
        stdout, stderr = reader.communicate(timeout=60)

        assert reader.returncode == 0, stderr
        assert stdout.strip() == "300000"


class _FakeEntryPoint:
    """Records whether load() ran, which is the thing that imports foreign code."""

    def __init__(self, name, factory=None, *, explode=False):
        self.name = name
        self._factory = factory or (lambda: _StubBackend())
        self._explode = explode
        self.loaded = False

    def load(self):
        self.loaded = True
        if self._explode:
            msg = "hostile plugin"
            raise RuntimeError(msg)
        return self._factory


@pytest.fixture
def entry_points(monkeypatch):
    """Serve a canned set of lfx.sandbox_backends entry points to the registry."""

    def _install(*points):
        monkeypatch.setattr(registry_module, "_entry_points_loaded", False)
        monkeypatch.setattr(
            registry_module,
            "_factories",
            dict(registry_module._factories),
        )
        monkeypatch.setattr(registry_module, "_instances", dict(registry_module._instances))
        import importlib.metadata

        monkeypatch.setattr(
            importlib.metadata,
            "entry_points",
            lambda group=None: list(points) if group == registry_module._ENTRY_POINT_GROUP else [],
        )
        return points

    return _install


class TestSandboxBackendPlugins:
    """Loading a plugin imports foreign code into the security path, so it is opt-in."""

    def test_nothing_is_imported_without_the_allowlist(self, monkeypatch, entry_points):
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", raising=False)
        (point,) = entry_points(_FakeEntryPoint("vendor"))

        names = registry_module.known_sandbox_backends()

        assert not point.loaded, "an unlisted plugin must never be imported"
        assert "vendor" not in names

    def test_an_allowlisted_plugin_is_loaded(self, monkeypatch, entry_points):
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        (point,) = entry_points(_FakeEntryPoint("vendor"))

        names = registry_module.known_sandbox_backends()

        assert point.loaded
        assert "vendor" in names

    def test_an_unlisted_plugin_is_skipped_while_a_listed_one_loads(self, monkeypatch, entry_points):
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "wanted")
        wanted, unwanted = entry_points(_FakeEntryPoint("wanted"), _FakeEntryPoint("unwanted"))

        names = registry_module.known_sandbox_backends()

        assert wanted.loaded
        assert not unwanted.loaded
        assert "wanted" in names
        assert "unwanted" not in names

    def test_a_plugin_cannot_take_over_a_builtin_name(self, monkeypatch, entry_points):
        """Otherwise an installed package becomes exec-sandbox while settings still say so."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "exec-sandbox")
        (point,) = entry_points(_FakeEntryPoint("exec-sandbox"))

        registry_module.known_sandbox_backends()

        assert not point.loaded, "a built-in name must be refused before the import"
        assert registry_module._factories["exec-sandbox"] is exec_module._ExecSandboxExecutor

    def test_registering_over_a_builtin_is_refused(self):
        with pytest.raises(ValueError, match="built-in sandbox backend"):
            registry_module.register_sandbox_backend("exec-sandbox", _StubBackend)

    def test_a_plugin_that_fails_to_load_does_not_break_startup(self, monkeypatch, entry_points):
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "broken,fine")
        broken, fine = entry_points(_FakeEntryPoint("broken", explode=True), _FakeEntryPoint("fine"))

        names = registry_module.known_sandbox_backends()

        assert broken.loaded
        assert fine.loaded
        assert "broken" not in names
        assert "fine" in names

    def test_a_missing_plugin_fails_closed_at_dispatch(self, monkeypatch, entry_points):
        """An absent backend refuses the run; it never degrades to in-process exec."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        entry_points(_FakeEntryPoint("vendor", explode=True))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("vendor"))

        with pytest.raises(SandboxUnavailableError, match="Unknown sandbox backend"):
            run_code_in_sandbox("print(1)")

    def test_the_allowlist_ignores_blanks_and_spacing(self, monkeypatch, entry_points):
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", " vendor , , ")
        (point,) = entry_points(_FakeEntryPoint("vendor"))

        assert "vendor" in registry_module.known_sandbox_backends()
        assert point.loaded

    def test_an_allowlisted_plugin_still_faces_the_policy_gate(self, monkeypatch, entry_points):
        """A declaration is configuration metadata, not evidence of enforcement."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        weak = _StubBackend(base_module.Capabilities(isolation="process", supports_deny_all_egress=True))
        weak.name = "vendor"
        entry_points(_FakeEntryPoint("vendor", factory=lambda: weak))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("vendor"))

        with pytest.raises(SandboxUnavailableError, match="not a hardware-virtualized boundary"):
            run_code_in_sandbox("print(1)")


class TestRegistryLockDiscipline:
    """The registry mutex must never be held while foreign code runs, or inherited across a fork."""

    def test_a_factory_may_call_back_into_the_registry(self, monkeypatch):
        """A factory that reads the registry must not deadlock on the registry's own lock.

        `_lock` is a plain Lock, so building the instance while holding it hangs
        the process permanently the first time any factory calls back in. There
        is no timeout and no error to observe, so this test asserts on
        completion rather than on a value.
        """
        seen = {}

        def factory():
            seen["names"] = registry_module.known_sandbox_backends()
            return _StubBackend()

        monkeypatch.setitem(registry_module._factories, "callsback", factory)
        monkeypatch.delitem(registry_module._instances, "callsback", raising=False)

        done = threading.Event()
        result = {}

        def build():
            result["backend"] = registry_module.resolve_sandbox_backend("callsback")
            done.set()

        worker = threading.Thread(target=build, daemon=True)
        worker.start()
        assert done.wait(timeout=5), "resolve_sandbox_backend deadlocked while calling the factory"
        assert "callsback" in seen["names"]
        assert isinstance(result["backend"], _StubBackend)

    def test_a_slow_factory_does_not_block_other_readers(self, monkeypatch):
        """known_sandbox_backends() runs in the settings validator at startup.

        A factory probes hardware or validates control-plane configuration, so
        holding a process-wide lock for its duration stalls an unrelated
        caller for exactly that long.
        """
        release = threading.Event()

        def slow_factory():
            release.wait(timeout=5)
            return _StubBackend()

        monkeypatch.setitem(registry_module._factories, "slow", slow_factory)
        monkeypatch.delitem(registry_module._instances, "slow", raising=False)

        building = threading.Thread(target=lambda: registry_module.resolve_sandbox_backend("slow"), daemon=True)
        building.start()
        time.sleep(0.1)  # let the factory get inside

        read = threading.Event()
        threading.Thread(target=lambda: (registry_module.known_sandbox_backends(), read.set()), daemon=True).start()
        assert read.wait(timeout=2), "known_sandbox_backends() blocked behind a running factory"

        release.set()
        building.join(timeout=5)

    def test_the_registry_mutex_is_replaced_after_a_fork(self):
        """A lock inherited locked has no owner in the child, so every reader hangs forever.

        The fork hook reads the registry before it touches anything else, so
        the child would block inside the hook itself, where the surrounding
        suppress() cannot help: it is blocked, not raising.
        """
        before = registry_module._lock
        registry_module.reset_registry_after_fork()
        try:
            assert registry_module._lock is not before
            assert not registry_module._lock.locked()
        finally:
            registry_module._lock = before

    def test_the_fork_hook_resets_the_registry_before_reading_it(self, monkeypatch):
        """Order matters: the reset has to happen before live_sandbox_backends() is called."""
        order = []
        monkeypatch.setattr(sandbox_module, "reset_registry_after_fork", lambda: order.append("reset"))
        monkeypatch.setattr(sandbox_module, "live_sandbox_backends", lambda: order.append("read") or ())

        sandbox_module._reinit_backends_after_fork()

        assert order == ["reset", "read"]


class TestEntryPointLoadingIsAtomic:
    """A reader must never observe a half-populated registry."""

    def test_a_concurrent_reader_waits_for_the_load_to_finish(self, monkeypatch, entry_points):
        """Setting the latch before loading lets a second thread read a partial list.

        The settings validator consumes exactly that list, so a plugin backend
        that is still registering is reported as unknown and startup fails
        with "sandbox_backend must be one of".
        """
        inside = threading.Event()
        release = threading.Event()

        class _SlowEntryPoint:
            """load() imports third-party code, which is the slow part."""

            name = "slowplugin"

            def load(self):
                inside.set()
                release.wait(timeout=5)
                return _StubBackend

        entry_points(_SlowEntryPoint())
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "slowplugin")

        threading.Thread(target=registry_module.known_sandbox_backends, daemon=True).start()
        assert inside.wait(timeout=5)

        observed = {}
        reader = threading.Thread(
            target=lambda: observed.update(names=registry_module.known_sandbox_backends()), daemon=True
        )
        reader.start()
        reader.join(timeout=0.5)
        assert not observed, "a reader returned while the load was still running"

        release.set()
        reader.join(timeout=5)
        assert "slowplugin" in observed["names"]


class TestPluginRegistrationFailuresAreNotFatal:
    """A broken plugin must leave Langflow able to start."""

    def test_a_plugin_named_none_is_refused_instead_of_crashing(self, monkeypatch, entry_points):
        """`none` is reserved, and register_sandbox_backend raises ValueError on it.

        Unguarded, that ValueError propagates out of the settings validator and
        Langflow does not start -- the opposite of what _load_entry_points
        documents.
        """
        entry_points(_FakeEntryPoint("none", lambda: _StubBackend))
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "none")

        names = registry_module.known_sandbox_backends()

        assert names.count("none") == 1
        assert registry_module._factories.get("none") is None

    def test_a_plugin_name_is_lowercased_so_it_can_be_selected(self, monkeypatch, entry_points):
        """The settings validator lowercases sandbox_backend before the membership check.

        A name kept in its original case is listed as available and yet can
        never be selected, which reports "must be one of" against a list that
        looks identical to what the operator configured.
        """
        entry_points(_FakeEntryPoint("VendorBox", lambda: _StubBackend))
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "VendorBox")

        names = registry_module.known_sandbox_backends()

        assert "vendorbox" in names
        assert "VendorBox" not in names


class TestSettingsUnavailableFailsClosed:
    """A settings stack that failed to build must not silently disable the sandbox."""

    def test_the_configured_backend_survives_an_unresolvable_settings_service(self, monkeypatch):
        """get_settings_service() returns None when settings failed to build.

        Answering "none" there sends user code to in-process exec on a
        deployment that explicitly asked for a sandbox.
        """
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND", "exec-sandbox")

        assert get_sandbox_backend() == "exec-sandbox"
        assert is_sandbox_enabled()

    def test_an_unconfigured_deployment_still_reports_none(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)

        assert get_sandbox_backend() == "none"


class TestCapabilitiesDefaultsGrantNothing:
    """An omitted capability must be refused, not trusted."""

    def test_a_backend_that_never_names_its_isolation_is_refused(self, monkeypatch, stub_backend):
        """The isolation field is what the strongest gate reads.

        Defaulting it to "hardware-virtualized" lets a plugin clear that gate
        by saying nothing, which contradicts the rule that a backend never
        approves its own policy.
        """
        stub_backend(base_module.Capabilities(supports_deny_all_egress=True, supports_domain_allowlist=True))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        with pytest.raises(SandboxUnavailableError, match="not a hardware-virtualized boundary"):
            run_code_in_sandbox("print(1)")

    def test_every_other_default_grants_nothing_either(self):
        caps = base_module.Capabilities()
        assert caps.isolation != "hardware-virtualized"
        assert not caps.supports_deny_all_egress
        assert not caps.supports_domain_allowlist
        assert not caps.supports_sessions
        assert not caps.supports_artifacts
        assert caps.max_timeout_seconds is None


class TestSessionModeIsAllowlisted:
    """An unrecognized session mode must run cold, not reuse a guest."""

    def test_an_unknown_session_mode_does_not_reuse_a_guest(self, monkeypatch, stub_backend):
        """_sandbox_settings reads the mode with getattr and validates nothing.

        "Anything but off" therefore grants reuse to a value that never passed
        the settings validator, and reuse is the direction that weakens
        isolation between executions.
        """
        backend = stub_backend(
            base_module.Capabilities(
                isolation="hardware-virtualized",
                supports_deny_all_egress=True,
                supports_domain_allowlist=True,
                supports_sessions=True,
            )
        )
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: _settings("stub", sandbox_session_mode="FLOW-typo"),
        )

        run_code_in_sandbox("print(1)", session=base_module.SessionKey(flow_id="f", user_id="u"))

        assert backend.runs[0][1] is None


class TestBackendRegistrationIsIdempotent:
    """Re-executing a backend module must not raise."""

    @pytest.mark.parametrize("module_name", ["exec_sandbox", "createos"])
    def test_reimporting_a_builtin_backend_module_does_not_raise(self, module_name):
        """seal_builtins() has already run, so a second registration is refused by design.

        The refusal is correct. Letting it escape as ValueError out of an
        import is not.

        The reload rebinds every attribute of the module, and the suppressed
        re-registration means _factories keeps pointing at the PRE-reload
        class. test_a_plugin_cannot_take_over_a_builtin_name asserts exactly
        that identity, so the module state is restored here rather than left
        for whatever test happens to run next.
        """
        module = importlib.import_module(f"lfx.utils.sandbox.{module_name}")
        before = dict(vars(module))

        importlib.reload(module)

        # Put the original attribute objects back, so the identity the registry
        # holds and the identity the module exposes stay the same object.
        for name, value in before.items():
            setattr(module, name, value)


class TestTheLosingInstanceIsShutDown:
    """Only one instance is kept, so the other one has to be told to stop."""

    def test_the_instance_that_loses_the_race_is_shut_down(self, monkeypatch):
        """The setdefault call keeps the first instance and drops the second.

        The dropped one is not in _instances, so live_sandbox_backends() never
        returns it and shutdown_sandbox() cannot reach it. A factory that
        acquired a loop thread or a client pool would leak it for the process
        lifetime.
        """

        class _Closable(_StubBackend):
            def __init__(self):
                super().__init__()
                self.stopped = False

            def shutdown(self):
                self.stopped = True

        winner = _Closable()
        loser = _Closable()

        def factory():
            # Stands in for another thread that finished first while this
            # factory was still building.
            registry_module._instances["racy"] = winner
            return loser

        monkeypatch.setitem(registry_module._factories, "racy", factory)
        monkeypatch.delitem(registry_module._instances, "racy", raising=False)

        assert registry_module.resolve_sandbox_backend("racy") is winner
        assert loser.stopped, "the losing instance was never shut down"
        assert not winner.stopped, "the kept instance must not be shut down"

    def test_a_shutdown_that_raises_does_not_break_resolution(self, monkeypatch):
        """Cleaning up the loser is best effort; it must not fail the caller."""

        class _Angry(_StubBackend):
            def shutdown(self):
                msg = "no"
                raise RuntimeError(msg)

        winner = _Angry()

        def factory():
            registry_module._instances["angry"] = winner
            return _Angry()

        monkeypatch.setitem(registry_module._factories, "angry", factory)
        monkeypatch.delitem(registry_module._instances, "angry", raising=False)

        assert registry_module.resolve_sandbox_backend("angry") is winner


class TestPluginAllowlistMatchingIsCaseInsensitive:
    """Registration lowercases, so the allowlist match has to as well."""

    def test_an_operator_may_spell_the_plugin_name_in_any_case(self, monkeypatch, entry_points):
        """Matching verbatim on one side and normalizing on the other is a silent skip.

        The only trace is a debug log, and the startup failure then reports the
        backend as unknown.
        """
        entry_points(_FakeEntryPoint("VendorBox", lambda: _StubBackend))
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendorbox")

        assert "vendorbox" in registry_module.known_sandbox_backends()
