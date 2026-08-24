"""Tests for the CreateOS sandbox backend.

Split from ``test_sandbox.py`` the same way the module was split: everything
here drives ``lfx.utils.sandbox.createos`` against a fake control plane, and
nothing here needs a QEMU host.

The fake serves the API's real shapes — a JSend envelope for control calls,
NDJSON for a streamed exec — because several of these tests exist to prove the
backend refuses a control plane that disagrees with the policy it was sent. A
fake that echoed the request back would make those tests pass whether or not
the check existed.
"""

import io
import json
import tarfile
import threading
from types import SimpleNamespace

import httpx
import pytest
from lfx.utils.sandbox import (
    SandboxExecutionError,
    SandboxUnavailableError,
    SessionKey,
    known_sandbox_backends,
    run_code_in_sandbox,
)
from lfx.utils.sandbox import base as base_module
from lfx.utils.sandbox import createos as createos_module
from lfx.utils.sandbox import registry as registry_module
from lfx.utils.sandbox.createos import (
    SANDBOX_BACKEND_CREATEOS,
    _is_valid_egress_rule,
)


def _settings(backend, **extra):
    """Return a settings stand-in with the given sandbox backend and overrides."""
    defaults = {
        "sandbox_backend": backend,
        "sandbox_timeout_seconds": 30,
        "sandbox_memory_mb": 192,
        "sandbox_allow_network": False,
        "sandbox_allowed_domains": [],
        "sandbox_accept_egress_exceptions": False,
        "sandbox_allow_software_emulation": False,
        "sandbox_session_mode": "off",
        "sandbox_session_idle_seconds": 600,
        "sandbox_collect_artifacts": False,
        "sandbox_max_artifact_bytes": 5 * 1024 * 1024,
    }
    defaults.update(extra)
    return SimpleNamespace(settings=SimpleNamespace(**defaults))


_SHAPE_CATALOG = [
    {"id": "s-1vcpu-256mb", "vcpu": 1, "mem_mib": 256},
    {"id": "s-1vcpu-1gb", "vcpu": 1, "mem_mib": 1024},
    {"id": "s-2vcpu-4gb", "vcpu": 2, "mem_mib": 4096},
    {"id": "s-4vcpu-4gb", "vcpu": 4, "mem_mib": 4096},
    {"id": "s-4vcpu-8gb", "vcpu": 4, "mem_mib": 8192},
]


class _FakeCreateosApi:
    """Serves canned responses and records every request it received.

    Exec is served the way the real control plane serves it: NDJSON events when
    ``?stream=true``, a JSend envelope otherwise. The two are different code
    paths in the backend (the program runs streamed, the artifact tar runs
    buffered) so the fake must not blur them.
    """

    def __init__(
        self,
        *,
        exec_result=None,
        exec_status=200,
        exec_raises=None,
        exec_stream_lines=None,
        create_data=None,
        create_ids=None,
        delete_status=200,
        exec_body="boom",
        status_after_create="running",
        artifact_archive=None,
        metrics=None,
    ):
        """Store the canned responses and behavior this fake control plane serves."""
        self.calls: list[tuple[str, str]] = []
        self.bodies: dict[str, object] = {}
        self.uploaded: bytes | None = None
        self.uploads: list[bytes] = []
        self.upload_paths: list[str] = []
        self.exec_commands: list[dict] = []
        self.created_ids: list[str] = []
        self.deleted_ids: list[str] = []
        self.exec_result = exec_result if exec_result is not None else {"stdout": "2\n", "stderr": "", "exit_code": 0}
        self.exec_status = exec_status
        self.exec_raises = exec_raises
        self.exec_stream_lines = exec_stream_lines
        self.create_data = create_data
        # Successive ids handed out by POST /v1/sandboxes, so a test can tell
        # a reused session guest from a replaced one.
        self.create_ids = list(create_ids) if create_ids else None
        self.delete_status = delete_status
        self.exec_body = exec_body
        self.status_after_create = status_after_create
        self.artifact_archive = artifact_archive
        self.artifact_bytes_served = 0
        self.artifact_chunk_size = 8192
        self.metrics = metrics if metrics is not None else {"cpu_pct": 3.5, "mem_mib": 128}
        # Overridable so a test can serve an entry this module cannot read.
        self.shapes = list(_SHAPE_CATALOG)
        # name -> id, mirroring the control plane's "unique per user among
        # non-terminal sandboxes" rule that makes create-with-name a CAS.
        self.names: dict[str, str] = {}
        self.conflicts = 0

    @staticmethod
    def _ok(data):
        """Return a JSend success envelope wrapping the given data."""
        return httpx.Response(200, json={"status": "success", "data": data})

    def _stream_body(self) -> bytes:
        """The NDJSON the real server emits: chunks, a heartbeat, then a terminal frame."""
        if self.exec_stream_lines is not None:
            return "".join(f"{json.dumps(event)}\n" for event in self.exec_stream_lines).encode()
        events: list[dict] = []
        if self.exec_result.get("stdout"):
            events.append({"stdout": self.exec_result["stdout"]})
        events.append({"hb": True})
        if self.exec_result.get("stderr"):
            events.append({"stderr": self.exec_result["stderr"]})
        events.append({"exit_code": self.exec_result.get("exit_code", 0)})
        return "".join(f"{json.dumps(event)}\n" for event in events).encode()

    def _serve_archive(self):
        """Yield the archive in chunks, recording how much the client actually pulled."""
        for start in range(0, len(self.artifact_archive), self.artifact_chunk_size):
            chunk = self.artifact_archive[start : start + self.artifact_chunk_size]
            self.artifact_bytes_served += len(chunk)
            yield chunk

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Route the request to the matching fake endpoint and record the call."""
        path = request.url.path
        self.calls.append((request.method, path))

        if path == "/v1/whoami":
            return self._ok({"user_id": "usr_test"})
        if path == "/v1/shapes":
            return self._ok({"data": self.shapes})
        if path == "/v1/sandboxes" and request.method == "POST":
            body = json.loads(request.content)
            self.bodies["create"] = body
            if self.create_data is not None:
                return self._ok(self.create_data)
            requested_name = body.get("name")
            if requested_name is not None and requested_name in self.names:
                self.conflicts += 1
                return httpx.Response(409, text=f'a sandbox named "{requested_name}" already exists')
            sandbox_id = self.create_ids.pop(0) if self.create_ids else "sb-test"
            self.created_ids.append(sandbox_id)
            if requested_name is not None:
                self.names[requested_name] = sandbox_id
            # The real control plane echoes the stored policy and the memory
            # actually granted for the requested shape; the backend verifies
            # both before running anything.
            mem = next(s["mem_mib"] for s in self.shapes if s["id"] == body["shape"])
            return self._ok({"id": sandbox_id, "egress": body["egress"], "mem_mib": mem})
        if path.endswith("/metrics"):
            return self._ok(self.metrics)
        if path.endswith("/files"):
            if request.method == "PUT":
                self.uploaded = request.content
                self.uploads.append(request.content)
                self.upload_paths.append(request.url.params.get("path", ""))
                return self._ok({})
            if self.artifact_archive is None:
                return httpx.Response(404, text="no such file")
            return httpx.Response(200, content=self._serve_archive())
        if path.endswith("/exec"):
            if self.exec_raises is not None:
                raise self.exec_raises
            self.exec_commands.append(json.loads(request.content))
            if self.exec_status != 200:
                return httpx.Response(self.exec_status, text=self.exec_body)
            if request.url.params.get("stream") == "true":
                return httpx.Response(
                    200, content=self._stream_body(), headers={"Content-Type": "application/x-ndjson"}
                )
            # Buffered mode: the artifact tar command, which reports only that
            # it ran.
            return self._ok({"result": {"stdout": "", "stderr": "", "exit_code": 0}, "exec_ms": 1.0})
        if request.method == "DELETE":
            deleted = path.rsplit("/", 1)[-1]
            self.deleted_ids.append(deleted)
            for name, sandbox_id in list(self.names.items()):
                if sandbox_id == deleted:
                    del self.names[name]
            if self.delete_status != 200:
                return httpx.Response(self.delete_status, text="cannot destroy")
            return self._ok({})
        if request.method == "GET" and path == "/v1/sandboxes":
            rows = [
                {"id": sandbox_id, "name": name, "status": "running"}
                for name, sandbox_id in self.names.items()
                if sandbox_id not in self.deleted_ids
            ]
            return self._ok({"data": rows})
        if request.method == "GET" and path.startswith("/v1/sandboxes/"):
            return self._ok({"id": path.rsplit("/", 1)[-1], "status": self.status_after_create})
        return httpx.Response(404, text=f"unexpected {path}")


@pytest.fixture
def createos(monkeypatch):
    """A fresh CreateOS executor wired to a fake control plane."""
    monkeypatch.setenv("CREATEOS_SANDBOX_API_KEY", "test-key")
    executor = createos_module._CreateosExecutor()
    monkeypatch.setitem(registry_module._instances, "createos", executor)

    def _install(api: _FakeCreateosApi) -> _FakeCreateosApi:
        """Wire the executor's client to the given fake control plane and return it."""
        monkeypatch.setattr(
            executor,
            "_client",
            lambda timeout: httpx.Client(
                base_url="https://api.sb.createos.sh",
                timeout=timeout,
                transport=httpx.MockTransport(api.handler),
            ),
        )
        return api

    return _install


def _use_createos(monkeypatch, **extra):
    """Configure createos for a test that is about something OTHER than the egress hole.

    createos declares 169.254.0.0/16 as a destination it cannot block, and the
    dispatcher refuses a restricted-egress policy against such a backend unless
    the operator accepts it. These tests are not about that decision, so they
    accept it by default. TestEgressExceptionsFailClosed covers the gate
    itself, and passes accept_egress_exceptions=False explicitly.
    """
    extra.setdefault("sandbox_accept_egress_exceptions", True)
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: _settings("createos", **extra))


class TestCreateosRegistration:
    """Verify that the createos backend registers with the shared sandbox machinery."""

    def test_backend_name_is_known(self):
        """Verify that the createos backend name appears among the known sandbox backends."""
        assert SANDBOX_BACKEND_CREATEOS in known_sandbox_backends()

    def test_settings_accept_the_backend(self):
        """Verify that SecuritySettings accepts "createos" as a valid sandbox_backend value."""
        from lfx.services.settings.groups.security import SecuritySettings

        assert SecuritySettings(sandbox_backend="createos").sandbox_backend == "createos"

    def test_settings_still_reject_typos(self):
        """Verify that SecuritySettings rejects a misspelled sandbox_backend value."""
        from lfx.services.settings.groups.security import SecuritySettings

        with pytest.raises(ValueError, match="sandbox_backend must be one of"):
            SecuritySettings(sandbox_backend="create-os")


class TestEgressRuleGrammar:
    """Verify that _is_valid_egress_rule accepts documented forms and rejects the rest."""

    @pytest.mark.parametrize(
        "rule",
        [
            "*",
            "pypi.org",
            "*.pythonhosted.org",
            "github.com:443",
            "1.1.1.1",
            "1.1.1.1:53",
            "10.0.0.0/8",
            "10.0.0.0/8:8080",
        ],
    )
    def test_accepts_documented_forms(self, rule):
        """Verify that a documented egress rule form is accepted."""
        assert _is_valid_egress_rule(rule)

    @pytest.mark.parametrize(
        "rule",
        [
            "",
            "  ",
            "pypi.org:",
            "pypi.org:0",
            "pypi.org:70000",
            "pypi.org:https",
            "-bad.org",
            "http://pypi.org",
            "a b.org",
        ],
    )
    def test_rejects_everything_else(self, rule):
        """Verify that a malformed egress rule is rejected."""
        assert not _is_valid_egress_rule(rule)


class TestCreateosExecution:
    """Verify that the createos backend runs code and maps the result correctly."""

    def test_happy_path_maps_the_result(self, monkeypatch, createos):
        """Verify that a successful run reports success, stdout, timing, and destroys the VM."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print(1+1)")

        assert result.success
        assert result.stdout == "2\n"
        # Streaming exec carries no server-side exec_ms, so the duration is the
        # client's wall clock. It covers transport as well as the guest, which
        # is why this only asserts that it was measured at all.
        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 0
        assert ("DELETE", "/v1/sandboxes/sb-test") in api.calls

    def test_import_preamble_reaches_the_guest(self, monkeypatch, createos):
        """Verify that global_imports are uploaded to the guest as import statements."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print(math.pi)", global_imports="math, json")

        assert api.uploaded is not None
        uploaded = api.uploaded.decode()
        assert "import math" in uploaded
        assert "import json" in uploaded

    def test_user_code_failure_is_a_result_not_an_exception(self, monkeypatch, createos):
        """Verify that a guest program error is reported as a failed result, not raised."""
        createos(_FakeCreateosApi(exec_result={"stdout": "", "stderr": "NameError: nope", "exit_code": 1}))
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("nope")

        assert not result.success
        assert "NameError" in result.error_message()

    def test_blank_code_short_circuits_without_touching_the_api(self, monkeypatch, createos):
        """Verify that blank code returns success without making any API call."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("   \n  ")

        assert result.success
        assert api.calls == []


class TestCreateosNetworkPolicy:
    """Verify that sandbox network settings translate into the correct egress rules."""

    def test_network_disabled_sends_a_deny_all_rule(self, monkeypatch, createos):
        """Verify that network disabled sends an explicit deny-all egress rule, not an empty list."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print('hi')")

        # Not an empty list: empty means allow-all to CreateOS.
        assert api.bodies["create"]["egress"] == ["240.0.0.0/4"]

    def test_allowed_domains_are_forwarded_with_a_resolver(self, monkeypatch, createos):
        """Verify that an allowed-domain egress list also includes a reachable DNS resolver rule."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_allow_network=True, sandbox_allowed_domains=["pypi.org"])

        run_code_in_sandbox("print('hi')")

        egress = api.bodies["create"]["egress"]
        assert "pypi.org" in egress
        assert "1.1.1.1:53" in egress, "a domain allowlist is inert without a reachable resolver"

    def test_network_enabled_without_domains_is_allow_all(self, monkeypatch, createos):
        """Verify that network enabled with no domain allowlist sends an allow-all egress rule."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_allow_network=True)

        run_code_in_sandbox("print('hi')")

        assert api.bodies["create"]["egress"] == ["*"]

    def test_unparseable_domain_refuses_before_creating_a_vm(self, monkeypatch, createos):
        """Verify that an unparseable allowed domain refuses before any sandbox is created."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_allow_network=True, sandbox_allowed_domains=["not a domain"])

        with pytest.raises(SandboxUnavailableError, match="cannot parse"):
            run_code_in_sandbox("print('hi')")

        assert ("POST", "/v1/sandboxes") not in api.calls


class TestCreateosShapeSelection:
    """Verify that the configured memory floor selects the correct CreateOS shape."""

    def test_default_shape_is_2vcpu_4gb(self, monkeypatch, createos):
        """Verify that the default memory setting selects the s-2vcpu-4gb shape."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)  # sandbox_memory_mb default is 192

        run_code_in_sandbox("print('hi')")

        # Not s-1vcpu-256mb: the 192 MB default is sized for exec-sandbox's
        # local guest and would starve a fresh CreateOS VM.
        assert api.bodies["create"]["shape"] == "s-2vcpu-4gb"

    def test_memory_below_the_default_does_not_shrink_the_vm(self, monkeypatch, createos):
        """Verify that a memory setting below the default still selects the s-2vcpu-4gb shape."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_memory_mb=300)

        run_code_in_sandbox("print('hi')")

        assert api.bodies["create"]["shape"] == "s-2vcpu-4gb"

    def test_memory_above_the_default_raises_the_floor(self, monkeypatch, createos):
        """Verify that a memory setting above the default selects a larger shape."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_memory_mb=6000)

        run_code_in_sandbox("print('hi')")

        assert api.bodies["create"]["shape"] == "s-4vcpu-8gb"

    def test_memory_beyond_the_catalog_refuses(self, monkeypatch, createos):
        """Verify that a memory setting beyond every catalog shape refuses to run."""
        createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_memory_mb=99999)

        with pytest.raises(SandboxUnavailableError, match="No CreateOS shape"):
            run_code_in_sandbox("print('hi')")

    def test_pinned_shape_is_used_verbatim(self, monkeypatch, createos):
        """Verify that a pinned shape environment variable is used as-is."""
        api = createos(_FakeCreateosApi())
        monkeypatch.setenv("CREATEOS_SANDBOX_SHAPE", "s-1vcpu-1gb")
        _use_createos(monkeypatch)

        run_code_in_sandbox("print('hi')")

        assert api.bodies["create"]["shape"] == "s-1vcpu-1gb"

    def test_unknown_pinned_shape_refuses(self, monkeypatch, createos):
        """Verify that a pinned shape absent from the catalog refuses to run."""
        createos(_FakeCreateosApi())
        monkeypatch.setenv("CREATEOS_SANDBOX_SHAPE", "s-nonexistent")
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="not in the CreateOS shape catalog"):
            run_code_in_sandbox("print('hi')")

    def test_pinned_shape_smaller_than_configured_memory_refuses(self, monkeypatch, createos):
        """Verify that a pinned shape smaller than the configured memory floor refuses to run."""
        createos(_FakeCreateosApi())
        monkeypatch.setenv("CREATEOS_SANDBOX_SHAPE", "s-1vcpu-256mb")
        _use_createos(monkeypatch, sandbox_memory_mb=1024)

        with pytest.raises(SandboxUnavailableError, match="Refusing to run the code"):
            run_code_in_sandbox("print('hi')")


class TestCreateosFailsClosed:
    """Verify that the createos backend refuses instead of running unsafely."""

    def test_missing_api_key_refuses(self, monkeypatch):
        """Verify that a missing API key refuses with a message naming the environment variable."""
        monkeypatch.delenv("CREATEOS_SANDBOX_API_KEY", raising=False)
        with pytest.raises(SandboxUnavailableError, match="CREATEOS_SANDBOX_API_KEY"):
            createos_module._CreateosExecutor._api_key()

    def test_plaintext_base_url_refuses(self, monkeypatch):
        """Verify that a non-loopback plaintext base URL refuses because it must use https."""
        monkeypatch.setenv("CREATEOS_SANDBOX_BASE_URL", "http://api.example.com")
        with pytest.raises(SandboxUnavailableError, match="must use https"):
            createos_module._CreateosExecutor._base_url()

    def test_loopback_over_http_is_allowed_for_development(self, monkeypatch):
        """Verify that a loopback base URL over plain http is allowed and its trailing slash trimmed."""
        monkeypatch.setenv("CREATEOS_SANDBOX_BASE_URL", "http://localhost:8080/")
        assert createos_module._CreateosExecutor._base_url() == "http://localhost:8080"

    def test_client_error_is_unavailable(self, monkeypatch, createos):
        """Verify that a 4xx exec response raises SandboxUnavailableError."""
        createos(_FakeCreateosApi(exec_status=403))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError):
            run_code_in_sandbox("print('hi')")

    def test_server_error_is_an_execution_error(self, monkeypatch, createos):
        """Verify that a 5xx exec response raises SandboxExecutionError."""
        createos(_FakeCreateosApi(exec_status=503))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError):
            run_code_in_sandbox("print('hi')")

    def test_timeout_maps_to_the_shared_timeout_exit_code(self, monkeypatch, createos):
        """Verify that a transport timeout maps to the shared timeout exit code and message."""
        createos(_FakeCreateosApi(exec_raises=httpx.ReadTimeout("too slow")))
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("while True: pass")

        assert result.exit_code == base_module._EXIT_CODE_TIMEOUT
        assert "timed out" in result.error_message()

    def test_the_vm_is_destroyed_even_when_execution_fails(self, monkeypatch, createos):
        """Verify that the VM is destroyed even when the execution raises an error."""
        api = createos(_FakeCreateosApi(exec_status=503))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError):
            run_code_in_sandbox("print('hi')")

        assert ("DELETE", "/v1/sandboxes/sb-test") in api.calls


class TestCreateosPolicyVerification:
    """Fixes raised by the Codex adversarial review, 2026-08-19."""

    def test_auto_pause_backstop_is_requested(self, monkeypatch, createos):
        """Verify that create requests an auto-pause backstop past the default timeout."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print('hi')")

        # Without this a VM survives a lost DELETE or a killed process. The
        # window must also outlast the execution -- see TestCreateosAutoPause.
        requested = api.bodies["create"]["auto_pause_after_seconds"]
        assert requested >= 60
        assert requested > 30, "must exceed the default sandbox_timeout_seconds"

    def test_rewritten_egress_refuses_before_running_code(self, monkeypatch, createos):
        """Verify that a control plane that rewrites the egress policy refuses before code runs."""
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["*"], "mem_mib": 4096}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="did not store the requested egress"):
            run_code_in_sandbox("print('hi')")

        assert not any(p.endswith("/exec") for _, p in api.calls), "code ran despite a rewritten policy"
        assert ("DELETE", "/v1/sandboxes/sb-test") in api.calls

    def test_downgraded_memory_refuses(self, monkeypatch, createos):
        """Verify that a control plane that grants less memory than requested refuses."""
        createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["240.0.0.0/4"], "mem_mib": 256}))
        _use_createos(monkeypatch, sandbox_memory_mb=1024)

        with pytest.raises(SandboxUnavailableError, match="granted 256 MiB"):
            run_code_in_sandbox("print('hi')")

    def test_missing_create_id_says_a_vm_may_be_orphaned(self, monkeypatch, createos):
        """Verify that a create response missing an id raises with a possible-orphan warning."""
        createos(_FakeCreateosApi(create_data={"egress": ["240.0.0.0/4"]}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError, match="may have been created"):
            run_code_in_sandbox("print('hi')")

    def test_failed_teardown_is_logged_but_does_not_mask_the_result(self, monkeypatch, createos):
        """Verify that a failed VM teardown does not prevent the execution result from being returned."""
        createos(_FakeCreateosApi(delete_status=500))
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print(1+1)")

        # The execution result survives; the leak is surfaced through the log.
        assert result.success
        assert result.stdout == "2\n"

    def test_api_key_is_redacted_when_the_server_reflects_it(self, monkeypatch, createos):
        """Verify that an API key echoed in the server's error body is redacted from the message."""
        # The endpoint echoes the credential back in its error body. Without
        # _redact this lands in the exception and then in tracebacks and logs.
        monkeypatch.setenv("CREATEOS_SANDBOX_API_KEY", "skp_supersecret")
        createos(_FakeCreateosApi(exec_status=403, exec_body="denied for key skp_supersecret"))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError) as excinfo:
            run_code_in_sandbox("print('hi')")

        message = str(excinfo.value)
        assert "skp_supersecret" not in message
        assert "***" in message, "the body reached the message but was not redacted"

    def test_api_key_is_redacted_from_the_policy_mismatch_path(self, monkeypatch, createos):
        """Verify that an API key embedded in a mismatched egress echo is redacted from the message."""
        # A different message-building path than the response-body one above.
        monkeypatch.setenv("CREATEOS_SANDBOX_API_KEY", "skp_supersecret")
        createos(
            _FakeCreateosApi(create_data={"id": "sb-test", "egress": ["skp_supersecret.evil.test"], "mem_mib": 4096})
        )
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError) as excinfo:
            run_code_in_sandbox("print('hi')")

        assert "skp_supersecret" not in str(excinfo.value)

    @pytest.mark.parametrize(
        ("timeout_seconds", "expected"),
        [(1, 3), (5, 10), (30, 45), (300, 315)],
    )
    def test_exec_deadline_scales_with_the_configured_timeout(self, timeout_seconds, expected):
        """Verify that the exec deadline scales with the configured sandbox timeout."""
        # A 1s timeout must not silently become a 16s wait.
        assert createos_module._exec_deadline(timeout_seconds) == expected


class TestCreateosEgressGrammarEdgeCases:
    """Stricter than the host parser on purpose; see _is_valid_egress_rule."""

    @pytest.mark.parametrize("rule", ["2001:db8::1", "::1", "2001:db8::/32", "*:443"])
    def test_forms_the_host_parser_mishandles_are_refused(self, rule):
        """Verify that a form the host's own parser mishandles is refused."""
        assert not _is_valid_egress_rule(rule)

    @pytest.mark.parametrize("rule", ["pypi.org:https", "pypi.org:0", "pypi.org:99999"])
    def test_bad_ports_are_refused(self, rule):
        """Verify that a rule with a bad port is refused."""
        # A bad port is the ONE input that makes the host fall back to allow-all.
        assert not _is_valid_egress_rule(rule)


class TestCreateosPolicyVerificationIsLoadBearing:
    """The fake normally echoes the request, so these drive it off that path.

    Without them the suite passes even if _assert_policy_applied is deleted.
    """

    def test_omitted_egress_is_treated_as_a_mismatch(self, monkeypatch, createos):
        """Verify that a create response with no egress field is treated as a policy mismatch."""
        # `egress` is omitempty on the control plane's response type, so a
        # server that silently dropped the policy returns no field at all.
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "mem_mib": 4096}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="did not store the requested egress"):
            run_code_in_sandbox("print('hi')")

        assert not any(p.endswith("/exec") for _, p in api.calls)

    def test_silently_widened_egress_is_caught(self, monkeypatch, createos):
        """Verify that a control plane that silently widens the egress policy is caught."""
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["0.0.0.0/0"], "mem_mib": 4096}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="did not store the requested egress"):
            run_code_in_sandbox("print('hi')")

        assert not any(p.endswith("/exec") for _, p in api.calls)

    def test_verification_runs_before_the_code_is_uploaded(self, monkeypatch, createos):
        """Verify that policy verification runs before the code is ever uploaded to the guest."""
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["*"], "mem_mib": 4096}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError):
            run_code_in_sandbox("print('hi')")

        # Not merely "did not exec" -- the code must never reach the guest.
        assert api.uploaded is None
        assert ("DELETE", "/v1/sandboxes/sb-test") in api.calls


class TestCreateosAutoPause:
    """The orphan backstop must outlive the execution it protects."""

    def test_auto_pause_exceeds_the_configured_timeout(self, monkeypatch, createos):
        """Verify that the requested auto-pause window exceeds the configured sandbox timeout."""
        # Regression: a backstop pinned at the 60s minimum paused healthy
        # executions, because the control plane touches the activity clock
        # only when /exec is accepted and a quiet program looks idle.
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_timeout_seconds=150)

        run_code_in_sandbox("print('hi')")

        assert api.bodies["create"]["auto_pause_after_seconds"] > 150

    @pytest.mark.parametrize("timeout_seconds", [1, 30, 300])
    def test_auto_pause_always_outlasts_the_execution_window(self, timeout_seconds):
        """Verify that the auto-pause window always outlasts the exec deadline."""
        assert createos_module._auto_pause_seconds(timeout_seconds) > createos_module._exec_deadline(timeout_seconds)

    def test_auto_pause_respects_the_control_plane_minimum(self):
        """Verify that the auto-pause window never drops below the control plane's 60s minimum."""
        # The API rejects anything below 60.
        assert createos_module._auto_pause_seconds(1) >= 60


# ---------------------------------------------------------------------------
# Streaming exec
# ---------------------------------------------------------------------------


class TestCreateosStreamingExec:
    """Verify that exec runs streamed and the NDJSON events are handled correctly."""

    def test_the_program_runs_streamed(self, monkeypatch, createos):
        """Streaming is the documented kill path; buffered mode has no timeout field."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print(1+1)")

        assert api.exec_commands, "no exec was issued"
        assert any(path.endswith("/exec") for _, path in api.calls)

    def test_heartbeats_do_not_reach_the_caller(self, monkeypatch, createos):
        """Verify that heartbeat events are filtered out and never appear in the result stdout."""
        createos(
            _FakeCreateosApi(
                exec_stream_lines=[{"hb": True}, {"stdout": "a"}, {"hb": True}, {"stdout": "b"}, {"exit_code": 0}]
            )
        )
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print('ab')")

        assert result.stdout == "ab"
        assert "hb" not in result.stdout

    def test_stdout_and_stderr_stay_separate(self, monkeypatch, createos):
        """Verify that interleaved stdout and stderr events stay separated in the result."""
        createos(
            _FakeCreateosApi(
                exec_stream_lines=[{"stdout": "out"}, {"stderr": "err"}, {"stdout": "put"}, {"exit_code": 3}]
            )
        )
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print('x')")

        assert result.stdout == "output"
        assert result.stderr == "err"
        assert result.exit_code == 3

    def test_an_unparsable_line_does_not_lose_the_execution(self, monkeypatch, createos):
        """Verify that an unparsable NDJSON line is skipped without losing the rest of the execution."""
        createos(_FakeCreateosApi(exec_stream_lines=[{"stdout": "kept"}, "not json", {"exit_code": 0}]))
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print('kept')")

        assert result.success
        assert result.stdout == "kept"

    def test_a_stream_without_a_terminal_frame_is_an_infrastructure_error(self, monkeypatch, createos):
        """No exit code was ever observed, so no outcome may be reported as success."""
        createos(_FakeCreateosApi(exec_stream_lines=[{"stdout": "partial"}]))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError, match="without an exit code"):
            run_code_in_sandbox("print('partial')")

    def test_an_agent_level_error_event_raises(self, monkeypatch, createos):
        """Verify that an agent-level error event raises SandboxExecutionError."""
        createos(_FakeCreateosApi(exec_stream_lines=[{"error": "no such command"}]))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError, match="could not start the guest command"):
            run_code_in_sandbox("print(1)")

    def test_the_deadline_stops_a_stream_that_never_ends(self, monkeypatch, createos):
        """Abandoning the stream is what kills the guest command."""
        createos(_FakeCreateosApi(exec_stream_lines=[{"stdout": "tick"}] * 50))
        _use_createos(monkeypatch, sandbox_timeout_seconds=1)
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda _timeout: -1.0)

        result = run_code_in_sandbox("while True: pass")

        assert result.exit_code == base_module._EXIT_CODE_TIMEOUT
        assert "timed out" in result.error_message()


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def _session(flow="flow-1", user="user-1"):
    """Return a SessionKey for the given flow and user, defaulting to a fixed pair."""
    return SessionKey(flow_id=flow, user_id=user)


def _session_identity_for(session=None, egress=None, memory_mb=192):
    """The cache/name key production derives, policy included.

    Mirrors _run_in_session: the identity binds the session to the egress and
    memory the guest was built under, so a test cannot assert a name that
    production would never ask for.
    """
    session = session or _session()
    egress = createos_module._CREATEOS_DENY_ALL_EGRESS if egress is None else egress
    return createos_module._session_identity(session.token(), egress, memory_mb)


def _session_name_for(**kwargs):
    """Return the guest name production would derive for the given session identity."""
    return createos_module._session_guest_name(_session_identity_for(**kwargs))


class TestCreateosSessions:
    """Verify that session mode controls whether a guest is reused, replaced, or destroyed."""

    def test_a_second_run_reuses_the_same_guest(self, monkeypatch, createos):
        """Verify that a second run of the same session reuses the existing guest."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("x = 1", session=_session())
        run_code_in_sandbox("print(x)", session=_session())

        assert api.created_ids == ["sb-one"]
        assert api.deleted_ids == []

    def test_two_users_of_one_flow_get_separate_guests(self, monkeypatch, createos):
        """Verify that two different users of the same flow get separate guests."""
        api = createos(_FakeCreateosApi(create_ids=["sb-alice", "sb-bob"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session(user="alice"))
        run_code_in_sandbox("print(1)", session=_session(user="bob"))

        assert api.created_ids == ["sb-alice", "sb-bob"]

    def test_sessions_off_destroys_the_guest_every_time(self, monkeypatch, createos):
        """Verify that with sessions off every run creates and destroys its own guest."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch)

        run_code_in_sandbox("print(1)", session=_session())
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-one", "sb-two"]
        assert api.deleted_ids == ["sb-one", "sb-two"]

    def test_a_guest_that_stopped_running_is_replaced(self, monkeypatch, createos):
        """A cached id may name a VM the control plane already reclaimed."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"], status_after_create="paused"))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session())
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-one", "sb-two"]
        assert "sb-one" in api.deleted_ids

    def test_an_idle_session_is_destroyed(self, monkeypatch, createos):
        """Verify that a session past its idle window is destroyed on the next call."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_session_idle_seconds=0)

        run_code_in_sandbox("print(1)", session=_session())
        run_code_in_sandbox("print(1)", session=_session())

        assert "sb-one" in api.deleted_ids
        assert api.created_ids == ["sb-one", "sb-two"]

    def test_a_failed_execution_drops_the_guest(self, monkeypatch, createos):
        """The guest state is unknown, so the next execution must not inherit it."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one"], exec_stream_lines=[{"stdout": "no terminal frame"}]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        with pytest.raises(SandboxExecutionError):
            run_code_in_sandbox("print(1)", session=_session())

        assert "sb-one" in api.deleted_ids

    def test_the_backstop_outlives_the_idle_window(self, monkeypatch, createos):
        """Otherwise the control plane pauses a session that is merely between runs."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_session_idle_seconds=3600)

        run_code_in_sandbox("print(1)", session=_session())

        assert api.bodies["create"]["auto_pause_after_seconds"] > 3600

    def test_shutdown_destroys_session_guests(self, monkeypatch, createos):
        """Verify that calling shutdown destroys every session guest the executor holds."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")
        executor = registry_module._instances["createos"]

        run_code_in_sandbox("print(1)", session=_session())
        assert api.deleted_ids == []

        executor.shutdown()

        assert api.deleted_ids == ["sb-one"]

    def test_a_fork_child_adopts_the_guest_instead_of_building_a_second_one(self, monkeypatch, createos):
        """The in-process map is a cache; the control plane is the registry.

        A fork gives the child an empty map. Without adoption it would create a
        second VM for the same (flow, user), so the state a flow sees would
        depend on which worker took the request and each worker would hold its
        own billed guest.
        """
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")
        executor = registry_module._instances["createos"]

        run_code_in_sandbox("print(1)", session=_session())
        executor.reset_after_fork()
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-one"]
        assert api.deleted_ids == []


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def _tarball(members: dict[str, bytes]) -> bytes:
    """Return a gzip tar archive built from the given member name-to-content mapping."""
    import io
    import tarfile

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class TestCreateosArtifacts:
    """Verify that artifact collection returns the files the guest wrote, and only when asked."""

    def test_files_the_guest_wrote_come_back(self, monkeypatch, createos):
        """Verify that files the guest wrote are returned in the result."""
        createos(_FakeCreateosApi(artifact_archive=_tarball({"./chart.png": b"PNG", "./out.csv": b"a,b\n"})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1)")

        assert {file.path for file in result.files} == {"chart.png", "out.csv"}
        assert {file.content for file in result.files} == {b"PNG", b"a,b\n"}

    def test_nothing_is_collected_when_the_operator_did_not_ask(self, monkeypatch, createos):
        """Verify that no files are collected and no download request is made without the setting."""
        api = createos(_FakeCreateosApi(artifact_archive=_tarball({"./chart.png": b"PNG"})))
        _use_createos(monkeypatch)

        result = run_code_in_sandbox("print(1)")

        assert result.files == ()
        assert not any(method == "GET" and path.endswith("/files") for method, path in api.calls)

    def test_the_artifact_directory_is_created_in_the_same_command(self, monkeypatch, createos):
        """One round trip, so the guest is ready before the program runs."""
        api = createos(_FakeCreateosApi(artifact_archive=_tarball({})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        run_code_in_sandbox("print(1)")

        program = api.exec_commands[0]["args"][1]
        assert program.startswith("rm -rf /workspace/artifacts; mkdir -p /workspace/artifacts")
        assert "python3 /workspace/.lf_run_" in program

    def test_a_reused_guest_does_not_hand_back_the_last_run_s_files(self, monkeypatch, createos):
        """Otherwise every execution inherits its predecessor's artifacts."""
        api = createos(_FakeCreateosApi(artifact_archive=_tarball({"./one.txt": b"1"})))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_collect_artifacts=True)

        run_code_in_sandbox("print(1)", session=_session())

        program = api.exec_commands[0]["args"][1]
        assert program.startswith("rm -rf /workspace/artifacts;")

    def test_a_missing_archive_does_not_fail_the_run(self, monkeypatch, createos):
        """Verify that a missing artifact archive does not fail the run and yields no files."""
        createos(_FakeCreateosApi(artifact_archive=None))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1+1)")

        assert result.success
        assert result.stdout == "2\n"
        assert result.files == ()

    def test_collection_stops_at_the_size_cap(self, monkeypatch, createos):
        """Verify that a file exceeding the configured artifact size cap is not returned."""
        createos(_FakeCreateosApi(artifact_archive=_tarball({"./big.bin": b"x" * 5000})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True, sandbox_max_artifact_bytes=100)

        result = run_code_in_sandbox("print(1)")

        assert result.files == ()

    def test_a_traversing_member_name_is_normalized(self, monkeypatch, createos):
        """Nothing is written to disk, but the reported name must not escape either."""
        createos(_FakeCreateosApi(artifact_archive=_tarball({"../../etc/passwd": b"root:x"})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1)")

        assert [file.path for file in result.files] == ["etc/passwd"]

    def test_an_absolute_member_name_is_normalized(self, monkeypatch, createos):
        """Verify that an absolute member path is normalized to a relative one."""
        createos(_FakeCreateosApi(artifact_archive=_tarball({"/etc/shadow": b"x"})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1)")

        assert [file.path for file in result.files] == ["etc/shadow"]


class TestCreateosCapabilities:
    """Verify that the createos backend reports its capabilities accurately."""

    def test_the_link_local_hole_is_declared(self):
        """D12: the host always ACCEPTs 169.254.0.0/16, whatever the egress policy says."""
        capabilities = createos_module._CreateosExecutor.capabilities()
        assert "169.254.0.0/16" in capabilities.egress_exceptions

    def test_sessions_and_artifacts_are_offered(self):
        """Verify that the reported capabilities include session and artifact support."""
        capabilities = createos_module._CreateosExecutor.capabilities()
        assert capabilities.supports_sessions
        assert capabilities.supports_artifacts


class TestCreateosTimeoutTaintsTheSession:
    """A timeout is not proof the guest command stopped, so the guest is not reusable."""

    def test_a_timed_out_session_guest_is_destroyed(self, monkeypatch, createos):
        """Verify that a session guest that timed out mid-execution is destroyed."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"], exec_stream_lines=[{"stdout": "tick"}] * 50))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_timeout_seconds=1)
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda _timeout: -1.0)

        result = run_code_in_sandbox("while True: pass", session=_session())

        assert result.exit_code == base_module._EXIT_CODE_TIMEOUT
        assert "sb-one" in api.deleted_ids

    def test_the_next_execution_gets_a_fresh_guest(self, monkeypatch, createos):
        """Verify that the execution after a timeout gets a fresh guest, not the tainted one."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"], exec_stream_lines=[{"stdout": "tick"}] * 50))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_timeout_seconds=1)
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda _timeout: -1.0)
        run_code_in_sandbox("while True: pass", session=_session())

        # Second execution completes normally, so it must not land on the
        # tainted guest.
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda timeout: timeout + 5)
        api.exec_stream_lines = None
        result = run_code_in_sandbox("print(1+1)", session=_session())

        assert result.success
        assert api.created_ids == ["sb-one", "sb-two"]

    def test_a_tainted_guest_is_dropped_even_when_the_destroy_fails(self, monkeypatch, createos):
        """Otherwise a lost DELETE would leave the mapping pointing at a running guest."""
        createos(
            _FakeCreateosApi(
                create_ids=["sb-one", "sb-two"],
                exec_stream_lines=[{"stdout": "tick"}] * 50,
                delete_status=500,
            )
        )
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_timeout_seconds=1)
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda _timeout: -1.0)
        run_code_in_sandbox("while True: pass", session=_session())

        executor = registry_module._instances["createos"]
        assert executor._sessions == {}

    def test_a_throwaway_timeout_still_destroys_its_guest(self, monkeypatch, createos):
        """Verify that a timeout on a throwaway (non-session) guest still destroys the VM."""
        api = createos(_FakeCreateosApi(exec_stream_lines=[{"stdout": "tick"}] * 50))
        _use_createos(monkeypatch, sandbox_timeout_seconds=1)
        monkeypatch.setattr(createos_module, "_exec_deadline", lambda _timeout: -1.0)

        result = run_code_in_sandbox("while True: pass")

        assert result.exit_code == base_module._EXIT_CODE_TIMEOUT
        assert "sb-test" in api.deleted_ids


class TestCreateosArtifactDownloadIsBounded:
    """The archive is guest-controlled, so the cap must bind before the bytes land."""

    def test_an_oversized_archive_is_refused_without_being_buffered(self, monkeypatch, createos):
        """The extracted-size budget cannot protect memory already spent on the download."""
        # Large on the wire, cheap to build: the client must stop pulling.
        huge = _tarball({"./pad.bin": b"x" * 4096}) + b"\0" * 200_000
        api = createos(_FakeCreateosApi(artifact_archive=huge))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True, sandbox_max_artifact_bytes=1024)

        result = run_code_in_sandbox("print(1)")

        assert result.success
        assert result.files == ()
        assert api.artifact_bytes_served <= 1024 + api.artifact_chunk_size

    def test_an_archive_inside_the_budget_still_arrives(self, monkeypatch, createos):
        """Verify that an archive within the size budget is still downloaded and returned."""
        createos(_FakeCreateosApi(artifact_archive=_tarball({"./small.txt": b"ok"})))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True, sandbox_max_artifact_bytes=1024 * 1024)

        result = run_code_in_sandbox("print(1)")

        assert [file.path for file in result.files] == ["small.txt"]

    def test_a_swarm_of_empty_members_is_capped(self, monkeypatch, createos):
        """Empty files never advance the byte budget, so only a member cap bounds them."""
        members = {f"./f{index}.txt": b"" for index in range(2000)}
        createos(_FakeCreateosApi(artifact_archive=_tarball(members)))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1)")

        assert result.success
        assert len(result.files) <= createos_module._CREATEOS_MAX_ARTIFACT_MEMBERS

    def test_the_member_cap_does_not_truncate_a_normal_archive(self, monkeypatch, createos):
        """Verify that the member cap does not truncate an archive well under the limit."""
        members = {f"./f{index}.txt": b"x" for index in range(10)}
        createos(_FakeCreateosApi(artifact_archive=_tarball(members)))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)

        result = run_code_in_sandbox("print(1)")

        assert len(result.files) == 10


class TestCreateosSessionsAreOwnedByTheControlPlane:
    """One guest per (flow, user), even across workers that share no memory."""

    @staticmethod
    def _second_worker(monkeypatch, api):
        """A second executor with its own empty maps, as a forked worker has."""
        executor = createos_module._CreateosExecutor()
        monkeypatch.setattr(
            executor,
            "_client",
            lambda timeout: httpx.Client(
                base_url="https://api.sb.createos.sh",
                timeout=timeout,
                transport=httpx.MockTransport(api.handler),
            ),
        )
        return executor

    def test_a_second_worker_adopts_rather_than_duplicates(self, monkeypatch, createos):
        """Verify that a second worker adopts the existing session guest instead of creating another."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")
        run_code_in_sandbox("print(1)", session=_session())

        other = self._second_worker(monkeypatch, api)
        monkeypatch.setitem(registry_module._instances, "createos", other)
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-one"]

    def test_the_guest_is_named_from_the_session_token(self, monkeypatch, createos):
        """Verify that the created guest's name is derived from the session token."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session())

        name = api.bodies["create"]["name"]
        assert name == _session_name_for()
        assert name.startswith(createos_module._CREATEOS_SESSION_NAME_PREFIX)

    def test_the_name_leaks_neither_flow_nor_user(self, monkeypatch, createos):
        """Verify that the guest name contains neither the flow id nor the user id."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=SessionKey(flow_id="secret-flow", user_id="secret-user"))

        name = api.bodies["create"]["name"]
        assert "secret-flow" not in name
        assert "secret-user" not in name

    def test_two_sessions_never_collide_on_a_name(self, monkeypatch, createos):
        """Verify that two different sessions never collide on the same guest name."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session(user="alice"))
        first = api.bodies["create"]["name"]
        run_code_in_sandbox("print(1)", session=_session(user="bob"))
        second = api.bodies["create"]["name"]

        assert first != second
        assert api.created_ids == ["sb-one", "sb-two"]

    def test_a_lost_create_race_adopts_the_winner(self, monkeypatch, createos):
        """Two workers can both find nothing, then both create; only one wins."""
        api = createos(_FakeCreateosApi(create_ids=["sb-winner", "sb-loser"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")
        loser = self._second_worker(monkeypatch, api)
        monkeypatch.setitem(registry_module._instances, "createos", loser)

        # Hide the winner from the lookup so the loser goes straight to create
        # and takes the 409 path, which is the race this guards.
        real_find = loser._find_session_vm
        calls = {"n": 0}

        def find_once(client, name):
            """Return None on the first lookup, then delegate to the real lookup."""
            calls["n"] += 1
            return None if calls["n"] == 1 else real_find(client, name)

        monkeypatch.setattr(loser, "_find_session_vm", find_once)
        api.names[_session_name_for()] = "sb-winner"

        run_code_in_sandbox("print(1)", session=_session())

        assert api.conflicts == 1
        assert loser._sessions[_session_identity_for()][0] == "sb-winner"
        assert "sb-loser" not in api.created_ids

    def test_an_unresolvable_conflict_fails_closed(self, monkeypatch, createos):
        """Never build a second guest for a session just because lookup failed."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow")
        executor = registry_module._instances["createos"]
        api.names[_session_name_for()] = "sb-ghost"
        monkeypatch.setattr(executor, "_find_session_vm", lambda _client, _name: None)

        with pytest.raises(SandboxExecutionError, match="cannot be found"):
            run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == []

    def test_a_throwaway_guest_is_not_named(self, monkeypatch, createos):
        """Only session guests are registered; a throwaway must not take a name."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print(1)")

        assert "name" not in api.bodies["create"]


class TestCreateosProgramFileIsPerExecution:
    """A shared session guest can hold two executions at once."""

    def test_two_executions_use_different_program_files(self, monkeypatch, createos):
        """Verify that two executions on the same session guest use different program file paths."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session())
        run_code_in_sandbox("print(2)", session=_session())

        paths = [command["args"][1] for command in api.exec_commands]
        assert len(paths) == 2
        assert paths[0] != paths[1]

    def test_the_program_file_is_removed_after_the_run(self, monkeypatch, createos):
        """A long-lived guest would otherwise keep one file per execution forever."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session())

        program = api.exec_commands[0]["args"][1]
        assert "rm -f /workspace/.lf_run_" in program

    def test_the_exit_status_survives_the_cleanup(self, monkeypatch, createos):
        """Verify that the program's exit status survives the program-file cleanup step."""
        createos(_FakeCreateosApi(exec_result={"stdout": "", "stderr": "boom", "exit_code": 42}))
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        result = run_code_in_sandbox("raise SystemExit(42)", session=_session())

        assert result.exit_code == 42

    def test_the_generated_path_cannot_carry_shell_syntax(self):
        """It is interpolated into a shell line, so it must be hex and nothing else."""
        import re as _re

        for _ in range(50):
            path = createos_module._guest_code_path()
            assert _re.fullmatch(r"/workspace/\.lf_run_[0-9a-f]{32}\.py", path), path

    def test_the_upload_and_the_command_agree(self, monkeypatch, createos):
        """Verify that the path the code is uploaded to matches the path the exec command reads."""
        api = createos(_FakeCreateosApi())
        _use_createos(monkeypatch)

        run_code_in_sandbox("print(1)")

        program = api.exec_commands[0]["args"][1]
        uploaded_path = api.upload_paths[0]
        assert uploaded_path in program

    def test_the_name_fits_the_control_plane_limit(self):
        """The API rejects a name over 22 characters with 400; found live, not by a mock."""
        name = createos_module._session_guest_name("f" * 64)
        assert len(name) <= createos_module._CREATEOS_SESSION_NAME_MAX
        assert len(name) == createos_module._CREATEOS_SESSION_NAME_MAX

    def test_the_name_is_still_unique_per_session(self):
        """Verify that the guest name is still unique per session even after length truncation."""
        first = createos_module._session_guest_name(SessionKey(flow_id="a", user_id="b").token())
        second = createos_module._session_guest_name(SessionKey(flow_id="a", user_id="c").token())
        assert first != second


class TestCreateosIdleReaperSparesRunningGuests:
    """A reap triggered by one session must never destroy another mid-execution.

    The reaper judges a stored timestamp, and that timestamp cannot advance
    while its session is busy: it is written on completion. An execution that
    starts inside the idle window and runs past the deadline is therefore
    indistinguishable from an abandoned one by timestamp alone.
    """

    def test_a_running_session_is_not_reaped_by_another_session(self, monkeypatch, createos):
        """Verify that a session mid-execution is not reaped by the idle reaper of another session."""
        api = createos(_FakeCreateosApi(create_ids=["sb-busy", "sb-other", "sb-third"]))
        # Idle window of zero makes every entry look stale the moment it exists,
        # which is the same condition a long execution reaches naturally.
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_session_idle_seconds=0)
        executor = registry_module._instances["createos"]

        busy = _session(user="busy")
        started = threading.Event()
        release = threading.Event()
        real_exec = executor._upload_and_exec

        def blocking_exec(client, sandbox_id, code, settings):
            """Block the busy session's exec until released, then delegate to the real exec."""
            if sandbox_id == "sb-busy":
                started.set()
                # Hold the guest "mid-execution" while the other session reaps.
                # Raised rather than asserted: this runs on the worker thread,
                # where an AssertionError would be swallowed. The caller
                # re-raises whatever lands in `failure`.
                if not release.wait(timeout=10):
                    msg = "the reaping thread never finished"
                    raise RuntimeError(msg)
            return real_exec(client, sandbox_id, code, settings)

        monkeypatch.setattr(executor, "_upload_and_exec", blocking_exec)

        # The worker's outcome is captured and asserted on the main thread.
        # An AssertionError raised inside a thread never reaches pytest, and a
        # swallowed failure here would surface as the reaper assertion below
        # failing for the wrong reason.
        failure: list[BaseException] = []

        def busy_run():
            """Run the busy session's execution and capture any exception it raises."""
            try:
                run_code_in_sandbox("print(1)", session=busy)
            except BaseException as exc:  # re-raised on the main thread
                failure.append(exc)

        worker = threading.Thread(target=busy_run)
        worker.start()
        try:
            assert started.wait(timeout=10), "the busy session never started executing"
            # A different session executes, which runs the idle reaper on entry.
            run_code_in_sandbox("print(1)", session=_session(user="other"))
            assert "sb-busy" not in api.deleted_ids, "the reaper destroyed a guest that was executing"
        finally:
            release.set()
            worker.join(timeout=10)
        assert not worker.is_alive(), "the busy session never finished"
        if failure:
            raise failure[0]

    def test_an_idle_session_is_still_reaped(self, monkeypatch, createos):
        """The guard must not disable reaping for sessions that really are idle."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two", "sb-three"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_session_idle_seconds=0)

        run_code_in_sandbox("print(1)", session=_session(user="idle"))
        run_code_in_sandbox("print(1)", session=_session(user="active"))

        assert "sb-one" in api.deleted_ids


class TestCreateosSessionGuestIsBoundToItsPolicy:
    """A guest is only adopted by a process asking for the policy it was built with.

    Create-time verification is the only policy check there is, and a reused
    guest never reaches it. The control plane cannot be asked what policy a
    running guest has -- GET /v1/sandboxes/{id} omits egress entirely and
    GET /v1/sandboxes/{id}/egress answers [] even for a sandbox created with
    rules -- so the identity has to carry it.
    """

    def test_tightening_the_network_policy_does_not_reuse_the_open_guest(self, monkeypatch, createos):
        """Verify that tightening the network policy to deny-all does not reuse the open guest."""
        api = createos(_FakeCreateosApi(create_ids=["sb-open", "sb-closed"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_allow_network=True)
        run_code_in_sandbox("print(1)", session=_session())
        assert api.created_ids == ["sb-open"]

        # The operator tightens to deny-all and the process restarts inside the
        # window where the old guest is still registered under its name.
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_allow_network=False)
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-open", "sb-closed"], "the guest built under open egress was reused"

    def test_narrowing_the_allowlist_does_not_reuse_the_wider_guest(self, monkeypatch, createos):
        """Verify that narrowing the domain allowlist does not reuse the wider guest."""
        api = createos(_FakeCreateosApi(create_ids=["sb-wide", "sb-narrow"]))
        _use_createos(
            monkeypatch,
            sandbox_session_mode="flow",
            sandbox_allow_network=True,
            sandbox_allowed_domains=["pypi.org", "example.com"],
        )
        run_code_in_sandbox("print(1)", session=_session())

        _use_createos(
            monkeypatch,
            sandbox_session_mode="flow",
            sandbox_allow_network=True,
            sandbox_allowed_domains=["pypi.org"],
        )
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-wide", "sb-narrow"]

    def test_raising_the_memory_floor_does_not_reuse_the_smaller_guest(self, monkeypatch, createos):
        """Verify that raising the memory floor does not reuse the smaller guest."""
        api = createos(_FakeCreateosApi(create_ids=["sb-small", "sb-big"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_memory_mb=192)
        run_code_in_sandbox("print(1)", session=_session())

        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_memory_mb=8192)
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-small", "sb-big"]

    def test_an_unchanged_policy_still_reuses_the_guest(self, monkeypatch, createos):
        """The binding must not defeat reuse, which is the whole point of sessions."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(monkeypatch, sandbox_session_mode="flow", sandbox_allow_network=True)

        run_code_in_sandbox("x = 1", session=_session())
        run_code_in_sandbox("print(x)", session=_session())

        assert api.created_ids == ["sb-one"]

    def test_the_allowlist_order_is_not_a_policy_change(self, monkeypatch, createos):
        """Verify that reordering the same domain allowlist does not count as a policy change."""
        api = createos(_FakeCreateosApi(create_ids=["sb-one", "sb-two"]))
        _use_createos(
            monkeypatch,
            sandbox_session_mode="flow",
            sandbox_allow_network=True,
            sandbox_allowed_domains=["pypi.org", "example.com"],
        )
        run_code_in_sandbox("print(1)", session=_session())

        _use_createos(
            monkeypatch,
            sandbox_session_mode="flow",
            sandbox_allow_network=True,
            sandbox_allowed_domains=["example.com", "pypi.org"],
        )
        run_code_in_sandbox("print(1)", session=_session())

        assert api.created_ids == ["sb-one"]

    def test_the_policy_bound_name_still_fits_the_control_plane_limit(self):
        """Verify that a policy-bound guest name still fits the control plane's name length limit."""
        identity = createos_module._session_identity(SessionKey(flow_id="a", user_id="b").token(), ("0.0.0.0/32",), 192)
        name = createos_module._session_guest_name(identity)
        assert len(name) == createos_module._CREATEOS_SESSION_NAME_MAX


class TestCreateosArtifactCollectionIsNeverFatal:
    """A guest-built archive is hostile input; a malformed one must not raise.

    tarfile reports corruption outside the OSError tree (TarError derives from
    Exception, and a truncated gzip surfaces as EOFError), so neither is caught
    by an OSError-only handler.
    """

    @staticmethod
    def _archive_returning(monkeypatch, executor, blob):
        """Patch the executor's archive download to return the given blob instead of fetching."""
        monkeypatch.setattr(executor, "_download_artifact_archive", lambda *_args, **_kwargs: blob)

    def test_a_corrupt_archive_returns_the_real_result(self, monkeypatch, createos):
        """Verify that a corrupt archive does not fail the run and yields the real exec result."""
        createos(_FakeCreateosApi(exec_result={"stdout": "real output", "stderr": "", "exit_code": 0}))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)
        executor = registry_module._instances["createos"]
        self._archive_returning(monkeypatch, executor, b"this is not a tar archive")

        result = run_code_in_sandbox("print('real output')")

        assert result.exit_code == 0
        assert result.stdout == "real output"
        assert result.files == ()

    def test_a_truncated_archive_returns_the_real_result(self, monkeypatch, createos):
        """Verify that a truncated gzip archive does not fail the run and yields the real exec result."""
        createos(_FakeCreateosApi(exec_result={"stdout": "real output", "stderr": "", "exit_code": 0}))
        _use_createos(monkeypatch, sandbox_collect_artifacts=True)
        executor = registry_module._instances["createos"]

        whole = io.BytesIO()
        with tarfile.open(fileobj=whole, mode="w:gz") as tar:
            info = tarfile.TarInfo("chart.png")
            payload = b"x" * 4096
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        self._archive_returning(monkeypatch, executor, whole.getvalue()[: len(whole.getvalue()) // 2])

        result = run_code_in_sandbox("print('real output')")

        assert result.exit_code == 0
        assert result.stdout == "real output"
        assert result.files == ()


class TestUntrustedControlPlaneValues:
    """A response this module cannot read is a failed check, not a crash."""

    @pytest.mark.parametrize("granted", ["not-a-number", ["4096"], {"mib": 4096}])
    def test_an_unreadable_memory_grant_refuses_and_destroys_the_vm(self, monkeypatch, createos, granted):
        """int(granted) on a non-numeric value raises outside the SandboxUnavailableError tree.

        The caller's teardown handler catches only that type, so the raw
        TypeError or ValueError skips it: the VM is never destroyed and the
        component receives a traceback instead of a mapped sandbox error.
        """
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["240.0.0.0/4"], "mem_mib": granted}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="unreadable memory grant"):
            run_code_in_sandbox("print('hi')")

        assert "sb-test" in api.deleted_ids, "the VM leaked when the grant could not be read"
        assert not any(p.endswith("/exec") for _, p in api.calls), "code ran despite a failed check"

    def test_an_unreadable_exit_code_is_a_sandbox_error(self, monkeypatch, createos):
        """The exit_code frame comes from the guest agent stream, so it is guest-controlled.

        An unmapped ValueError escapes the SandboxExecutionError tree, and
        _run_in_session drops a guest only for that type -- so the session
        mapping would keep pointing at a guest whose program state is unknown
        and the next execution would reuse it.
        """
        createos(_FakeCreateosApi(exec_result={"stdout": "", "stderr": "", "exit_code": "done"}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxExecutionError, match="unreadable exit code"):
            run_code_in_sandbox("print('hi')")

    def test_a_readable_grant_still_passes(self, monkeypatch, createos):
        """The guard must not reject the numeric strings a JSON API legitimately returns."""
        createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": ["240.0.0.0/4"], "mem_mib": "4096"}))
        _use_createos(monkeypatch)

        assert run_code_in_sandbox("print(1+1)").success


class TestCatalogIsFetchedOutsideTheMutex:
    """The catalog request must not stall unrelated session work."""

    def test_a_slow_catalog_fetch_does_not_block_session_bookkeeping(self, monkeypatch, createos):
        """`self._lock` guards every session operation, and the fetch has a 60s budget.

        Holding it across the request serializes unrelated flows behind a
        control-plane call that has nothing to do with them.
        """
        executor = createos(_FakeCreateosApi()) and registry_module._instances["createos"]
        executor._shapes = None
        inside = threading.Event()
        release = threading.Event()

        real_client = executor._client

        def slow_client(timeout):
            """Signal that the fetch has started, then block until released."""
            inside.set()
            release.wait(timeout=5)
            return real_client(timeout)

        monkeypatch.setattr(executor, "_client", slow_client)

        fetching = threading.Thread(target=executor._catalog, daemon=True)
        fetching.start()
        assert inside.wait(timeout=5), "the catalog fetch never started"

        touched = threading.Event()
        threading.Thread(target=lambda: (executor._touch_session("t", "sb-x"), touched.set()), daemon=True).start()
        assert touched.wait(timeout=2), "a session operation blocked behind the catalog fetch"

        release.set()
        fetching.join(timeout=5)

    def test_an_unreadable_shape_entry_is_skipped_not_raised(self, monkeypatch, createos):
        """A control-plane value that cannot be read must cost only itself."""
        api = _FakeCreateosApi()
        api.shapes = [
            {"id": "s-broken", "vcpu": 1, "mem_mib": "many"},
            {"id": "s-2vcpu-4gb", "vcpu": 2, "mem_mib": 4096},
        ]
        createos(api)
        _use_createos(monkeypatch)

        assert run_code_in_sandbox("print(1+1)").success


class TestEgressEchoIsUntrusted:
    """A create response this code cannot read is a failed check, not a crash."""

    @pytest.mark.parametrize("echoed", [5, 3.5, True])
    def test_a_non_iterable_egress_echo_refuses_and_destroys_the_vm(self, monkeypatch, createos, echoed):
        """sorted(map(str, echoed)) raises TypeError outside the mapped error tree.

        That skips the caller's teardown handler, so the VM leaks and the
        component receives a raw traceback instead of a policy refusal.
        """
        api = createos(_FakeCreateosApi(create_data={"id": "sb-test", "egress": echoed, "mem_mib": 4096}))
        _use_createos(monkeypatch)

        with pytest.raises(SandboxUnavailableError, match="did not store the requested egress"):
            run_code_in_sandbox("print('hi')")

        assert "sb-test" in api.deleted_ids, "the VM leaked on an unreadable egress echo"
        assert not any(p.endswith("/exec") for _, p in api.calls), "code ran despite a failed check"


class TestResolverRuleIsNotSentTwice:
    """A duplicate rule turns into a policy mismatch the operator cannot act on."""

    def test_an_operator_supplied_resolver_is_not_duplicated(self, monkeypatch, createos):
        """_assert_policy_applied compares sorted lists.

        A control plane that stores a deduplicated set then produces a length
        mismatch, and the run is refused with a message about a policy the
        operator did in fact request.
        """
        api = createos(_FakeCreateosApi())
        _use_createos(
            monkeypatch,
            sandbox_allow_network=True,
            sandbox_allowed_domains=["api.example.com", createos_module._CREATEOS_DNS_EGRESS],
        )

        assert run_code_in_sandbox("print(1+1)").success

        sent = api.bodies["create"]["egress"]
        assert sent.count(createos_module._CREATEOS_DNS_EGRESS) == 1
        assert len(sent) == len(set(sent))


class TestSessionLocksDoNotGrow:
    """The lock map has no reaper of its own, so it must be pruned with the session."""

    def test_dropping_a_session_drops_its_lock(self, monkeypatch, createos):
        """The identity encodes the policy, so a leak here is one entry per policy change.

        _sessions is bounded by the idle reaper. _session_locks was not bounded
        by anything.
        """
        executor = createos(_FakeCreateosApi()) and registry_module._instances["createos"]
        _use_createos(monkeypatch, sandbox_session_mode="flow")

        run_code_in_sandbox("print(1)", session=_session(user="a"))
        assert executor._session_locks, "the session never took a lock"

        with executor._client(5) as client:
            for token in list(executor._sessions):
                executor._drop_session(client, token)

        assert not executor._session_locks, "the per-session lock outlived its session"


class TestSessionErrorHandlingCoversBothErrorClasses:
    """Guards the hierarchy the session handler relies on."""

    def test_sandbox_unavailable_is_caught_by_the_execution_handler(self):
        """_run_in_session catches SandboxExecutionError to drop a tainted guest.

        That only covers a control-plane 4xx because SandboxUnavailableError
        derives from it. Breaking that relationship would silently stop the
        guest from being dropped, so it is asserted rather than assumed.
        """
        assert issubclass(SandboxUnavailableError, SandboxExecutionError)
