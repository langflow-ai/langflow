"""Unit tests for the opt-in microVM sandbox backend (issue #12029).

These tests never require exec-sandbox or QEMU: the exec_sandbox module is
stubbed into sys.modules so the routing, fail-closed, and result-mapping logic
is exercised everywhere CI runs.
"""

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


def _settings(backend, **extra):
    defaults = {
        "sandbox_backend": backend,
        "sandbox_timeout_seconds": 30,
        "sandbox_memory_mb": 192,
        "sandbox_allow_network": False,
        "sandbox_warm_pool_size": 0,
    }
    defaults.update(extra)
    return SimpleNamespace(settings=SimpleNamespace(**defaults))


@pytest.fixture(autouse=True)
def fresh_executor(monkeypatch):
    """Give each test its own executor so loop threads/schedulers don't leak between tests."""
    executor = sandbox_module._ExecSandboxExecutor()
    monkeypatch.setattr(sandbox_module, "_executor", executor)
    return executor


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
        type(self).instances.append(self)

    async def __aenter__(self):
        # Yield control so concurrent first calls genuinely interleave here,
        # exercising the scheduler-creation lock.
        import asyncio

        await asyncio.sleep(0.02)
        self.entered = True
        return self

    async def __aexit__(self, *args):
        return False

    async def run(self, **kwargs):
        self.run_calls.append(kwargs)
        code = kwargs["code"]
        if "BOOM_INFRA" in code:
            msg = "vm exploded"
            raise RuntimeError(msg)
        if "FAIL_CODE" in code:
            return _FakeExecutionResult(stderr="NameError: nope", exit_code=1)
        if "TIMEOUT" in code:
            return _FakeExecutionResult(exit_code=-1)
        return _FakeExecutionResult(stdout="hello from vm\n")


class _FakeSchedulerConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


@pytest.fixture
def fake_exec_sandbox(monkeypatch):
    """See _install_fake_exec_sandbox; kept as a named fixture for value access."""
    return _install_fake_exec_sandbox(monkeypatch)


def _install_fake_exec_sandbox(monkeypatch):
    """Install a stub exec_sandbox module and return the fake Scheduler class."""
    _FakeScheduler.instances = []
    module = SimpleNamespace(Scheduler=_FakeScheduler, SchedulerConfig=_FakeSchedulerConfig)
    monkeypatch.setitem(sys.modules, "exec_sandbox", module)
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

    def test_absent_services_layer_means_none(self, monkeypatch):
        monkeypatch.delattr("lfx.services.deps.get_settings_service")
        assert get_sandbox_backend() == "none"

    def test_none_settings_service_means_none(self, monkeypatch):
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: None)
        assert get_sandbox_backend() == "none"

    def test_settings_without_field_means_none(self, monkeypatch):
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
                sandbox_warm_pool_size=2,
            ),
        )
        run_code_in_sandbox("print('hi')")
        scheduler = fake_exec_sandbox.instances[-1]
        call = scheduler.run_calls[-1]
        assert call["timeout_seconds"] == 77
        assert call["memory_mb"] == 256
        assert call["allow_network"] is True
        # exec_sandbox's run() takes env_vars (not env)
        assert call["env_vars"] == {}
        assert scheduler.config.kwargs == {"warm_pool_size": 2}

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

    def test_concurrent_first_calls_create_one_scheduler(self, monkeypatch, fake_exec_sandbox):
        """Two racing first executions must share one scheduler (no leaked VM pool)."""
        import threading

        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        errors = []

        def call():
            try:
                run_code_in_sandbox("print('hi')")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=call) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
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
        with pytest.raises(ValidationError):
            SecuritySettings(sandbox_warm_pool_size=-1)
        with pytest.raises(ValidationError):
            SecuritySettings(sandbox_warm_pool_size=100000)

    def test_backend_normalized(self):
        from lfx.services.settings.groups.security import SecuritySettings

        assert SecuritySettings(sandbox_backend="Exec-Sandbox").sandbox_backend == "exec-sandbox"
        assert SecuritySettings().sandbox_backend == "none"
