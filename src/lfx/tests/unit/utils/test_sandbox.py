"""Unit tests for the opt-in microVM sandbox backend (issue #12029).

These tests never require exec-sandbox or QEMU: the exec_sandbox module is
stubbed into sys.modules so the routing, fail-closed, and result-mapping logic
is exercised everywhere CI runs.
"""

import os
import sys
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
from lfx.utils.sandbox import exec_sandbox as exec_module
from lfx.utils.sandbox import registry as registry_module


def _settings(backend, **extra):
    """Return a fake settings service with the given sandbox backend and overrides."""
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
    """Stand in for exec_sandbox's execution result value."""

    def __init__(self, stdout="", stderr="", exit_code=0, execution_time_ms=5):
        """Store the fake stdout, stderr, exit code, and execution time."""
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms


class _FakeScheduler:
    """Stands in for exec_sandbox.Scheduler; records the kwargs run() received."""

    instances: list = []

    def __init__(self, config=None):
        """Store the config and record this instance for later inspection."""
        self.config = config
        self.run_calls: list[dict] = []
        self.entered = False
        self.exited = False
        type(self).instances.append(self)

    async def __aenter__(self):
        """Yield control, then mark the scheduler as entered."""
        # Yield control so concurrent first calls genuinely interleave here,
        # exercising the scheduler-creation lock.
        import asyncio

        await asyncio.sleep(0.02)
        self.entered = True
        return self

    async def __aexit__(self, *args):
        """Mark the scheduler as exited without suppressing an exception."""
        self.exited = True
        return False

    async def run(self, **kwargs):
        """Record the run call and return a canned result based on the code sent."""
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
    """Stand in for exec_sandbox.SchedulerConfig; records the kwargs it received."""

    def __init__(self, **kwargs):
        """Store the kwargs the config was built with."""
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
        """Return a fake upstream settings object reading EXEC_SANDBOX_FORCE_EMULATION."""
        # Mirrors upstream: a pydantic bool field fed by EXEC_SANDBOX_FORCE_EMULATION.
        raw = os.environ.get("EXEC_SANDBOX_FORCE_EMULATION", "").strip().lower()
        return SimpleNamespace(force_emulation=raw in {"1", "true", "yes", "on", "y", "t"})

    async def _detect_accel_type(kvm_available=None, hvf_available=None, *, force_emulation=False):  # noqa: ARG001
        """Return "kvm", or "tcg" when emulation is forced."""
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
    """Verify how the configured sandbox backend is resolved."""

    def test_default_is_none(self, monkeypatch):
        """Verify that the sandbox backend defaults to "none" and stays disabled."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))
        assert get_sandbox_backend() == "none"
        assert not is_sandbox_enabled()

    def test_exec_sandbox_enables(self, monkeypatch):
        """Verify that selecting exec-sandbox enables the sandbox."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        assert get_sandbox_backend() == "exec-sandbox"
        assert is_sandbox_enabled()

    # An unresolvable settings stack falls back to the environment, so these
    # three assert the "nothing is configured anywhere" case and have to clear
    # the variable. TestSettingsUnavailableFailsClosed covers the case where
    # the operator DID configure a backend and settings failed to build.
    def test_absent_services_layer_means_none(self, monkeypatch):
        """Verify that a missing settings service with no env var means "none"."""
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.delattr("lfx.services.deps.get_settings_service")
        assert get_sandbox_backend() == "none"

    def test_none_settings_service_means_none(self, monkeypatch):
        """Verify that a settings service returning None means "none"."""
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        assert get_sandbox_backend() == "none"

    def test_settings_without_field_means_none(self, monkeypatch):
        """Verify that a settings object missing the sandbox_backend field means "none"."""
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND", raising=False)
        monkeypatch.setattr(
            "lfx.services.deps.get_settings_service",
            lambda: SimpleNamespace(settings=SimpleNamespace()),
        )
        assert get_sandbox_backend() == "none"


class TestImportPreamble:
    """Verify how build_import_preamble turns a module list into import statements."""

    def test_string_input(self):
        """Verify that a comma-separated string builds one import per module."""
        assert build_import_preamble("math, json") == "import math\nimport json"

    def test_list_input(self):
        """Verify that a list of module names builds one import per module."""
        assert build_import_preamble(["math", "os.path"]) == "import math\nimport os.path"

    def test_empty(self):
        """Verify that an empty string or list builds an empty preamble."""
        assert build_import_preamble("") == ""
        assert build_import_preamble([]) == ""

    def test_rejects_injection(self):
        """Verify that a module name with extra statements is rejected."""
        with pytest.raises(ValueError, match="Invalid module name"):
            build_import_preamble("math; import os")
        with pytest.raises(ValueError, match="Invalid module name"):
            build_import_preamble("os\nimport subprocess")

    def test_rejects_non_string_types(self):
        """Verify that a non-string, non-list input raises TypeError."""
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
        """Verify that markdown code fences and surrounding whitespace are stripped."""
        assert sanitize_code(raw) == expected


class TestRunCodeInSandbox:
    """Verify run_code_in_sandbox's routing, result mapping, and fail-closed behavior."""

    def test_refuses_when_not_configured(self, monkeypatch):
        """Verify that a "none" backend raises SandboxExecutionError."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))
        with pytest.raises(SandboxExecutionError, match="no sandbox backend"):
            run_code_in_sandbox("print('hi')")

    def test_unknown_backend_fails_closed(self, monkeypatch):
        """Verify that an unrecognized backend name raises SandboxUnavailableError."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("firecracker"))
        with pytest.raises(SandboxUnavailableError, match="Unknown sandbox backend"):
            run_code_in_sandbox("print('hi')")

    def test_missing_package_fails_closed(self, monkeypatch):
        """Verify that a configured backend whose package cannot import fails closed."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        monkeypatch.setitem(sys.modules, "exec_sandbox", None)  # import raises ImportError
        with pytest.raises(SandboxUnavailableError, match=r"exec-sandbox.*not installed"):
            run_code_in_sandbox("print('hi')")

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_success_maps_result(self, monkeypatch):
        """Verify that a successful run maps to a success result with stdout and exit code."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("print('hello from vm')")
        assert result.success
        assert result.stdout == "hello from vm\n"
        assert result.exit_code == 0

    def test_global_imports_prepended(self, monkeypatch, fake_exec_sandbox):
        """Verify that global_imports are prepended as import statements before the code."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        run_code_in_sandbox("print(math.pi)", global_imports="math, json")
        scheduler = fake_exec_sandbox.instances[-1]
        code = scheduler.run_calls[-1]["code"]
        assert code.startswith("import math\nimport json\n")
        assert code.endswith("print(math.pi)")

    def test_settings_forwarded_to_backend(self, monkeypatch, fake_exec_sandbox):
        """Verify that timeout, memory, network, and domain settings reach the backend's run call."""
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
        """Verify that user code failure returns a failed result, not a raised exception."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("FAIL_CODE")
        assert not result.success
        assert result.exit_code == 1
        assert "NameError" in result.error_message()

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_timeout_exit_code_message(self, monkeypatch):
        """Verify that a timeout exit code produces a "timed out" error message."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("TIMEOUT")
        assert not result.success
        assert "timed out" in result.error_message()

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_infrastructure_error_wrapped(self, monkeypatch):
        """Verify that a scheduler exception is wrapped in SandboxExecutionError."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        with pytest.raises(SandboxExecutionError, match="vm exploded"):
            run_code_in_sandbox("BOOM_INFRA")

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_oom_exit_code_message(self, monkeypatch):
        """Verify that an OOM exit code produces a "memory" error message."""
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
            """Return "tcg" regardless of arguments."""
            return "tcg"

        monkeypatch.setattr(sys.modules["exec_sandbox.system_probes"], "detect_accel_type", _tcg_accel)
        with pytest.raises(SandboxUnavailableError, match="TCG"):
            run_code_in_sandbox("print('hi')")
        assert not fake_exec_sandbox.instances

    def test_fails_closed_when_accel_decision_unobtainable(self, monkeypatch, fake_exec_sandbox):
        """If upstream's decision API is missing, refuse — never guess via the shallow check."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))

        async def _boom(**_kwargs):
            """Raise RuntimeError to simulate a missing accelerator decision API."""
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
        """Verify that a semicolon-joined statement after a docstring composes correctly."""
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
        """Verify that sandbox_allow_software_emulation lets a run proceed under TCG."""
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
            """Return an accelerator type that is neither KVM, HVF, nor TCG."""
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
            """Signal that the loop is frozen, then block until released."""
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
            """Signal that the loop is frozen, then block until released."""
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
            """Run code in the sandbox and collect the result."""
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
            """Run code in the sandbox and collect the result."""
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
            """Wait at the barrier, then run code in the sandbox, recording any exception."""
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
        """Verify that a second call reuses the same scheduler instance."""
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
        """Verify that the Python Interpreter component routes code through the sandbox."""
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLComponent(global_imports="math", python_code="print('hello from vm')")
        data = component.run_python_repl()
        assert data.data == {"result": "hello from vm"}
        # Sandbox mode must not exec in-process: the fake scheduler saw the code.
        assert fake_exec_sandbox.instances[-1].run_calls

    @pytest.mark.usefixtures("fake_exec_sandbox")
    def test_python_interpreter_sandbox_error(self, monkeypatch):
        """Verify that a sandboxed user-code error surfaces in the component's error data."""
        from lfx.components.utilities.python_repl_core import PythonREPLComponent

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        component = PythonREPLComponent(global_imports="math", python_code="FAIL_CODE")
        data = component.run_python_repl()
        assert "NameError" in data.data["error"]

    def test_python_interpreter_fails_closed_without_package(self, monkeypatch):
        """Verify that the component raises SandboxUnavailableError when exec-sandbox is missing."""
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
            """Stand in for langchain_experimental's PythonREPL, exec'ing in-process."""

            def __init__(self, _globals=None):
                """Store the globals dict code will execute against."""
                self._globals = _globals or {}

            @staticmethod
            def sanitize_input(code):
                """Return the code stripped of surrounding whitespace."""
                return code.strip()

            def run(self, code):
                """Execute the code in-process and return captured stdout."""
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
            """Raise AssertionError to prove the sandbox entry point is never called."""
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
        """Verify that the Python REPL tool component routes code through the sandbox."""
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
            """Stand in for langchain_experimental's PythonREPL, exec'ing in-process."""

            def __init__(self, _globals=None):
                """Store the globals dict code will execute against."""
                self._globals = _globals or {}

            @staticmethod
            def sanitize_input(code):
                """Return the code stripped of surrounding whitespace."""
                return code.strip()

            def run(self, code):
                """Execute the code in-process and return captured stdout."""
                out = io.StringIO()
                with redirect_stdout(out):
                    exec(code, self._globals)  # noqa: S102
                return out.getvalue()

        fake_utilities = SimpleNamespace(PythonREPL=_FakePythonREPL)
        monkeypatch.setitem(sys.modules, "langchain_experimental", SimpleNamespace(utilities=fake_utilities))
        monkeypatch.setitem(sys.modules, "langchain_experimental.utilities", fake_utilities)
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("none"))

        def _explode(*_args, **_kwargs):
            """Raise AssertionError to prove the sandbox entry point is never called."""
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
