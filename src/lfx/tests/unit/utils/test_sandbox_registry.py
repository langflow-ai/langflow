"""Tests for sandbox settings, backend registration, and policy enforcement."""

import importlib
import importlib.util
import os
import threading
import time
from types import SimpleNamespace

import pytest
from lfx.utils import sandbox as sandbox_module
from lfx.utils.sandbox import SandboxUnavailableError, get_sandbox_backend, is_sandbox_enabled, run_code_in_sandbox
from lfx.utils.sandbox import base as base_module
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
    atexit.unregister(executor.shutdown)
    executor.shutdown()
    loop, thread = executor._loop, executor._thread
    if loop is not None and not loop.is_closed():
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)
        loop.close()


class TestSettingsValidation:
    """Verify SecuritySettings validates and normalizes sandbox configuration."""

    def test_unknown_backend_rejected_at_settings_level(self):
        """Verify that an unrecognized sandbox_backend is rejected at settings construction."""
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

    def test_allowed_domains_normalized(self):
        """Verify that allowed domains are trimmed and blanks are dropped."""
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
        """Verify that sandbox_backend is lowercased, and defaults to "none"."""
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
        """Verify that real guest code executes successfully in a live microVM."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("exec-sandbox"))
        result = run_code_in_sandbox("print('sandbox ok')", global_imports="math")
        assert result.success
        assert result.stdout.strip() == "sandbox ok"

    def test_real_guest_user_error(self, monkeypatch):
        """Verify that a real guest NameError is reported as a failed result."""
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
        """Store the given capabilities, or a fully-permissive default set."""
        self._capabilities = capabilities or base_module.Capabilities(
            isolation="hardware-virtualized", supports_deny_all_egress=True, supports_domain_allowlist=True
        )
        self.runs: list[str] = []

    def capabilities(self):
        """Return the stored capabilities."""
        return self._capabilities

    def run(self, code, *, env=None):  # noqa: ARG002
        """Record the code and return a canned success result."""
        self.runs.append(code)
        return base_module.SandboxResult(stdout="stub", stderr="", exit_code=0)

    def shutdown(self):
        """Do nothing; a no-op shutdown for the stub backend."""

    def reset_after_fork(self):
        """Do nothing; a no-op fork reset for the stub backend."""


@pytest.fixture
def stub_backend(monkeypatch):
    """Register a stub under its own name and return an installer for it."""

    def _install(capabilities=None):
        """Register and return a stub backend built with the given capabilities."""
        backend = _StubBackend(capabilities)
        monkeypatch.setitem(registry_module._factories, "stub", lambda: backend)
        monkeypatch.setitem(registry_module._instances, "stub", backend)
        return backend

    return _install


class TestRegistry:
    """Verify how the sandbox backend registry registers and resolves backends."""

    def test_in_tree_backends_are_registered(self):
        """Verify that "none" and "exec-sandbox" are known backends."""
        names = registry_module.known_sandbox_backends()
        assert "none" in names
        assert "exec-sandbox" in names

    def test_none_cannot_be_claimed_by_a_backend(self):
        """Verify that registering a backend under the reserved name "none" is refused."""
        with pytest.raises(ValueError, match="reserved"):
            registry_module.register_sandbox_backend("none", _StubBackend)

    @pytest.mark.parametrize("name", ["", "   "])
    def test_a_backend_name_cannot_be_empty(self, name):
        """Verify that an empty normalized name is not added to the registry."""
        with pytest.raises(ValueError, match="cannot be empty"):
            registry_module.register_sandbox_backend(name, _StubBackend)

    def test_a_backend_factory_must_be_callable(self):
        """Verify that malformed plugin objects fail during registration, not first execution."""
        with pytest.raises(TypeError, match="callable factory"):
            registry_module.register_sandbox_backend("broken", object())  # type: ignore[arg-type]

    def test_a_registered_name_cannot_be_replaced(self, monkeypatch):
        """Verify that re-registration cannot orphan a live backend or race its factory."""
        monkeypatch.setitem(registry_module._factories, "taken", _StubBackend)

        with pytest.raises(ValueError, match="already registered"):
            registry_module.register_sandbox_backend("taken", lambda: _StubBackend())

        assert registry_module._factories["taken"] is _StubBackend

    def test_a_registered_backend_is_dispatched_to(self, monkeypatch, stub_backend):
        """Verify that a registered backend receives the run call and its result is returned."""
        backend = stub_backend()
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        result = run_code_in_sandbox("print(1)")

        assert result.stdout == "stub"
        assert len(backend.runs) == 1

    def test_an_unregistered_backend_fails_closed(self, monkeypatch):
        """Verify that an unregistered backend name raises SandboxUnavailableError."""
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("no-such-backend"))
        with pytest.raises(SandboxUnavailableError, match="Unknown sandbox backend"):
            run_code_in_sandbox("print(1)")

    def test_the_factory_is_called_once(self, monkeypatch):
        """Verify that resolve_sandbox_backend caches the built instance across calls."""
        built = []

        def factory():
            """Record a build and return a new stub backend."""
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
        """Verify that a backend with process-level isolation is refused."""
        stub_backend(base_module.Capabilities(isolation="process", supports_deny_all_egress=True))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        with pytest.raises(SandboxUnavailableError, match="not a hardware-virtualized boundary"):
            run_code_in_sandbox("print(1)")

    def test_a_backend_that_cannot_deny_egress_is_refused(self, monkeypatch, stub_backend):
        """Verify that a backend unable to deny all egress is refused."""
        stub_backend(base_module.Capabilities(isolation="hardware-virtualized", supports_deny_all_egress=False))
        monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("stub"))

        with pytest.raises(SandboxUnavailableError, match="cannot block all egress"):
            run_code_in_sandbox("print(1)")

    def test_a_backend_without_domain_filtering_is_refused(self, monkeypatch, stub_backend):
        """Verify that a backend without domain-allowlist support is refused when domains are configured."""
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

    def test_a_timeout_above_the_backend_cap_is_refused(self, monkeypatch, stub_backend):
        """Verify that a configured timeout above the backend's max_timeout_seconds is refused."""
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


class _FakeEntryPoint:
    """Records whether load() ran, which is the thing that imports foreign code."""

    def __init__(self, name, factory=None, *, explode=False, dist=None):
        """Store the entry point name, factory, distribution, and whether load() should raise."""
        self.name = name
        self.dist = SimpleNamespace(name=dist) if dist else None
        self._factory = factory or (lambda: _StubBackend())
        self._explode = explode
        self.loaded = False

    def load(self):
        """Mark the entry point as loaded, then return the factory or raise if configured to explode."""
        self.loaded = True
        if self._explode:
            msg = "hostile plugin"
            raise RuntimeError(msg)
        return self._factory


@pytest.fixture
def entry_points(monkeypatch):
    """Serve a canned set of lfx.sandbox_backends entry points to the registry."""

    def _install(*points):
        """Register the given entry points as the registry's canned plugin list."""
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
        """Verify that a plugin absent from the allowlist is never loaded."""
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", raising=False)
        (point,) = entry_points(_FakeEntryPoint("vendor"))

        names = registry_module.known_sandbox_backends()

        assert not point.loaded, "an unlisted plugin must never be imported"
        assert "vendor" not in names

    def test_an_allowlisted_plugin_is_loaded(self, monkeypatch, entry_points):
        """Verify that a plugin named in the allowlist is loaded and registered."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        (point,) = entry_points(_FakeEntryPoint("vendor"))

        names = registry_module.known_sandbox_backends()

        assert point.loaded
        assert "vendor" in names

    def test_a_plugin_import_may_read_the_registry_without_recursive_loading(self, monkeypatch, entry_points):
        """A plugin import can call the public registry API without re-entering its own load."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        point = _FakeEntryPoint("vendor")
        loads = 0

        def load_and_read_registry():
            """Model plugin import-time code that asks which backends are known."""
            nonlocal loads
            loads += 1
            registry_module.known_sandbox_backends()
            return lambda: _StubBackend()

        point.load = load_and_read_registry
        entry_points(point)

        assert "vendor" in registry_module.known_sandbox_backends()
        assert loads == 1

    def test_an_unlisted_plugin_is_skipped_while_a_listed_one_loads(self, monkeypatch, entry_points):
        """Verify that only the allowlisted plugin loads when several entry points are present."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "wanted")
        wanted, unwanted = entry_points(_FakeEntryPoint("wanted"), _FakeEntryPoint("unwanted"))

        names = registry_module.known_sandbox_backends()

        assert wanted.loaded
        assert not unwanted.loaded
        assert "wanted" in names
        assert "unwanted" not in names

    def test_two_distributions_claiming_one_name_are_both_refused(self, monkeypatch, entry_points):
        """The allowlist names a backend, not a distribution, so it cannot choose.

        Loading either would be a guess decided by whatever order
        importlib.metadata returns, and the old loop imported BOTH and let the
        second overwrite the first -- so the code that ran an import was not
        even the code that ended up registered.
        """
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "vendor")
        first, second = entry_points(
            _FakeEntryPoint("vendor", dist="vendor-a"),
            _FakeEntryPoint("vendor", dist="vendor-b"),
        )

        names = registry_module.known_sandbox_backends()

        assert not first.loaded, "a contested name must not import anything"
        assert not second.loaded, "a contested name must not import anything"
        assert "vendor" not in names

    def test_a_contested_name_does_not_stop_an_uncontested_one(self, monkeypatch, entry_points):
        """Verify that one contested plugin name does not block another that is unambiguous."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "contested,clear")
        one, two, clear = entry_points(
            _FakeEntryPoint("contested", dist="a"),
            _FakeEntryPoint("contested", dist="b"),
            _FakeEntryPoint("clear", dist="c"),
        )

        names = registry_module.known_sandbox_backends()

        assert not one.loaded
        assert not two.loaded
        assert clear.loaded
        assert "contested" not in names
        assert "clear" in names

    def test_a_duplicate_name_nobody_allowlisted_is_still_never_loaded(self, monkeypatch, entry_points):
        """Verify that an unlisted contested name is skipped without any import."""
        monkeypatch.delenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", raising=False)
        first, second = entry_points(_FakeEntryPoint("vendor"), _FakeEntryPoint("vendor"))

        registry_module.known_sandbox_backends()

        assert not first.loaded
        assert not second.loaded

    def test_a_plugin_cannot_take_over_a_builtin_name(self, monkeypatch, entry_points):
        """Otherwise an installed package becomes exec-sandbox while settings still say so."""
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "exec-sandbox")
        (point,) = entry_points(_FakeEntryPoint("exec-sandbox"))

        registry_module.known_sandbox_backends()

        assert not point.loaded, "a built-in name must be refused before the import"
        assert registry_module._factories["exec-sandbox"] is exec_module._ExecSandboxExecutor

    def test_registering_over_a_builtin_is_refused(self):
        """Verify that registering a plugin under a built-in backend name is refused."""
        with pytest.raises(ValueError, match="built-in sandbox backend"):
            registry_module.register_sandbox_backend("exec-sandbox", _StubBackend)

    def test_a_plugin_that_fails_to_load_does_not_break_startup(self, monkeypatch, entry_points):
        """Verify that one plugin's load failure does not stop a working plugin from loading."""
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
        """Verify that blank entries and surrounding spaces in the allowlist are ignored."""
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
            """Read the registry's known backends, then return a new stub backend."""
            seen["names"] = registry_module.known_sandbox_backends()
            return _StubBackend()

        monkeypatch.setitem(registry_module._factories, "callsback", factory)
        monkeypatch.delitem(registry_module._instances, "callsback", raising=False)

        done = threading.Event()
        result = {}

        def build():
            """Resolve the callsback backend and signal completion."""
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
            """Block until released, then return a new stub backend."""
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
                """Signal that loading has started, then block until released."""
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

    def test_a_plugin_that_is_not_a_factory_is_refused_instead_of_crashing(self, monkeypatch, entry_points):
        """A malformed entry-point value must not break settings validation at startup."""
        entry_points(_FakeEntryPoint("broken", object()))
        monkeypatch.setenv("LANGFLOW_SANDBOX_BACKEND_PLUGINS", "broken")

        names = registry_module.known_sandbox_backends()

        assert "broken" not in names

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
        """Verify that an unresolvable settings service with no env var still reports "none"."""
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
        """Verify that every Capabilities field defaults to a value that grants nothing."""
        caps = base_module.Capabilities()
        assert caps.isolation != "hardware-virtualized"
        assert not caps.supports_deny_all_egress
        assert not caps.supports_domain_allowlist
        assert caps.max_timeout_seconds is None


class TestBackendRegistrationIsIdempotent:
    """Re-executing a backend module must not raise."""

    @pytest.mark.parametrize("module_name", ["exec_sandbox"])
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
            """A stub backend that tracks whether shutdown() ran."""

            def __init__(self):
                """Initialize the stub backend and clear the stopped flag."""
                super().__init__()
                self.stopped = False

            def shutdown(self):
                """Mark this instance as stopped."""
                self.stopped = True

        winner = _Closable()
        loser = _Closable()

        def factory():
            """Simulate a concurrent winner claiming the slot, then return the loser."""
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
            """A stub backend whose shutdown() always raises."""

            def shutdown(self):
                """Raise RuntimeError to simulate a broken shutdown."""
                msg = "no"
                raise RuntimeError(msg)

        winner = _Angry()

        def factory():
            """Simulate a concurrent winner claiming the slot, then return a new loser."""
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
