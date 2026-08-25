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

# A session guest belongs to the process that created it, and its name is fresh
# random hex rather than anything derivable from the session.
#
# An earlier design derived the name from the session token so any worker could
# find and ADOPT another worker's guest, using the control plane's per-user name
# uniqueness as a compare-and-swap. That cannot be made safe from here. Every
# mechanism this module uses to keep one guest consistent is process-local: the
# per-session ``threading.Lock`` that stops two executions from sharing one
# guest's ``/workspace``, the idle reaper, and the ``shutdown``/``atexit``
# teardown. None of them reach another process, so an adopted guest is one this
# process serializes against nothing -- two workers would run in the same VM at
# once, racing on the code file, the artifact directory, and the state pickle,
# and either could destroy it while the other was mid-execution.
#
# So a guest is owned by exactly one process. The cost is one VM per worker per
# session instead of one per session; the idle reaper and the control plane's
# auto-pause bound it, and both are already required for the crash case.
#
# A fresh name per create matters for the SAME reason a replacement must not
# reuse the old one: DELETE only moves a sandbox to ``destroying``, and the
# control plane rejects a duplicate name among non-terminal sandboxes. A
# derived (stable) name would therefore make the replacement of a just-dropped
# guest collide with the corpse of its predecessor.
#
# The control plane caps a name at 22 characters and rejects a longer one with
# 400 -- found by running this against the live API, not by any local test. 19
# hex characters leave 76 bits, so a collision with another guest of the same
# account is not a real risk.
_CREATEOS_SESSION_NAME_MAX = 22
_CREATEOS_SESSION_NAME_PREFIX = "lf-"
_CREATEOS_SESSION_NAME_CHARS = _CREATEOS_SESSION_NAME_MAX - len(_CREATEOS_SESSION_NAME_PREFIX)


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


# Largest combined stdout+stderr one execution may return.
#
# The guest streams output line by line and this process accumulates it, so
# without a cap the guest -- not the operator -- decides how much of the
# worker's memory one execution costs. ``while True: print("x" * 4096)`` fills
# it as fast as the link carries, and the result object is then held for the
# whole flow. 8 MiB is far above what a component that returns text to a flow
# has any use for, and far below what a worker can lose.
#
# Truncation is not an error: the execution keeps running and its exit code
# still decides the outcome. What is dropped is announced in the stream it was
# dropped from, so a caller reading only stdout still sees that it happened.
_CREATEOS_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
_CREATEOS_TRUNCATION_NOTICE = "\n[langflow] output truncated at {limit} bytes\n"


def _auto_pause_seconds(timeout_seconds: int) -> int:
    """Idle window for the orphan backstop, always longer than one execution."""
    return max(_CREATEOS_AUTO_PAUSE_MIN_SECONDS, timeout_seconds + _CREATEOS_AUTO_PAUSE_MARGIN_SECONDS)


def _exec_transport_budget(timeout_seconds: int) -> float:
    """HTTP timeout for one exec call, which is NOT the execution deadline.

    Two different limits, and conflating them is what let an execution outlive
    its configured timeout. ``sandbox_timeout_seconds`` is the wall clock the
    guest program gets, enforced by :meth:`_CreateosExecutor._stream_exec`
    against ``time.monotonic()``. This value is only the transport's patience:
    httpx applies it per phase, so it has to survive a slow connect and the gap
    between two stream frames, and it must therefore be LONGER than the
    execution deadline or the transport would fire first and report a timeout
    the guest had not reached.

    The margin scales with the configured value: 1s yields 3s rather than 16s,
    while the 30s default still gets the full 15s of slack.
    """
    return timeout_seconds + min(_CREATEOS_EXEC_GRACE_SECONDS, max(_CREATEOS_MIN_EXEC_GRACE_SECONDS, timeout_seconds))


# Hostname / wildcard-subdomain form from the documented egress grammar.
_CREATEOS_HOSTNAME_RE = re.compile(r"^(?:\*\.)?(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*$")

_MAX_PORT = 65535


def _rootfs() -> str:
    """The guest image every sandbox this process creates is built from."""
    return os.environ.get("CREATEOS_SANDBOX_ROOTFS", _CREATEOS_DEFAULT_ROOTFS).strip()


def _guest_code_path() -> str:
    """A path for one execution's program, unique within the guest."""
    return f"{_CREATEOS_GUEST_CODE_DIR}/{_CREATEOS_GUEST_CODE_PREFIX}{uuid.uuid4().hex}.py"


def _session_identity(token: str, egress: tuple[str, ...], memory_mb: int, rootfs: str) -> str:
    """Bind a session to the policy and image its guest was created under.

    The create-time check (:meth:`_CreateosExecutor._assert_policy_applied`) is
    the only place a guest's policy is ever verified, and a REUSED guest never
    reaches it. A session guest outlives the execution that created it -- that
    is the point -- so it also outlives a settings change: tighten
    ``LANGFLOW_SANDBOX_ALLOW_NETWORK``, narrow the allowlist, or raise the
    memory floor, and the cached guest was created under the OLD, looser policy.

    Re-verifying is not an option: ``GET /v1/sandboxes/{id}`` omits ``egress``
    entirely, and ``GET /v1/sandboxes/{id}/egress`` answers with an empty list
    even for a sandbox created with rules (checked against the live control
    plane, both while starting and while running). There is no way to ask what
    policy a guest actually has.

    So the policy is folded into the identity instead. A guest is only reused by
    a run asking for exactly what that guest was created with, because anything
    else derives a different key and misses the cache entry. Changing a setting
    orphans the old guest rather than inheriting it; the idle reaper and the
    control plane's auto-pause collect it. Session state does not survive that,
    which is correct -- the state belongs to a guest the operator has just
    declared unacceptable.

    ``rootfs`` is in here for the same reason and one more. A guest carries the
    image it booted plus everything the session wrote on top of it, so reusing
    it across a ``CREATEOS_SANDBOX_ROOTFS`` change would run the new image's
    flows against the old image's filesystem -- and the pickled session state
    was written by the old image's interpreter, which the new one may not even
    be able to read. An image change starts clean.
    """
    # Sorted so an allowlist written in a different order is the same policy,
    # and unit-separated so ("a", "b") cannot collide with ("a\x1fb",).
    policy = "\x1f".join((*sorted(egress), str(memory_mb), rootfs))
    return hashlib.sha256(f"{token}\x00{policy}".encode()).hexdigest()


def _session_guest_name() -> str:
    """A fresh control-plane name for one session guest.

    Random rather than derived. Nothing looks a guest up by name -- the process
    that created it holds its id -- so the name only has to be unique among this
    account's non-terminal sandboxes, including the ``destroying`` predecessor a
    replacement is racing against. See the note on the name constants.
    """
    return f"{_CREATEOS_SESSION_NAME_PREFIX}{uuid.uuid4().hex[:_CREATEOS_SESSION_NAME_CHARS]}"


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


class _BoundedOutput:
    """Accumulates one output stream and stops at a byte budget.

    The budget is measured in UTF-8 bytes rather than characters, because bytes
    are what the memory cost actually is: one astral-plane character is four of
    them, so a character count would let a guest spend four times the limit.

    Once the budget is spent the remaining chunks are counted and dropped rather
    than joined, so the cost of a program that never stops printing settles at
    the limit instead of growing with what it sends. The execution is NOT
    stopped: its exit code is still the guest's, and only the text is short.
    """

    def __init__(self, limit: int) -> None:
        """Start an empty accumulator bounded to ``limit`` UTF-8 bytes."""
        self._limit = limit
        self._chunks: list[str] = []
        self._size = 0
        self.truncated = False

    def append(self, chunk: str) -> None:
        """Add ``chunk``, or mark the stream truncated once the budget is gone."""
        if self.truncated:
            return
        self._size += len(chunk.encode())
        if self._size > self._limit:
            # The chunk that crosses the line is dropped whole rather than cut.
            # A partial chunk would end mid-character in the encoded form and,
            # worse, look like output the guest actually produced.
            self.truncated = True
            return
        self._chunks.append(chunk)

    def text(self) -> str:
        """The collected output, with a notice appended when anything was dropped."""
        collected = "".join(self._chunks)
        if not self.truncated:
            return collected
        return collected + _CREATEOS_TRUNCATION_NOTICE.format(limit=self._limit)


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

        The second entry is the DNS resolver. A domain allowlist is enforced on
        the DESTINATION ADDRESS, so it is inert unless the guest can also
        resolve names -- ``_egress_for`` therefore opens ``1.1.1.1:53`` whenever
        an allowlist is set. That resolver answers for ANY name, not only the
        allowlisted ones (verified live), so a guest that cannot CONNECT to
        ``evil.example`` can still ask about ``<stolen-secret>.evil.example``
        and the query itself carries the data out. exec-sandbox filters DNS
        inside the guest and refuses the lookup, so an operator moving between
        the two backends is not getting the same allowlist.

        It is declared here, in the same field as the metadata range, because
        the two are the same kind of fact: a destination the policy does not
        reach. ``_assert_backend_honours_policy`` then refuses the run unless
        the operator sets LANGFLOW_SANDBOX_ACCEPT_EGRESS_EXCEPTIONS, so the
        allowlist cannot be read as "the guest can only talk to these names"
        without someone having said, once, that they know it is not.
        """
        return Capabilities(
            isolation="hardware-virtualized",
            supports_deny_all_egress=True,
            supports_domain_allowlist=True,
            supports_sessions=True,
            supports_artifacts=True,
            egress_exceptions=(
                "169.254.0.0/16",
                f"{_CREATEOS_DNS_EGRESS} (DNS: opened when a domain allowlist is set, resolves any name)",
            ),
        )

    def shutdown(self) -> None:
        """Destroy any session guests this process is still holding.

        A throwaway run destroys its own VM in a ``finally``, so only sessions
        can outlive an execution. They must not outlive the process.
        """
        self._destroy_all_sessions()

    def __init__(self) -> None:
        """Initialize empty shape cache, preflight flag, and session state."""
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
        """Return the CreateOS API key from the environment, or refuse to run.

        Raises:
            SandboxUnavailableError: The key is not set.
        """
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
        """Return the CreateOS control-plane URL, requiring https except on loopback.

        Raises:
            SandboxUnavailableError: The URL is not https and not loopback.
        """
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
        """Build an httpx client for the CreateOS control plane with the API key set."""
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
            cached = self._shapes
        if cached is not None:
            return cached

        # Fetched OUTSIDE the mutex. The request carries a 60s budget, and this
        # is the same mutex every session operation takes, so holding it here
        # would stall unrelated flows for that whole budget. Two callers that
        # race simply fetch twice, which is far cheaper than the contention.
        try:
            with self._client(_CREATEOS_CONTROL_TIMEOUT_SECONDS) as client:
                data = self._unwrap(client.get("/v1/shapes"))
        except httpx.HTTPError as exc:
            msg = f"Could not read the CreateOS shape catalog: {exc}"
            raise SandboxUnavailableError(msg) from exc

        entries = []
        for shape in data.get("data", []):
            mem_mib, shape_id = shape.get("mem_mib"), shape.get("id")
            if not mem_mib or not shape_id:
                continue
            try:
                entries.append((int(mem_mib), str(shape_id)))
            except (TypeError, ValueError):
                # A control-plane value, so untrusted. One unreadable entry
                # costs itself; letting it raise here would escape the mapped
                # error tree and reach the component as a raw traceback.
                logger.debug("Skipping a CreateOS shape with an unreadable mem_mib", exc_info=True)

        with self._lock:
            if self._shapes is None:
                self._shapes = tuple(sorted(entries))
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
        """Translate operator network settings into CreateOS egress rules.

        Raises:
            SandboxUnavailableError: An allowed-domain entry does not parse.
        """
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
        # Deduplicated, order preserved. An operator who already lists the
        # resolver would otherwise send it twice, and _assert_policy_applied
        # compares sorted lists -- so a control plane that stores a set would
        # produce a length mismatch and refuse the run with a policy message
        # the operator cannot act on.
        rules = [*settings.allowed_domains, _CREATEOS_DNS_EGRESS]
        return tuple(dict.fromkeys(rules))

    # -- execution --------------------------------------------------------

    def run(self, code: str, *, env: dict[str, str] | None = None, session: SessionKey | None = None) -> SandboxResult:
        """Run ``code`` in a throwaway VM, or in a reused session guest when ``session`` is given."""
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
        token = _session_identity(session.token(), self._egress_for(settings), settings.memory_mb, _rootfs())
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
        """Return the lock for one session token, creating it on first use."""
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

        The in-process map is also the registry. A guest belongs to the process
        that created it and is never adopted by another, so each worker holds
        its own guest for a session and ``os.fork`` correctly gives a child an
        empty map: the child owns nothing yet.

        That is deliberate, and it is what makes the rest of this class sound.
        The per-session lock, the idle reaper, and the shutdown teardown are all
        process-local, so a shared guest would be a guest nothing serializes --
        see the note on the name constants for what that costs. A flow that runs
        across two workers therefore sees two session states rather than one;
        pinning it to one guest needs coordination this module does not have.
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

        # The control plane's own backstop must outlive our reaper, or it would
        # pause a session that is merely between executions and the state the
        # operator opted into would vanish without anyone saying so.
        auto_pause = max(
            _auto_pause_seconds(settings.timeout_seconds),
            settings.session_idle_seconds + _CREATEOS_AUTO_PAUSE_MARGIN_SECONDS,
        )
        # A fresh name every time, including for a guest that replaces a dropped
        # one: the predecessor's DELETE only moved it to ``destroying``, and a
        # name is unique among non-terminal sandboxes, so reusing the name would
        # make the replacement collide with the corpse it is replacing.
        sandbox_id = self._create(client, env, settings, auto_pause=auto_pause, name=_session_guest_name())
        with self._lock:
            self._sessions[token] = (sandbox_id, time.monotonic())
        return sandbox_id

    def _is_running(self, client: httpx.Client, sandbox_id: str) -> bool:
        """Return True when the CreateOS sandbox reports status "running"."""
        try:
            data = self._unwrap(client.get(f"/v1/sandboxes/{sandbox_id}"))
        except (httpx.HTTPError, SandboxExecutionError):
            return False
        return data.get("status") == "running"

    def _drop_session(self, client: httpx.Client, token: str) -> None:
        """Forget one session's guest and its lock, then destroy the guest."""
        with self._lock:
            entry = self._sessions.pop(token, None)
            # The lock goes with the session. The identity encodes the policy
            # as well as the flow and the user, so leaving it behind means one
            # permanent entry per tenant AND per policy change -- _sessions is
            # bounded by the idle reaper, this map would not be.
            #
            # Safe to delete while the caller still holds the lock object: a
            # concurrent _session_lock() call simply creates a fresh one, and
            # the two can only be handed out once no _sessions entry remains,
            # which is exactly when there is no guest left to serialize on.
            self._session_locks.pop(token, None)
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
        """Destroy every session guest this process is still holding."""
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
        """Create one guest and prove the control plane stored the policy we asked for."""
        shape = self._shape_for(settings.memory_mb)
        egress = self._egress_for(settings)
        # Keys must be declared at create time; a key introduced on the exec
        # call alone is rejected by the control plane.
        envs = {key: str(value) for key, value in (env or {}).items()}
        rootfs = _rootfs()
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
            # No name-collision branch. A session name is fresh random hex per
            # create, so a 409 here is not another worker holding this session's
            # guest -- it is the control plane rejecting the request, and
            # _unwrap turns it into the error it is.
            created = self._unwrap(client.post("/v1/sandboxes", json=body))
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
        try:
            # Control-plane value, so untrusted. A non-iterable echo raises
            # TypeError outside the mapped error tree, which skips the
            # caller's teardown handler and leaks the VM. An echo this code
            # cannot read is a failed verification, not a crash.
            mismatch = echoed is None or sorted(map(str, echoed)) != sorted(egress)
        except TypeError:
            mismatch = True
        if mismatch:
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
        """Upload the code file, run it, and attach artifacts and metrics.

        Returns:
            SandboxResult: The outcome of the run, with artifacts attached
                when collection is enabled.
        """
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
        if result.exit_code == _EXIT_CODE_TIMEOUT:
            # Nothing else is worth doing to a guest whose deadline just passed.
            #
            # The program was not stopped by this process -- closing the stream
            # only asks the server to kill it, which it does on its next
            # heartbeat -- so it is very likely still running and still writing.
            # An artifact pass would run a `tar` alongside it and hand back a
            # half-written archive as if it were the run's output, and both
            # calls are round trips that stand between the timeout and the
            # teardown that is the one kill this process can actually issue.
            #
            # So return immediately. The caller destroys the guest next (a
            # throwaway one in its `finally`, a session one because a timeout
            # taints it), which is what stops the program.
            logger.debug("CreateOS execution timed out; skipping artifacts and metrics to tear the guest down")
            return result
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
        # Two limits, and they are not the same number. `deadline` is the
        # operator's wall clock for the guest program; `budget` is how long the
        # transport waits, and it is deliberately the longer of the two so the
        # deadline below is what fires, on the configured second, rather than a
        # transport timeout some seconds later. Clamped at zero because httpx
        # rejects a negative timeout, while the loop reads any past deadline as
        # "already expired".
        budget = _exec_transport_budget(settings.timeout_seconds)
        started = time.monotonic()
        deadline = started + settings.timeout_seconds
        stdout = _BoundedOutput(_CREATEOS_MAX_OUTPUT_BYTES)
        stderr = _BoundedOutput(_CREATEOS_MAX_OUTPUT_BYTES)
        exit_code: int | None = None

        try:
            with client.stream(
                "POST",
                f"/v1/sandboxes/{sandbox_id}/exec",
                params={"stream": "true"},
                json={"cmd": _CREATEOS_GUEST_SHELL, "args": ["-c", self._guest_command(code_path, settings)]},
                timeout=self._timeout(max(budget, 0.0)),
            ) as response:
                if response.status_code != httpx.codes.OK:
                    response.read()
                    self._unwrap(response)  # raises with the mapped error class
                for line in response.iter_lines():
                    if time.monotonic() > deadline:
                        # Leaving the block closes the connection, which is the
                        # signal that kills the guest command. Checked before
                        # the line is parsed, so a guest that keeps printing
                        # cannot push the deadline out by staying chatty.
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

        if stdout.truncated or stderr.truncated:
            logger.warning("CreateOS guest output exceeded %d bytes and was truncated", _CREATEOS_MAX_OUTPUT_BYTES)
        return SandboxResult(
            stdout=stdout.text(),
            stderr=stderr.text(),
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
