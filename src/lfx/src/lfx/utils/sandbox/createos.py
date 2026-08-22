"""The ``createos`` backend: one remote Firecracker microVM per execution.

The microVM runs on the CreateOS control plane instead of the Langflow host,
so no KVM/HVF device is needed locally. Requires ``CREATEOS_SANDBOX_API_KEY``.

This is vendor code. It is deliberately confined to this one module so the
registry, the shared primitives, and the ``exec-sandbox`` backend stay free of
any vendor reference.

That confinement matters beyond tidiness: this backend calls
``api.sb.createos.sh`` directly, which is exactly the shape a protocol-first
upstream design rules out. This module is meant to prove the vendor-neutral
protocol is implementable and to stay a reference for what an upstream
``remote`` backend needs -- it must not be proposed upstream as-is.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import ipaddress
import json
import os
import posixpath
import re
import tarfile
import threading
import time
import uuid
from dataclasses import replace

import httpx

from lfx.log.logger import logger
from lfx.utils.sandbox.base import (
    _EXIT_CODE_TIMEOUT,
    Capabilities,
    SandboxExecutionError,
    SandboxFile,
    SandboxResult,
    SandboxUnavailableError,
    SessionKey,
    _sandbox_settings,
    _SandboxSettings,
)
from lfx.utils.sandbox.registry import register_sandbox_backend

SANDBOX_BACKEND_CREATEOS = "createos"

# --------------------------------------------------------------------------
# CreateOS backend
# --------------------------------------------------------------------------

_CREATEOS_DEFAULT_BASE_URL = "https://api.sb.createos.sh"
_CREATEOS_DEFAULT_ROOTFS = "devbox:1"
# Each execution uploads its program under its own name. A fixed path was
# enough while one guest served one execution, but a session guest is now
# shared across workers (see _acquire_session_vm), so two executions can be in
# flight on one guest and a fixed path would let each overwrite the other's
# program. The suffix is hex from uuid4, so nothing a caller supplies reaches
# the shell line built from it.
_CREATEOS_GUEST_CODE_DIR = "/workspace"
_CREATEOS_GUEST_CODE_PREFIX = ".lf_run_"
_CREATEOS_GUEST_PYTHON = "python3"

# The program is launched through a shell so the artifact directory can be
# created in the same round trip. Every piece of the command line is a constant
# in this module -- no caller-supplied value is ever interpolated into it.
_CREATEOS_GUEST_SHELL = "/bin/sh"

# Where guest code writes files it wants the flow to receive. A convention
# rather than a mount: the guest may write anywhere, and only this directory is
# read back.
_CREATEOS_GUEST_ARTIFACT_DIR = "/workspace/artifacts"
_CREATEOS_GUEST_ARTIFACT_ARCHIVE = "/tmp/lf-artifacts.tar.gz"  # noqa: S108 - guest path, not a host path

# Collect into a tarball because the API downloads one path per request, and
# only the guest knows which files the program wrote. Failure is silent on
# purpose: an empty or missing directory must not turn into an exec error, so
# the archive is created either way and an empty one collects nothing.
_CREATEOS_ARTIFACT_TAR_COMMAND = (
    f"mkdir -p {_CREATEOS_GUEST_ARTIFACT_DIR} && "
    f"tar -czf {_CREATEOS_GUEST_ARTIFACT_ARCHIVE} -C {_CREATEOS_GUEST_ARTIFACT_DIR} . 2>/dev/null || true"
)

# A session guest is named after its session token so the control plane can act
# as the registry: a sandbox name is unique per user among non-terminal
# sandboxes, so create-with-name is a compare-and-swap between workers. The
# token is already a truncated hash, so the name reveals no flow or user id.
#
# The control plane caps a name at 22 characters and rejects a longer one with
# 400 -- found by running this against the live API, not by any local test. The
# prefix plus the token slice must therefore total exactly that. 19 hex
# characters leave 76 bits, so two sessions colliding is not a real risk.
_CREATEOS_SESSION_NAME_MAX = 22
_CREATEOS_SESSION_NAME_PREFIX = "lf-"
_CREATEOS_SESSION_TOKEN_CHARS = _CREATEOS_SESSION_NAME_MAX - len(_CREATEOS_SESSION_NAME_PREFIX)

# Bounds on the name lookup. The list endpoint has no name filter, so adoption
# pages and matches client-side; a missed match only costs a 409 and a retry,
# while an unbounded loop over a control-plane list does not.
_CREATEOS_SESSION_LOOKUP_PAGE_SIZE = 500
_CREATEOS_SESSION_LOOKUP_PAGES = 4


# Upper bound on entries read from a guest-produced archive. The byte budget
# does not bound this on its own: empty members cost nothing against it while
# still costing a header parse and an object each.
_CREATEOS_MAX_ARTIFACT_MEMBERS = 256

# Default VM size. Langflow's sandbox_memory_mb default is 192, which is sized
# for exec-sandbox's local QEMU guest and is far too small for a fresh CreateOS
# guest importing numpy or pandas. A CreateOS shape also fixes vCPU, which
# sandbox_memory_mb cannot express at all, so the default is a named shape and
# sandbox_memory_mb only raises the floor. Override with
# CREATEOS_SANDBOX_SHAPE.
_CREATEOS_DEFAULT_SHAPE = "s-2vcpu-4gb"
_CREATEOS_DEFAULT_SHAPE_MEMORY_MIB = 4096

# CreateOS egress is allowlist-only and has no deny-all token: an empty list,
# null, and ["*"] all mean allow-all. "No network" therefore has to be spelled
# as a rule set that parses cleanly but matches nothing, so the host installs
# the iptables chain and its default DROP applies to everything else.
# 240.0.0.0/4 is IANA-reserved and unroutable. It is a constant we control, so
# it can never reach the host's parse-failure path -- which falls back to
# allow-all rather than refusing.
_CREATEOS_DENY_ALL_EGRESS = ("240.0.0.0/4",)

# Egress is enforced on destination address, so a domain allowlist is inert
# unless the guest may also reach a resolver. Appended to any non-empty
# allowlist; it is a destination the operator did not ask for, hence the
# explicit constant rather than a silent addition buried in a f-string.
#
# Consequence worth knowing, verified against a live sandbox: the resolver
# answers for ANY name, so a guest can still resolve non-allowlisted domains
# (it just cannot connect to them). exec-sandbox filters DNS inside the guest
# and would refuse the lookup itself, so the two backends differ here: under
# createos, DNS remains a low-bandwidth exfiltration channel whenever
# sandbox_allowed_domains is non-empty. Reachability is enforced; name
# resolution is not.
_CREATEOS_DNS_EGRESS = "1.1.1.1:53"

# Control-plane calls (create, destroy, catalog, whoami) are not the user's
# code, so they get a fixed budget. Only the exec call is bounded by
# sandbox_timeout_seconds.
_CREATEOS_CONTROL_TIMEOUT_SECONDS = 60

# Connect and pool-acquire budget. Kept short and separate from the read budget
# because httpx applies its timeout per phase, not per request.
_CREATEOS_CONNECT_TIMEOUT_SECONDS = 10

# Upper bound on what is added to the guest wall clock before the HTTP read is
# abandoned, covering request transport and result marshalling. The VM teardown
# is what actually stops a runaway execution, so this only decides when we stop
# waiting. Capped against the configured timeout in _exec_deadline so a short
# sandbox_timeout_seconds is not silently multiplied.
_CREATEOS_EXEC_GRACE_SECONDS = 15
_CREATEOS_MIN_EXEC_GRACE_SECONDS = 2

# Reclaim window for a VM this process failed to destroy.
#
# It MUST outlast the execution it is protecting. The control plane touches a
# sandbox's activity clock once, when /exec is accepted, and its idle sweeper
# then pauses any sandbox whose window expired and whose bandwidth barely
# moved. A quiet program (``time.sleep(95)``) therefore looks idle, so a
# backstop pinned at the 60s minimum PAUSES a perfectly healthy execution and
# the caller sees a timeout. Verified against a live sandbox.
#
# Sized above the whole execution window -- upload, plus the exec deadline --
# so the backstop can only ever catch a VM this process failed to destroy.
_CREATEOS_AUTO_PAUSE_MIN_SECONDS = 60
_CREATEOS_AUTO_PAUSE_MARGIN_SECONDS = 120


def _auto_pause_seconds(timeout_seconds: int) -> int:
    """Idle window for the orphan backstop, always longer than one execution."""
    return max(_CREATEOS_AUTO_PAUSE_MIN_SECONDS, timeout_seconds + _CREATEOS_AUTO_PAUSE_MARGIN_SECONDS)


def _exec_deadline(timeout_seconds: int) -> float:
    """HTTP read deadline for one exec call.

    ``sandbox_timeout_seconds`` is documented as the wall-clock limit, and the
    exec endpoint has no server-side timeout, so this deadline IS the
    enforcement. The margin therefore only has to cover transport, and it
    scales with the configured value: 1s yields 3s rather than 16s, while the
    30s default still gets the full 15s of slack.
    """
    return timeout_seconds + min(_CREATEOS_EXEC_GRACE_SECONDS, max(_CREATEOS_MIN_EXEC_GRACE_SECONDS, timeout_seconds))


# Hostname / wildcard-subdomain form from the documented egress grammar.
_CREATEOS_HOSTNAME_RE = re.compile(r"^(?:\*\.)?(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")

_MAX_PORT = 65535


class _SessionNameTakenError(Exception):
    """Another worker already registered this session's guest with the control plane."""


def _guest_code_path() -> str:
    """A path for one execution's program, unique within the guest."""
    return f"{_CREATEOS_GUEST_CODE_DIR}/{_CREATEOS_GUEST_CODE_PREFIX}{uuid.uuid4().hex}.py"


def _session_identity(token: str, egress: tuple[str, ...], memory_mb: int) -> str:
    """Bind a session to the policy its guest must have been created under.

    The create-time check (:meth:`_CreateosExecutor._assert_policy_applied`) is
    the only place a guest's policy is ever verified, and a REUSED guest never
    reaches it. A session guest deliberately outlives the process -- it carries
    a stable name so another worker, or the same worker after a restart, adopts
    it instead of building a second VM. That is what makes stale policy
    reachable: tighten ``LANGFLOW_SANDBOX_ALLOW_NETWORK`` (or narrow the
    allowlist, or raise the memory floor) and restart inside the auto-pause
    window, and the old guest -- created under the OLD, looser policy -- is
    still sitting there under the name the new process looks up.

    Re-verifying on adoption is not an option: ``GET /v1/sandboxes/{id}`` omits
    ``egress`` entirely, and ``GET /v1/sandboxes/{id}/egress`` answers with an
    empty list even for a sandbox created with rules (checked against the live
    control plane, both while starting and while running). There is no way to
    ask what policy a guest actually has.

    So the policy is folded into the identity instead. A guest is only ever
    adopted by a process asking for the same policy that guest was created
    with, because any other policy simply derives a different name and misses
    it. Changing a setting orphans the old guest rather than inheriting it; the
    idle reaper and the control plane's auto-pause collect it. Session state
    does not survive that, which is correct -- the state belongs to a guest the
    operator has just declared unacceptable.
    """
    # Sorted so an allowlist written in a different order is the same policy,
    # and unit-separated so ("a", "b") cannot collide with ("a\x1fb",).
    policy = "\x1f".join((*sorted(egress), str(memory_mb)))
    return hashlib.sha256(f"{token}\x00{policy}".encode()).hexdigest()


def _session_guest_name(identity: str) -> str:
    """The control-plane name that identifies one session's guest."""
    return f"{_CREATEOS_SESSION_NAME_PREFIX}{identity[:_CREATEOS_SESSION_TOKEN_CHARS]}"


def _safe_artifact_name(name: str) -> str:
    """Normalize a tar member name for reporting.

    Artifacts are only ever held in memory, so this cannot prevent a write
    outside a directory -- there is no write. It exists so a hostile member
    name cannot make a downstream consumer (a log line, a filename a user is
    shown, a component that saves the file later) treat it as an absolute or
    escaping path.
    """
    cleaned = posixpath.normpath(name).lstrip("/")
    parts = [part for part in cleaned.split("/") if part not in ("", ".", "..")]
    return "/".join(parts) or "artifact"


def _is_valid_egress_rule(rule: str) -> bool:
    """Whether ``rule`` matches CreateOS's documented egress grammar.

    Validated here because the host FAILS OPEN on a rule set its parser
    rejects: it logs a warning, installs no chain at all, and the sandbox gets
    the open internet (``fc/internal/hosts/vm/egress.go:88-92``).

    Read that parser to see which inputs actually trigger it: only a
    non-numeric or out-of-range PORT returns false. An unrecognised host falls
    through to the domain list and simply never matches, which fails closed.
    So the dangerous input is a plausible typo like ``pypi.org:https`` --
    exactly the shape this function exists to reject.

    Deliberately stricter than the host parser in two places, both verified
    against it:

    * IPv6 is refused. The parser splits on the last colon and notes that IPv6
      is "not handled here", so ``2001:db8::1`` degrades into a domain rule
      that can never match. Refusing beats silently doing nothing.
    * ``*:port`` is refused. Bare ``*`` is matched before the port split, so
      ``*:443`` also degrades into an unmatchable domain rule rather than
      meaning "all hosts on 443".

    Accepted: ``*``, ``host``, ``*.host``, ``ipv4``, ``cidr``, each optionally
    suffixed with ``:port``.
    """
    if rule == "*":
        return True
    host, separator, port = rule.rpartition(":")
    if not separator:
        host = rule
    elif not port.isdigit() or not 0 < int(port) <= _MAX_PORT:
        return False
    if not host:
        return False
    with contextlib.suppress(ValueError):
        ipaddress.IPv4Network(host, strict=False)
        return True
    return bool(_CREATEOS_HOSTNAME_RE.match(host))


class _CreateosExecutor:
    """Runs one execution in a throwaway CreateOS Firecracker microVM.

    One VM per execution, matching the exec-sandbox backend's blast radius:
    nothing survives between two runs of a component. The VM is always
    destroyed, and that teardown is also how the wall-clock timeout is
    enforced -- the exec request is abandoned at the deadline and destroying
    the VM kills whatever the guest was still running.

    Unlike exec-sandbox there is no TCG question to gate on. A CreateOS
    sandbox is a Firecracker microVM with its own kernel, so the hardware
    boundary is structural rather than a host property that has to be probed.
    Preflight therefore checks the credential, not the hypervisor.
    """

    name = SANDBOX_BACKEND_CREATEOS

    @staticmethod
    def capabilities() -> Capabilities:
        """What CreateOS enforces, including the hole it cannot close.

        ``supports_deny_all_egress`` is true by way of a spelling rather than a
        first-class token: CreateOS treats an empty list, null, and ``["*"]``
        all as allow-all, so "no network" is expressed as a reserved CIDR that
        parses cleanly and matches nothing (see ``_CREATEOS_DENY_ALL_EGRESS``).

        ``egress_exceptions`` names the traffic that policy cannot reach:
        ``fc/internal/hosts/vm/egress.go`` unconditionally ACCEPTs the guest's
        own /31, all of 169.254.0.0/16, and the agent time servers before the
        final DROP, so link-local is always reachable whatever the policy says.
        Verified live under the default deny-all policy: a guest reached
        ``169.254.169.254:80`` and got HTTP 200, while a public address on the
        same policy was blocked. That range carries the VM metadata service,
        and ``fc/internal/proto/disks.go`` publishes attached-disk S3
        credentials to it in plaintext -- Langflow attaches no disks today, so
        nothing Langflow places in a sandbox is exposed through this path, but
        a future integration that does attach one would need to know this
        first. Declared here rather than left for an operator to discover.
        """
        return Capabilities(
            isolation="hardware-virtualized",
            supports_deny_all_egress=True,
            supports_domain_allowlist=True,
            supports_sessions=True,
            supports_artifacts=True,
            egress_exceptions=("169.254.0.0/16",),
        )

    def shutdown(self) -> None:
        """Destroy any session guests this process is still holding.

        A throwaway run destroys its own VM in a ``finally``, so only sessions
        can outlive an execution. They must not outlive the process.
        """
        self._destroy_all_sessions()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._shapes: tuple[tuple[int, str], ...] | None = None
        self._preflighted = False
        # session token -> (sandbox id, monotonic time of last use)
        self._sessions: dict[str, tuple[str, float]] = {}
        # One lock per session so two executions of the same session cannot
        # share a guest concurrently. Keyed the same way as _sessions.
        self._session_locks: dict[str, threading.Lock] = {}

    # -- configuration ----------------------------------------------------

    @staticmethod
    def _api_key() -> str:
        key = os.environ.get("CREATEOS_SANDBOX_API_KEY", "").strip()
        if not key:
            msg = (
                "LANGFLOW_SANDBOX_BACKEND=createos is configured but "
                "CREATEOS_SANDBOX_API_KEY is not set. Refusing to run the code."
            )
            raise SandboxUnavailableError(msg)
        return key

    @staticmethod
    def _base_url() -> str:
        url = os.environ.get("CREATEOS_SANDBOX_BASE_URL", _CREATEOS_DEFAULT_BASE_URL).strip().rstrip("/")
        parsed = httpx.URL(url)
        # Every request carries the API key in a header, so a plaintext
        # control plane would leak it to the network. Loopback stays allowed
        # for local development against a self-hosted control plane.
        if parsed.scheme != "https" and parsed.host not in {"localhost", "127.0.0.1", "::1"}:
            msg = (
                f"CREATEOS_SANDBOX_BASE_URL must use https (got {url!r}); the CreateOS API key is "
                "sent as a request header. Refusing to run the code."
            )
            raise SandboxUnavailableError(msg)
        return url

    @staticmethod
    def _timeout(budget: float) -> httpx.Timeout:
        """Per-phase timeouts that keep the worst case near ``budget``.

        httpx applies a scalar timeout to EACH phase (connect, write, read,
        pool) rather than to the request as a whole, so passing one number lets
        a slow connect and a slow read each consume the full value. Connect and
        pool are pinned short so the read budget carries the actual wait.

        This still is not an absolute wall-clock deadline -- destroying the VM
        is what actually stops a runaway guest, and that happens in the caller's
        ``finally``.
        """
        short = min(_CREATEOS_CONNECT_TIMEOUT_SECONDS, budget)
        return httpx.Timeout(budget, connect=short, pool=short)

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(
            base_url=self._base_url(),
            timeout=self._timeout(timeout),
            headers={"X-Api-Key": self._api_key()},
        )

    # -- JSend envelope ---------------------------------------------------

    @staticmethod
    def _redact(text: str) -> str:
        """Remove the API key from text that will reach an exception or a log.

        Response bodies are echoed into error messages, and a misconfigured or
        hostile endpoint could reflect the request headers back. The key must
        not travel into a traceback just because the server chose to repeat it.
        """
        key = os.environ.get("CREATEOS_SANDBOX_API_KEY", "").strip()
        return text.replace(key, "***") if key else text

    def _unwrap(self, response: httpx.Response) -> dict:
        """Return the ``data`` payload of a JSend envelope, or raise.

        Nothing in this mapping degrades to in-process execution: a
        misconfiguration or a rejected policy raises SandboxUnavailableError
        (fail closed), while a transient control-plane fault raises
        SandboxExecutionError.
        """
        if response.status_code == httpx.codes.OK:
            try:
                body = response.json()
            except ValueError as exc:
                msg = "CreateOS returned a non-JSON response"
                raise SandboxExecutionError(msg) from exc
            if not isinstance(body, dict) or body.get("status") != "success":
                msg = f"CreateOS returned an unsuccessful envelope: {self._redact(repr(body))}"
                raise SandboxExecutionError(msg)
            data = body.get("data")
            return data if isinstance(data, dict) else {}

        detail = self._redact(response.text.strip()[:500])
        msg = f"CreateOS request failed ({response.status_code}): {detail}"
        # 429 and 5xx are worth retrying and are not the operator's fault;
        # everything else means the request or the credential is wrong, which
        # must block execution rather than look like a flaky run.
        transient = (
            response.status_code == httpx.codes.TOO_MANY_REQUESTS
            or response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR
        )
        if transient:
            raise SandboxExecutionError(msg)
        raise SandboxUnavailableError(msg)

    # -- preflight and catalog --------------------------------------------

    def preflight(self) -> None:
        """Verify the credential once per process, failing closed."""
        if self._preflighted:
            return
        try:
            with self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
                self._unwrap(client.get("/v1/whoami"))
        except httpx.HTTPError as exc:
            msg = f"CreateOS control plane is unreachable: {exc}. Refusing to run the code."
            raise SandboxUnavailableError(msg) from exc
        self._preflighted = True

    def _catalog(self) -> tuple[tuple[int, str], ...]:
        """The CreateOS shape catalog as ``(mem_mib, shape_id)``, ascending.

        Fetched once per process. The catalog is static configuration, so a
        stale entry is not a correctness risk worth a request per execution.
        """
        with self._lock:
            if self._shapes is None:
                try:
                    with self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
                        data = self._unwrap(client.get("/v1/shapes"))
                except httpx.HTTPError as exc:
                    msg = f"Could not read the CreateOS shape catalog: {exc}"
                    raise SandboxUnavailableError(msg) from exc
                self._shapes = tuple(
                    sorted(
                        (int(shape["mem_mib"]), str(shape["id"]))
                        for shape in data.get("data", [])
                        if shape.get("mem_mib") and shape.get("id")
                    )
                )
        return self._shapes

    def _shape_for(self, memory_mb: int) -> str:
        """Choose the VM shape for one execution.

        A CreateOS shape fixes vCPU as well as memory, so it cannot be derived
        from ``sandbox_memory_mb`` alone. The default is therefore a named
        shape sized for real work (numpy/pandas in a fresh guest), and
        ``sandbox_memory_mb`` acts only as a floor that can raise it.

        Never rounds DOWN. A shape with less memory than the operator
        configured would produce OOM kills that read as user-code bugs rather
        than as a misconfigured sandbox.
        """
        shapes = self._catalog()
        available = {shape_id: mem_mib for mem_mib, shape_id in shapes}

        pinned = os.environ.get("CREATEOS_SANDBOX_SHAPE", "").strip()
        if pinned:
            if pinned not in available:
                msg = (
                    f"CREATEOS_SANDBOX_SHAPE={pinned!r} is not in the CreateOS shape catalog "
                    f"({', '.join(sorted(available))}). Refusing to run the code."
                )
                raise SandboxUnavailableError(msg)
            if available[pinned] < memory_mb:
                msg = (
                    f"CREATEOS_SANDBOX_SHAPE={pinned!r} provides {available[pinned]} MiB but "
                    f"LANGFLOW_SANDBOX_MEMORY_MB is {memory_mb}. Refusing to run the code."
                )
                raise SandboxUnavailableError(msg)
            return pinned

        # Named rather than derived: "smallest shape with >= 4096 MiB" would
        # tie between s-2vcpu-4gb and s-4vcpu-4gb and resolve on sort order.
        if memory_mb <= _CREATEOS_DEFAULT_SHAPE_MEMORY_MIB and _CREATEOS_DEFAULT_SHAPE in available:
            return _CREATEOS_DEFAULT_SHAPE

        for mem_mib, shape_id in shapes:
            if mem_mib >= memory_mb:
                return shape_id
        msg = (
            f"No CreateOS shape provides the configured {memory_mb} MB "
            "(see LANGFLOW_SANDBOX_MEMORY_MB). Refusing to run the code."
        )
        raise SandboxUnavailableError(msg)

    # -- network policy ---------------------------------------------------

    @staticmethod
    def _egress_for(settings: _SandboxSettings) -> tuple[str, ...]:
        if not settings.allow_network:
            return _CREATEOS_DENY_ALL_EGRESS
        if not settings.allowed_domains:
            # Divergence from exec-sandbox, which keeps a package-registry-only
            # default here. CreateOS has no equivalent built-in list, and
            # inventing one would be guesswork, so allow_network without an
            # explicit allowlist means unrestricted egress.
            return ("*",)
        invalid = [rule for rule in settings.allowed_domains if not _is_valid_egress_rule(rule)]
        if invalid:
            msg = (
                f"LANGFLOW_SANDBOX_ALLOWED_DOMAINS contains entries CreateOS cannot parse: {invalid}. "
                "Rules the host cannot parse make it fall back to allow-all, so this is refused "
                "rather than sent. Use host, *.host, ipv4, or cidr, each optionally with :port. "
                "IPv6 and *:port are not supported by the host parser."
            )
            raise SandboxUnavailableError(msg)
        return (*settings.allowed_domains, _CREATEOS_DNS_EGRESS)

    # -- execution --------------------------------------------------------

    def run(self, code: str, *, env: dict[str, str] | None = None, session: SessionKey | None = None) -> SandboxResult:
        settings = _sandbox_settings()
        self.preflight()
        if session is None:
            return self._run_throwaway(code, env, settings)
        return self._run_in_session(code, env, settings, session)

    # -- one VM per execution ---------------------------------------------

    def _run_throwaway(self, code: str, env: dict[str, str] | None, settings: _SandboxSettings) -> SandboxResult:
        """The default: nothing survives between two runs of a component."""
        with self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
            sandbox_id = self._create(client, env, settings, auto_pause=_auto_pause_seconds(settings.timeout_seconds))
            try:
                return self._upload_and_exec(client, sandbox_id, code, settings)
            finally:
                # Always tear down: sandboxes bill while running, and the
                # teardown is what kills a guest process we stopped waiting on.
                self._destroy(client, sandbox_id)

    # -- one VM per (flow, user) session -----------------------------------

    def _run_in_session(
        self, code: str, env: dict[str, str] | None, settings: _SandboxSettings, session: SessionKey
    ) -> SandboxResult:
        """Reuse one guest across executions of the same flow and user.

        Serialized per session. Two executions of one session share a guest and
        a code path on its filesystem, so running them at once would let each
        overwrite the other's program. Serializing also matches what the shared
        state implies: a session behaves like one interpreter, not several.

        The guest is NOT paused between runs. Pause and resume were measured on
        the live control plane at 16.2s and 12.7s for a 4 GiB shape, against
        ~1.0s to create a fresh VM, so pausing an idle session would cost more
        than throwing it away. The session stays running and the idle reaper
        destroys it.
        """
        # Keyed on the policy as well as the identity, so a guest created under
        # settings the operator has since changed is never adopted. See
        # _session_identity -- the control plane cannot be asked what policy a
        # running guest has, so the name is what has to encode it.
        token = _session_identity(session.token(), self._egress_for(settings), settings.memory_mb)
        lock = self._session_lock(token)
        with lock, self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
            self._reap_idle_sessions(client, settings, token)
            sandbox_id = self._acquire_session_vm(client, token, env, settings)
            try:
                result = self._upload_and_exec(client, sandbox_id, code, settings)
            except SandboxExecutionError:
                # The guest is in an unknown state (it may have been reclaimed
                # under us). Drop it rather than hand a possibly-dead VM to the
                # next execution, which would fail for a reason that has
                # nothing to do with its own code.
                self._drop_session(client, token)
                raise
            if result.exit_code == _EXIT_CODE_TIMEOUT:
                # A timeout is NOT proof that the guest command stopped. The
                # deadline only closes the stream; the server then notices the
                # dead client on its next heartbeat and kills the command, and
                # neither step is confirmed to this process. A delayed or lost
                # kill would leave the old program running, and the next
                # execution would see status "running", pass the liveness
                # check, and execute alongside it -- racing on /workspace, on
                # the artifact directory, and on the state pickle, with the
                # per-session lock powerless because the first execution has
                # already returned.
                #
                # So a timed-out session is tainted. Destroying the guest is
                # the one kill this process can actually issue, and dropping
                # the mapping means the next execution builds a clean VM even
                # if that destroy never lands.
                logger.warning("CreateOS session guest timed out; destroying it rather than reusing it")
                self._drop_session(client, token)
                return result
            self._touch_session(token, sandbox_id)
            return result

    def _session_lock(self, token: str) -> threading.Lock:
        with self._lock:
            lock = self._session_locks.get(token)
            if lock is None:
                lock = self._session_locks[token] = threading.Lock()
            return lock

    def _touch_session(self, token: str, sandbox_id: str) -> None:
        """Record that this session's guest is in use as of now.

        Only refreshes an entry that still exists: a session dropped while this
        execution was running must stay dropped, not be resurrected by a
        timestamp.
        """
        with self._lock:
            if token in self._sessions:
                self._sessions[token] = (sandbox_id, time.monotonic())

    def _acquire_session_vm(
        self, client: httpx.Client, token: str, env: dict[str, str] | None, settings: _SandboxSettings
    ) -> str:
        """Return this session's guest, creating one when there is none alive.

        A cached id is confirmed against the control plane before it is used:
        the sandbox may have been paused by its own auto-pause backstop,
        destroyed by an operator, or lost with its host. A stale id would
        otherwise surface as a 404 that looks like a broken execution.

        The in-process map is a CACHE, not the registry. Langflow runs more
        than one worker, and ``os.fork`` gives each child an empty map, so a
        map-only design hands every worker its own guest for the same session:
        the state a flow sees would depend on which worker took the request,
        and each worker would hold a billed VM for the same identity.

        The control plane is the registry instead. A sandbox ``name`` is unique
        per user among non-terminal sandboxes, so creating with a name derived
        from the session token is a compare-and-swap: the first worker wins and
        every other gets 409, then adopts the winner's guest. Verified against
        the live API -- a duplicate name returns 409 and the guest is findable
        by name.
        """
        with self._lock:
            cached = self._sessions.get(token)
        if cached is not None:
            sandbox_id, _ = cached
            if self._is_running(client, sandbox_id):
                # Stamp on the way IN, not only on the way out. The stored
                # timestamp is what the idle reaper judges, and until this
                # execution finishes the only timestamp on record is the
                # PREVIOUS completion. A run that starts inside the idle
                # window but outlives it would otherwise be reaped while its
                # own code is still running.
                self._touch_session(token, sandbox_id)
                return sandbox_id
            logger.debug("CreateOS session guest %s is no longer running; replacing it", sandbox_id)
            self._drop_session(client, token)

        name = _session_guest_name(token)
        # Another worker may already own this session's guest.
        adopted = self._find_session_vm(client, name)
        if adopted is not None:
            with self._lock:
                self._sessions[token] = (adopted, time.monotonic())
            return adopted

        # The control plane's own backstop must outlive our reaper, or it would
        # pause a session that is merely between executions and the state the
        # operator opted into would vanish without anyone saying so.
        auto_pause = max(
            _auto_pause_seconds(settings.timeout_seconds),
            settings.session_idle_seconds + _CREATEOS_AUTO_PAUSE_MARGIN_SECONDS,
        )
        try:
            sandbox_id = self._create(client, env, settings, auto_pause=auto_pause, name=name)
        except _SessionNameTakenError:
            # Another worker won the race between the lookup above and this
            # create. Its guest is the session's guest.
            sandbox_id = self._find_session_vm(client, name)
            if sandbox_id is None:
                msg = (
                    "CreateOS reports a sandbox already exists for this session but it cannot be "
                    "found. Refusing to run the code rather than build a second guest for the "
                    "same session."
                )
                raise SandboxExecutionError(msg) from None
        with self._lock:
            self._sessions[token] = (sandbox_id, time.monotonic())
        return sandbox_id

    def _find_session_vm(self, client: httpx.Client, name: str) -> str | None:
        """Find a running guest already registered under ``name``.

        The list endpoint has no name filter, so this pages and matches
        client-side. Paging is bounded: a caller with more running sandboxes
        than that has problems this function cannot solve, and an unbounded
        loop on a control-plane list is worse than a missed adoption, which
        only costs a 409 and a retry.

        Returns None on any failure. A failed lookup must not block a run; the
        create that follows either succeeds or reports the conflict itself.
        """
        offset = 0
        for _ in range(_CREATEOS_SESSION_LOOKUP_PAGES):
            try:
                data = self._unwrap(
                    client.get(
                        "/v1/sandboxes",
                        params={"status": "running", "limit": _CREATEOS_SESSION_LOOKUP_PAGE_SIZE, "offset": offset},
                    )
                )
            except (httpx.HTTPError, SandboxExecutionError):
                logger.debug("Could not list CreateOS sandboxes while looking up a session guest", exc_info=True)
                return None
            rows = data.get("data") or []
            for row in rows:
                if row.get("name") == name and row.get("id"):
                    return str(row["id"])
            if len(rows) < _CREATEOS_SESSION_LOOKUP_PAGE_SIZE:
                return None
            offset += _CREATEOS_SESSION_LOOKUP_PAGE_SIZE
        return None

    def _is_running(self, client: httpx.Client, sandbox_id: str) -> bool:
        try:
            data = self._unwrap(client.get(f"/v1/sandboxes/{sandbox_id}"))
        except (httpx.HTTPError, SandboxExecutionError):
            return False
        return data.get("status") == "running"

    def _drop_session(self, client: httpx.Client, token: str) -> None:
        with self._lock:
            entry = self._sessions.pop(token, None)
        if entry is not None:
            self._destroy(client, entry[0])

    def _reap_idle_sessions(self, client: httpx.Client, settings: _SandboxSettings, current: str) -> None:
        """Destroy sessions that went quiet, bounding both cost and exposure.

        Runs on the way into an execution rather than on a timer: a background
        thread would have to survive forks and shutdown, and this module
        already owns enough lifecycle. The gap is honest and bounded -- a
        process that stops running code entirely leaves its last sessions to
        the control plane's auto-pause backstop.

        This reaps OTHER sessions than the caller's, so it must never destroy a
        guest that is mid-execution. Nothing about the timestamps rules that
        out on its own: an execution can legitimately start just inside the
        idle window and run past the deadline (the default settings allow a
        300s execution against a 600s idle window), and the victim's own
        ``last_used`` cannot advance while it is busy. The per-session lock is
        the authority on "in use", so a session whose lock is held is skipped
        outright and the destroy happens under that lock.

        ``current`` is the caller's own session, which is exempt from that
        probe: the caller already holds its lock and a ``threading.Lock`` is not
        reentrant, so probing would always fail and a session could never expire
        for the flow that owns it. Reaping it here is safe and wanted -- the
        caller has not started executing yet, and a guest past the idle bound
        must not be handed back to the very next run just because it is the same
        flow asking.
        """
        cutoff = time.monotonic() - settings.session_idle_seconds
        with self._lock:
            stale = [token for token, (_, last_used) in self._sessions.items() if last_used < cutoff]
        for token in stale:
            if token == current:
                logger.debug("Destroying idle CreateOS session guest")
                self._drop_session(client, token)
                continue
            lock = self._session_lock(token)
            # NEVER block: this runs on another session's critical path, and
            # waiting here would serialize unrelated flows behind whatever the
            # busy one is doing. A session that is executing simply is not
            # idle, so failing to take the lock is the answer, not a retry.
            if not lock.acquire(blocking=False):
                logger.debug("Skipping idle reap: the session is executing")
                continue
            try:
                # Re-read under the lock. The scan above is a snapshot, and the
                # owner may have finished and stamped a fresh timestamp in
                # between -- destroying on the stale reading would kill a guest
                # that just proved it is live.
                with self._lock:
                    entry = self._sessions.get(token)
                    still_idle = entry is not None and entry[1] < cutoff
                if not still_idle:
                    continue
                logger.debug("Destroying idle CreateOS session guest")
                self._drop_session(client, token)
            finally:
                lock.release()

    def _destroy_all_sessions(self) -> None:
        with self._lock:
            tokens = list(self._sessions)
        if not tokens:
            return
        with self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
            for token in tokens:
                self._drop_session(client, token)

    # -- creation ----------------------------------------------------------

    def _create(
        self,
        client: httpx.Client,
        env: dict[str, str] | None,
        settings: _SandboxSettings,
        *,
        auto_pause: int,
        name: str | None = None,
    ) -> str:
        """Create one guest and prove the control plane stored the policy we asked for.

        Raises:
            _SessionNameTakenError: ``name`` was given and is already in use, which
                means another worker owns this session's guest.
        """
        shape = self._shape_for(settings.memory_mb)
        egress = self._egress_for(settings)
        # Keys must be declared at create time; a key introduced on the exec
        # call alone is rejected by the control plane.
        envs = {key: str(value) for key, value in (env or {}).items()}
        rootfs = os.environ.get("CREATEOS_SANDBOX_ROOTFS", _CREATEOS_DEFAULT_ROOTFS).strip()
        body = {
            "shape": shape,
            "rootfs": rootfs,
            "envs": envs,
            "egress": list(egress),
            # Backstop against orphans: if teardown never runs (process
            # killed, DELETE lost) the VM stops consuming a host instead of
            # running forever. Deliberately longer than this execution -- see
            # _auto_pause_seconds.
            "auto_pause_after_seconds": auto_pause,
        }
        if name is not None:
            body["name"] = name

        try:
            response = client.post("/v1/sandboxes", json=body)
            if name is not None and response.status_code == httpx.codes.CONFLICT:
                raise _SessionNameTakenError(name)
            created = self._unwrap(response)
        except httpx.HTTPError as exc:
            msg = f"Could not create a CreateOS sandbox: {exc}"
            raise SandboxExecutionError(msg) from exc

        sandbox_id = created.get("id")
        if not sandbox_id:
            # The VM may exist remotely even though we cannot address it.
            # auto_pause_after_seconds is the only thing that will reclaim
            # it, so say so rather than failing silently.
            msg = (
                f"CreateOS sandbox create returned no id: {self._redact(repr(created))}. "
                "A VM may have been created and cannot be destroyed by this process."
            )
            raise SandboxExecutionError(msg)

        try:
            self._assert_policy_applied(created, egress, settings)
        except SandboxUnavailableError:
            self._destroy(client, sandbox_id)
            raise
        return sandbox_id

    @staticmethod
    def _assert_policy_applied(created: dict, egress: tuple[str, ...], settings: _SandboxSettings) -> None:
        """Verify the control plane accepted the policy we asked for.

        The create response echoes the stored ``egress`` and the granted
        ``mem_mib``, so a request that was silently trimmed, reordered away, or
        capped is caught before any user code runs. This does NOT prove the
        rules were installed on the host -- the API exposes requested state,
        not installed state -- so it narrows the gap rather than closing it.

        The gap is real: CreateOS has no explicit deny-all token (empty,
        ``null``, and ``["*"]`` all mean allow-all), and
        ``fc/internal/hosts/vm/egress.go`` falls back to allow-all, not
        deny-all, when it cannot parse a rule set. This check only catches a
        policy that was accepted and then silently altered; it cannot catch
        one the host never installed at all. ``_is_valid_egress_rule`` is what
        keeps a rule from ever reaching that unparseable path in the first
        place.
        """
        # `egress` is omitempty on the control plane's response type, and the
        # request always carries a non-empty list, so an ABSENT field is itself
        # a mismatch -- treating it as "nothing to check" would let a server
        # that dropped the policy pass verification silently.
        echoed = created.get("egress")
        if echoed is None or sorted(map(str, echoed)) != sorted(egress):
            stored = "omitted" if echoed is None else _CreateosExecutor._redact(repr(echoed))
            msg = (
                f"CreateOS did not store the requested egress policy "
                f"(sent {list(egress)}, stored {stored}). Refusing to run the code."
            )
            raise SandboxUnavailableError(msg)

        granted = created.get("mem_mib")
        if granted is not None:
            # The rest of this module treats control-plane responses as
            # untrusted, and this one is no different. A bare int() on a
            # string, list, or dict raises outside the SandboxUnavailableError
            # tree, so the caller's teardown handler would not run and the VM
            # would leak. A value that cannot be compared is a FAILED
            # verification, not a crash.
            try:
                granted_mib = int(granted)
            except (TypeError, ValueError) as exc:
                msg = (
                    f"CreateOS reported an unreadable memory grant "
                    f"({_CreateosExecutor._redact(repr(granted))}). Refusing to run the code."
                )
                raise SandboxUnavailableError(msg) from exc
            if granted_mib < settings.memory_mb:
                msg = (
                    f"CreateOS granted {granted} MiB but LANGFLOW_SANDBOX_MEMORY_MB is "
                    f"{settings.memory_mb}. Refusing to run the code."
                )
                raise SandboxUnavailableError(msg)

    def _destroy(self, client: httpx.Client, sandbox_id: str) -> None:
        """Best-effort teardown that never masks the execution result.

        A failed destroy must not replace a real result or a real error with a
        teardown error, but it must not be invisible either: the VM keeps
        billing until auto-pause catches it.

        A 200 here means the control plane accepted the request and moved the
        sandbox to ``destroying``; the host reclaims it asynchronously. So this
        confirms the request landed, not that the guest is already gone.
        """
        try:
            response = client.delete(f"/v1/sandboxes/{sandbox_id}")
            if response.status_code != httpx.codes.OK:
                logger.warning(
                    "CreateOS sandbox %s was not destroyed (HTTP %s); it will auto-pause when idle",
                    sandbox_id,
                    response.status_code,
                )
        except Exception:  # noqa: BLE001 - teardown must never mask the result
            logger.warning(
                "CreateOS sandbox %s could not be destroyed; it will auto-pause when idle",
                sandbox_id,
                exc_info=True,
            )

    def _upload_and_exec(
        self, client: httpx.Client, sandbox_id: str, code: str, settings: _SandboxSettings
    ) -> SandboxResult:
        code_path = _guest_code_path()
        try:
            # Uploaded as a file rather than passed as `python3 -c <code>` so
            # no quoting or argv length limit can alter what the guest runs.
            self._unwrap(
                client.put(
                    f"/v1/sandboxes/{sandbox_id}/files",
                    params={"path": code_path},
                    content=code.encode(),
                    headers={"Content-Type": "application/octet-stream"},
                )
            )
        except httpx.HTTPError as exc:
            msg = f"Could not upload code to the CreateOS sandbox: {exc}"
            raise SandboxExecutionError(msg) from exc

        result = self._stream_exec(client, sandbox_id, code_path, settings)
        if settings.collect_artifacts:
            result = self._with_artifacts(client, sandbox_id, result, settings)
        self._log_metrics(client, sandbox_id)
        return result

    def _stream_exec(
        self, client: httpx.Client, sandbox_id: str, code_path: str, settings: _SandboxSettings
    ) -> SandboxResult:
        """Run the uploaded program, streaming its output under a wall clock.

        Streaming rather than buffered for one reason: the exec endpoint has no
        server-side timeout field, and the stream is the documented kill path.
        The server heartbeats every 5s, so it notices a client that went away
        and kills the in-VM command within about 5s of the disconnect. Closing
        the response at the deadline is therefore what enforces
        ``sandbox_timeout_seconds``, and it works on a session guest that must
        survive the timeout as well as on a throwaway one that gets destroyed.

        Buffered mode could only be bounded by abandoning the request and
        destroying the VM, which is not available when the guest has to live on,
        and which discards whatever the program had already printed.
        """
        deadline = time.monotonic() + _exec_deadline(settings.timeout_seconds)
        stdout: list[str] = []
        stderr: list[str] = []
        exit_code: int | None = None
        started = time.monotonic()

        try:
            with client.stream(
                "POST",
                f"/v1/sandboxes/{sandbox_id}/exec",
                params={"stream": "true"},
                json={"cmd": _CREATEOS_GUEST_SHELL, "args": ["-c", self._guest_command(code_path, settings)]},
                timeout=self._timeout(_exec_deadline(settings.timeout_seconds)),
            ) as response:
                if response.status_code != httpx.codes.OK:
                    response.read()
                    self._unwrap(response)  # raises with the mapped error class
                for line in response.iter_lines():
                    if time.monotonic() > deadline:
                        # Leaving the block closes the connection, which is the
                        # signal that kills the guest command.
                        exit_code = _EXIT_CODE_TIMEOUT
                        break
                    event = self._parse_stream_line(line)
                    if event is None:
                        continue
                    if event.get("hb"):
                        continue
                    if event.get("stdout"):
                        stdout.append(str(event["stdout"]))
                    if event.get("stderr"):
                        stderr.append(str(event["stderr"]))
                    if event.get("error"):
                        msg = f"CreateOS could not start the guest command: {self._redact(str(event['error']))}"
                        raise SandboxExecutionError(msg)
                    if "exit_code" in event:
                        # Guest-controlled frame. An unmapped ValueError here
                        # escapes the SandboxExecutionError tree, so
                        # _run_in_session would keep the session mapping
                        # pointing at a guest whose program state is unknown
                        # and the next execution would reuse it.
                        try:
                            exit_code = int(event["exit_code"] or 0)
                        except (TypeError, ValueError) as exc:
                            msg = f"CreateOS returned an unreadable exit code: {self._redact(repr(event['exit_code']))}"
                            raise SandboxExecutionError(msg) from exc
                        break
        except httpx.TimeoutException:
            exit_code = _EXIT_CODE_TIMEOUT
        except httpx.HTTPError as exc:
            msg = f"CreateOS sandbox execution failed: {exc}"
            raise SandboxExecutionError(msg) from exc

        if exit_code is None:
            # The stream ended without a terminal frame. Treat it as an
            # infrastructure fault rather than reporting a success this code
            # never saw the guest declare.
            msg = "CreateOS exec stream ended without an exit code"
            raise SandboxExecutionError(msg)

        return SandboxResult(
            stdout="".join(stdout),
            stderr="".join(stderr),
            exit_code=exit_code,
            execution_time_ms=int((time.monotonic() - started) * 1000),
        )

    @staticmethod
    def _guest_command(code_path: str, settings: _SandboxSettings) -> str:
        """The shell line that runs the uploaded program.

        Every part is either a module constant or ``code_path``, which this
        module generates from uuid4 hex. Nothing a caller supplies is ever
        interpolated into a shell string. When artifacts are collected the
        directory is prepared in the same command rather than in a second
        exec, so the guest is ready before the program runs and the run still
        costs one round trip.

        The program file is removed afterwards, and the program's exit status
        is preserved across that cleanup. Without it a long-lived session guest
        would accumulate one file per execution forever.
        """
        run_program = f"{_CREATEOS_GUEST_PYTHON} {code_path}; _lf_rc=$?; rm -f {code_path}; exit $_lf_rc"
        if not settings.collect_artifacts:
            return run_program
        # Emptied, not just created. On a reused session guest the directory
        # survives from the last execution, so without this every run would
        # hand back its predecessor's files as if it had produced them, and the
        # set would grow without bound. Anything a session is meant to keep
        # belongs elsewhere under /workspace.
        return f"rm -rf {_CREATEOS_GUEST_ARTIFACT_DIR}; mkdir -p {_CREATEOS_GUEST_ARTIFACT_DIR}; {run_program}"

    @staticmethod
    def _parse_stream_line(line: str) -> dict | None:
        """One NDJSON event, or None for a blank or unparsable line.

        A malformed line is skipped rather than fatal: the terminal frame is
        what decides the outcome, and discarding a whole completed execution
        over one bad line would be worse than losing that line's output.
        """
        line = line.strip()
        if not line:
            return None
        try:
            event = json.loads(line)
        except ValueError:
            logger.debug("Skipping unparsable CreateOS exec stream line")
            return None
        return event if isinstance(event, dict) else None

    # -- artifacts ---------------------------------------------------------

    def _with_artifacts(
        self, client: httpx.Client, sandbox_id: str, result: SandboxResult, settings: _SandboxSettings
    ) -> SandboxResult:
        """Attach whatever the program left in the guest's artifact directory.

        Collected as one tarball rather than file by file, because the API
        downloads a single path per request and the guest is the only side that
        knows what was written.

        Never fatal. Artifacts are an extra, so a guest that wrote nothing, a
        rootfs without ``tar``, or a failed download all return the execution's
        real result rather than replacing it with a collection error.

        The archive is built by the guest, so it is not merely absent or
        oversized -- it can be malformed. ``tarfile`` reports that outside the
        ``OSError`` tree (``TarError`` derives straight from ``Exception``, and
        a truncated gzip member surfaces as ``EOFError``), so both have to be
        named here or a corrupt tarball would escape as an uncaught traceback
        and replace a perfectly good execution result. A guest that filled its
        disk mid-``tar``, or a program still writing after a post-timeout kill
        that has not landed yet, produces exactly that.
        """
        try:
            self._unwrap(
                client.post(
                    f"/v1/sandboxes/{sandbox_id}/exec",
                    json={
                        "cmd": _CREATEOS_GUEST_SHELL,
                        "args": ["-c", _CREATEOS_ARTIFACT_TAR_COMMAND],
                    },
                )
            )
            archive = self._download_artifact_archive(client, sandbox_id, settings.max_artifact_bytes)
            if archive is None:
                return result
            files = self._unpack_artifacts(archive, settings.max_artifact_bytes)
        except (httpx.HTTPError, SandboxExecutionError, OSError, tarfile.TarError, EOFError):
            logger.warning("Could not collect CreateOS artifacts; returning the execution result", exc_info=True)
            return result
        if not files:
            return result
        return replace(result, files=files)

    def _download_artifact_archive(self, client: httpx.Client, sandbox_id: str, max_bytes: int) -> bytes | None:
        """Fetch the archive, refusing it as soon as it exceeds the budget.

        Streamed rather than read whole. The archive is guest-controlled, so
        reading ``response.content`` would put an arbitrarily large body in
        this process BEFORE any cap could be applied -- the extracted-size
        budget cannot protect memory it has already spent.

        The compressed budget is the same number as the extracted one. A
        gzipped tar of N bytes of files is smaller than N except when the
        member headers dominate, and that case is bounded separately by the
        member count.

        Returns None when there is nothing to collect or the archive is too
        large; artifacts are an extra and must never replace a real result.
        """
        chunks: list[bytes] = []
        total = 0
        with client.stream(
            "GET",
            f"/v1/sandboxes/{sandbox_id}/files",
            params={"path": _CREATEOS_GUEST_ARTIFACT_ARCHIVE},
        ) as response:
            if response.status_code != httpx.codes.OK:
                logger.debug("No CreateOS artifact archive to collect (HTTP %s)", response.status_code)
                return None
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    # Leaving the block closes the connection, so the rest of
                    # the body is never transferred.
                    logger.warning(
                        "CreateOS artifact archive exceeded %d compressed bytes; collecting nothing", max_bytes
                    )
                    return None
                chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _unpack_artifacts(archive: bytes, max_bytes: int) -> tuple[SandboxFile, ...]:
        """Read a guest-produced tarball into memory under a hard size cap.

        The archive is built by code the guest controls, so it is treated as
        hostile input:

        * Only regular files are read. Symlinks, devices and directories are
          skipped, so a link pointing out of the archive cannot be followed.
        * Nothing is ever written to the host filesystem, so a member named
          ``../../etc/passwd`` cannot escape anywhere. Its name is still
          normalized before it is reported.
        * Reading stops at ``max_bytes`` in total, which bounds a decompression
          bomb by output size rather than trusting the declared member sizes.
        * At most ``_CREATEOS_MAX_ARTIFACT_MEMBERS`` members are read. The byte
          budget alone does not bound this: an archive of a million empty files
          never advances ``total``, yet each one costs a header parse and a
          SandboxFile.
        """
        files: list[SandboxFile] = []
        total = 0
        inspected = 0
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            for member in tar:
                inspected += 1
                if inspected > _CREATEOS_MAX_ARTIFACT_MEMBERS:
                    logger.warning(
                        "CreateOS artifact archive holds more than %d entries; collecting no further",
                        _CREATEOS_MAX_ARTIFACT_MEMBERS,
                    )
                    break
                if not member.isfile():
                    continue
                remaining = max_bytes - total
                if remaining <= 0:
                    logger.warning("Stopped collecting CreateOS artifacts at %d bytes", max_bytes)
                    break
                handle = tar.extractfile(member)
                if handle is None:
                    continue
                # One byte over the cap is enough to know the cap was hit,
                # without materializing whatever the member actually holds.
                content = handle.read(remaining + 1)
                if len(content) > remaining:
                    logger.warning("Stopped collecting CreateOS artifacts at %d bytes", max_bytes)
                    break
                total += len(content)
                files.append(SandboxFile(path=_safe_artifact_name(member.name), content=content))
        return tuple(files)

    # -- telemetry ---------------------------------------------------------

    def _log_metrics(self, client: httpx.Client, sandbox_id: str) -> None:
        """Log this guest's resource use, when the operator asked for it.

        Off by default and behind an env var rather than a log level, because
        it costs a control-plane round trip on every execution and most
        deployments never read it.
        """
        if os.environ.get("CREATEOS_SANDBOX_METRICS", "").strip().lower() not in {"1", "true", "yes", "on"}:
            return
        try:
            data = self._unwrap(client.get(f"/v1/sandboxes/{sandbox_id}/metrics"))
        except (httpx.HTTPError, SandboxExecutionError):
            logger.debug("Could not read CreateOS sandbox metrics", exc_info=True)
            return
        logger.info("CreateOS sandbox %s metrics: %s", sandbox_id, self._redact(repr(data)))

    def reset_after_fork(self) -> None:
        """Rebuild synchronization state in a freshly forked child.

        The cached catalog and preflight flag stay valid across a fork; the
        mutexes must be replaced, since the threads that owned them do not
        exist in the child.

        Session guests are forgotten rather than destroyed. The parent still
        owns them and is still using them, so a child that tore them down would
        break executions it knows nothing about. The child simply creates its
        own.
        """
        self._lock = threading.Lock()
        self._session_locks = {}
        self._sessions = {}


# Re-executing this module (importlib.reload, or a test that reimports it)
# must not raise. seal_builtins() has run by then, and re-registering a sealed
# built-in name is refused by design -- which is the correct refusal, just not
# a reason to break the import.
with contextlib.suppress(ValueError):
    register_sandbox_backend(SANDBOX_BACKEND_CREATEOS, _CreateosExecutor)
