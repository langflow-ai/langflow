"""Backend-independent primitives shared by every sandbox backend.

Nothing here knows which backend is configured. It holds the result and error
types the callers see, the operator settings a backend must honor, and the
code normalization that has to be identical whichever backend runs the code.

Split out of the former single ``lfx/utils/sandbox.py`` module so a backend
can be added without editing shared code. See :mod:`lfx.utils.sandbox.registry`.
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# Mirrors langchain_experimental's PythonREPL.sanitize_input, which the
# in-process path applies before exec: strip a leading markdown fence /
# "python" language tag / backticks and trailing backticks-whitespace. The
# sandbox path must normalize identically or fenced LLM-generated code that
# runs in-process today would become a guest SyntaxError. Replicated here
# (two small regexes) so the sandbox path does not depend on
# langchain_experimental being installed.
_FENCE_PREFIX_RE = re.compile(r"^(\s|`)*(?i:python)?\s*")
_FENCE_SUFFIX_RE = re.compile(r"(\s|`)*$")

# The Python tokenizer's line-break set: \n, \r\n, \r. Deliberately narrower
# than str.splitlines(), which also breaks on U+2028/U+2029 etc. that Python
# source treats as ordinary characters inside string literals.
_SOURCE_NEWLINE_RE = re.compile(r"\r\n|\r|\n")


def sanitize_code(code: str) -> str:
    """Strip markdown fences/backticks the way PythonREPL.sanitize_input does."""
    return _FENCE_SUFFIX_RE.sub("", _FENCE_PREFIX_RE.sub("", code))


class SandboxExecutionError(RuntimeError):
    """Raised when a sandboxed execution fails for infrastructure reasons.

    Infrastructure failures (VM boot timeout, guest communication loss) are
    distinct from the user code failing — the latter is reported through
    :attr:`SandboxResult.exit_code` / :attr:`SandboxResult.stderr`, not an
    exception.
    """


class SandboxUnavailableError(SandboxExecutionError):
    """Raised when a sandbox backend is configured but cannot be used.

    Deliberately NOT caught by the components' fallback paths: a configured
    sandbox that cannot start must block execution (fail closed), not degrade
    to in-process ``exec``.
    """


# exec-sandbox reports these outcomes through exit_code instead of raising:
# -1 is a wall-clock timeout, 137 is SIGKILL (usually the guest OOM killer).
_EXIT_CODE_TIMEOUT = -1
_EXIT_CODE_KILLED = 137


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of one sandboxed execution."""

    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int | None = None
    # Files the code left in the guest's artifact directory. Empty unless the
    # operator enabled collection and the backend supports it.
    files: tuple[SandboxFile, ...] = ()

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def error_message(self) -> str:
        """A user-facing message for a failed execution (non-zero exit code)."""
        if self.exit_code == _EXIT_CODE_TIMEOUT:
            return "Sandboxed execution timed out (see LANGFLOW_SANDBOX_TIMEOUT_SECONDS)."
        if self.exit_code == _EXIT_CODE_KILLED:
            return (
                "Sandboxed execution was killed (exit code 137), typically because it "
                "exceeded the VM memory limit (see LANGFLOW_SANDBOX_MEMORY_MB)."
            )
        return self.stderr.strip() or f"Sandboxed execution failed with exit code {self.exit_code}"


# Session isolation is off unless the operator turns it on. Reusing one guest
# across executions is faster and lets state survive, but it also lets one
# execution read what the previous one left behind, so it must be a decision
# rather than a default.
SESSION_MODE_OFF = "off"
SESSION_MODE_FLOW = "flow"
KNOWN_SESSION_MODES = (SESSION_MODE_OFF, SESSION_MODE_FLOW)


@dataclass(frozen=True)
class _SandboxSettings:
    timeout_seconds: int = 30
    memory_mb: int = 192
    allow_network: bool = False
    allowed_domains: tuple[str, ...] = ()
    allow_software_emulation: bool = False
    session_mode: str = SESSION_MODE_OFF
    session_idle_seconds: int = 600
    collect_artifacts: bool = False
    max_artifact_bytes: int = 5 * 1024 * 1024


def _sandbox_settings() -> _SandboxSettings:
    """Read the sandbox tuning settings, defaulting when the settings stack is absent."""
    defaults = _SandboxSettings()
    try:
        from lfx.services.deps import get_settings_service

        settings_service = get_settings_service()
    except ImportError:
        return defaults
    if settings_service is None:
        return defaults
    settings = settings_service.settings
    return _SandboxSettings(
        timeout_seconds=getattr(settings, "sandbox_timeout_seconds", defaults.timeout_seconds),
        memory_mb=getattr(settings, "sandbox_memory_mb", defaults.memory_mb),
        allow_network=getattr(settings, "sandbox_allow_network", defaults.allow_network),
        allowed_domains=tuple(getattr(settings, "sandbox_allowed_domains", ()) or ()),
        allow_software_emulation=getattr(
            settings, "sandbox_allow_software_emulation", defaults.allow_software_emulation
        ),
        session_mode=getattr(settings, "sandbox_session_mode", defaults.session_mode),
        session_idle_seconds=getattr(settings, "sandbox_session_idle_seconds", defaults.session_idle_seconds),
        collect_artifacts=getattr(settings, "sandbox_collect_artifacts", defaults.collect_artifacts),
        max_artifact_bytes=getattr(settings, "sandbox_max_artifact_bytes", defaults.max_artifact_bytes),
    )


@dataclass(frozen=True)
class SessionKey:
    """Identifies the guest that a run may reuse.

    Deliberately not a plain string. A caller-supplied string would let two
    unrelated flows, or two users of the same flow, name the same guest and
    read each other's leftover state. The identity fields are the input and
    :meth:`token` is the only thing a backend ever sees, so the guest name can
    never be chosen by a caller.
    """

    flow_id: str
    user_id: str

    def token(self) -> str:
        """A stable, opaque id for this (flow, user) pair.

        Hashed rather than concatenated so a backend cannot reconstruct the
        flow or user id from a VM name it stores or logs.
        """
        digest = hashlib.sha256(f"{self.flow_id}\x00{self.user_id}".encode())
        return digest.hexdigest()[:32]


@dataclass(frozen=True)
class SandboxFile:
    """One file the sandboxed code produced, read back into the host process."""

    path: str
    content: bytes

    @property
    def size(self) -> int:
        return len(self.content)


# Where a session's carried-over variables live inside the guest.
_SESSION_STATE_PATH = "/workspace/.lf_session_state.pkl"

# Largest single value carried from one execution to the next. Bounds both the
# time spent serializing and the disk a forgotten session holds. A value over
# the limit is simply not carried; the execution that created it is unaffected.
_SESSION_MAX_VALUE_BYTES = 4 * 1024 * 1024

# Prepended to the user's code when a session is active.
#
# Reusing a guest preserves its FILESYSTEM, not the Python process: each
# execution is a new interpreter, so module-level variables would be gone even
# though the VM is the same. Verified against a live sandbox -- ``state = 41``
# followed by ``print(state)`` raised NameError until this existed.
#
# This carries the variables across instead. It is a small preamble rather than
# a runner script or a long-lived kernel process:
#
# * ``atexit`` runs the save on a normal exit AND on ``sys.exit``, and on an
#   uncaught exception, so no ``try``/``finally`` has to wrap (and re-indent)
#   the user's code.
# * Only picklable values are carried. Anything else -- an open socket, a file
#   handle, a lambda -- is skipped rather than failing the run.
# * Everything it defines is ``_lf_``-prefixed and excluded from the save, so
#   the machinery never leaks into the next execution's namespace.
#
# Each value is serialized SEPARATELY, into a mapping of name to bytes, and the
# file holds one pickle of that mapping. The obvious alternative -- pickle the
# whole namespace as a single object -- loses everything to one bad entry, and
# ordinary code produces such entries: a function defined by the user pickles
# cleanly by reference to ``__main__.fn``, but the next execution is a fresh
# interpreter where that name does not exist yet, so the load fails and takes
# every other variable with it. With per-entry bytes the outer mapping is only
# str to bytes, which always loads, and a failing entry costs just itself.
#
# A name that cannot be carried is reported on stderr rather than dropped in
# silence, so a session that quietly stopped carrying something is visible.
#
# The pickle is written and read entirely inside the guest. It never crosses
# into the Langflow process, so it grants code that is already running
# arbitrarily in that guest no capability it did not have.
def _build_session_preamble(state_path: str) -> str:
    """The preamble text, parameterized only so a test can point it at a writable path."""
    return f"""\
import atexit as _lf_atexit, os as _lf_os, pathlib as _lf_pathlib, pickle as _lf_pickle, sys as _lf_sys
_lf_state = _lf_pathlib.Path({state_path!r})
_lf_lost = []
if _lf_state.exists():
    try:
        _lf_entries = _lf_pickle.loads(_lf_state.read_bytes())
    except Exception:
        _lf_entries = {{}}
    if isinstance(_lf_entries, dict):
        for _lf_name, _lf_blob in _lf_entries.items():
            try:
                globals()[_lf_name] = _lf_pickle.loads(_lf_blob)
            except Exception:
                _lf_lost.append(_lf_name)
    if _lf_lost:
        print(
            "langflow session: could not restore " + ", ".join(sorted(_lf_lost)),
            file=_lf_sys.stderr,
        )


def _lf_save_state():
    _lf_keep = {{}}
    _lf_dropped = []
    for _lf_name, _lf_value in list(globals().items()):
        if _lf_name.startswith("_lf_") or _lf_name.startswith("__"):
            continue
        # Defined by this run, so it pickles by reference to a __main__
        # attribute the next interpreter will not have. Skipped here rather
        # than left to fail on every future restore.
        if getattr(_lf_value, "__module__", None) == "__main__":
            _lf_dropped.append(_lf_name)
            continue
        try:
            _lf_blob = _lf_pickle.dumps(_lf_value)
        except Exception:
            _lf_dropped.append(_lf_name)
            continue
        if len(_lf_blob) > {_SESSION_MAX_VALUE_BYTES}:
            _lf_dropped.append(_lf_name)
            continue
        _lf_keep[_lf_name] = _lf_blob
    # Written to a private temporary name and renamed into place. A session
    # guest can be shared by more than one worker, so a plain write could be
    # read half-finished by an execution starting on another worker; a rename
    # is atomic, making the loser of that race a whole older state rather than
    # a torn file.
    _lf_tmp = _lf_state.with_name(_lf_state.name + "." + str(_lf_os.getpid()) + ".tmp")
    try:
        _lf_tmp.write_bytes(_lf_pickle.dumps(_lf_keep))
        _lf_os.replace(_lf_tmp, _lf_state)
    except Exception:
        try:
            _lf_tmp.unlink()
        except Exception:
            pass
        print("langflow session: could not save state", file=_lf_sys.stderr)
        return
    if _lf_dropped:
        print(
            "langflow session: did not carry " + ", ".join(sorted(_lf_dropped)),
            file=_lf_sys.stderr,
        )


_lf_atexit.register(_lf_save_state)
"""


def compose_session_code(code: str, *, state_path: str = _SESSION_STATE_PATH) -> str:
    """Wrap ``code`` so its variables survive into the next execution.

    Applied only when a session is active. The preamble goes through the same
    placement rules as the import preamble, so a leading docstring or
    ``from __future__`` block still comes first.

    ``state_path`` is the guest path holding the carried values. It is a
    constant in production; the parameter exists so a test can run the same
    preamble against a writable path instead of /workspace.
    """
    return _compose_sandbox_code(_build_session_preamble(state_path), code)


def build_import_preamble(global_imports: str | list[str]) -> str:
    """Translate the components' ``Global Imports`` field into import statements.

    In-process execution imports these modules on the host and injects them
    into the exec globals; in sandbox mode the equivalent is a plain import
    preamble that runs inside the guest VM. A module missing from the guest
    image surfaces as an ImportError in the sandboxed stderr.
    """
    if isinstance(global_imports, str):
        modules = [module.strip() for module in global_imports.split(",") if module.strip()]
    elif isinstance(global_imports, list):
        modules = [str(module).strip() for module in global_imports if str(module).strip()]
    else:
        msg = "global_imports must be either a string or a list"
        raise TypeError(msg)
    for module in modules:
        # Modules become import statements in generated code, so restrict to
        # dotted-identifier names to keep code injection out of the preamble.
        if not all(part.isidentifier() for part in module.split(".")):
            msg = f"Invalid module name in Global Imports: {module!r}"
            raise ValueError(msg)
    return "\n".join(f"import {module}" for module in modules)


def _compose_sandbox_code(preamble: str, code: str) -> str:
    """Join the import preamble and user code without breaking future imports.

    ``from __future__ import ...`` must be the first statement after an
    optional module docstring, so naively prepending the preamble would turn
    valid user code into a SyntaxError. Insert the preamble after any leading
    docstring/future-import block instead. If the user code does not parse,
    return the naive concatenation — the guest surfaces the same SyntaxError
    the user would get anyway.
    """
    if not preamble:
        return code
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return f"{preamble}\n{code}"
    idx = 0
    body = tree.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        idx = 1
    while idx < len(body) and isinstance(body[idx], ast.ImportFrom) and body[idx].module == "__future__":
        idx += 1
    if idx == 0:
        return f"{preamble}\n{code}"
    if idx >= len(body):
        # Only a docstring/future block — nothing runs after the preamble.
        return f"{code}\n{preamble}"
    # Split at the exact (line, column) start of the first real statement, not
    # at a line boundary: semicolon-joined code like
    # ``from __future__ import annotations; print(math.pi)`` would otherwise
    # keep user statements on the hoisted line and run them before the
    # preamble's imports.
    first_tail = body[idx]
    # Line starts must use the tokenizer's newline semantics (\n, \r\n, \r) —
    # NOT str.splitlines(), which also breaks on U+2028/U+2029 and friends
    # that Python source treats as ordinary characters inside strings; a
    # docstring containing U+2028 would otherwise shift every subsequent
    # offset and drop the preamble inside the docstring.
    line_start = 0
    for _ in range(first_tail.lineno - 1):
        match = _SOURCE_NEWLINE_RE.search(code, line_start)
        if match is None:  # pragma: no cover - AST linenos always fit the source
            break
        line_start = match.end()
    # ast col_offset counts UTF-8 BYTES, not characters — slicing the string
    # with it directly would split mid-identifier after any non-ASCII text
    # (e.g. an accented docstring). Convert via a byte-slice round-trip; AST
    # offsets always fall on character boundaries so the decode is safe.
    col_chars = len(code[line_start:].encode("utf-8")[: first_tail.col_offset].decode("utf-8"))
    offset = line_start + col_chars
    head, tail = code[:offset], code[offset:]
    # head ends mid-line in the semicolon-joined case; add the newline only
    # then (a trailing semicolon before a newline is valid Python).
    separator = "" if head.endswith("\n") else "\n"
    return f"{head}{separator}{preamble}\n{tail}"


@dataclass(frozen=True)
class Capabilities:
    """What a backend claims it can enforce.

    The backend declares. The dispatcher decides (see
    ``_assert_backend_honours_policy``). A backend never gets to approve its
    own policy, so a third-party backend cannot grant itself an exemption from
    an operator's setting.

    Describes what the backend CAN do, not what the current settings ask for.
    A backend that offers an explicit "run without hardware isolation" opt-out
    still reports ``hardware-virtualized`` here and enforces that opt-out
    itself, because the opt-out is the operator's decision rather than a limit
    of the backend.
    """

    isolation: str = "hardware-virtualized"
    supports_deny_all_egress: bool = False
    supports_domain_allowlist: bool = False
    # Longest single execution the backend accepts, or None for no cap.
    max_timeout_seconds: int | None = None
    # Whether the backend can keep one guest alive across executions of the
    # same SessionKey. A backend without this runs every execution cold.
    supports_sessions: bool = False
    # Whether the backend can read files back out of the guest after a run.
    supports_artifacts: bool = False
    # Destinations the backend cannot block even when egress is denied. Honesty
    # field: it exists so a hole has to be declared rather than discovered.
    # Logged once per process when non-empty.
    egress_exceptions: tuple[str, ...] = ()


@runtime_checkable
class SandboxBackend(Protocol):
    """One way to run user code under isolation.

    Implementations are process-wide singletons built lazily by the registry.
    ``run`` is called from arbitrary threads, so an implementation owns its own
    synchronization.
    """

    name: str

    def capabilities(self) -> Capabilities:
        """Declare what this backend enforces. Must not perform I/O."""
        ...

    def run(self, code: str, *, env: dict[str, str] | None = None, session: SessionKey | None = None) -> SandboxResult:
        """Run ``code`` to completion and return its outcome.

        ``session`` asks the backend to reuse the guest it used for the same
        key last time. A backend that reports ``supports_sessions=False``
        ignores it and runs cold, which is always safe: reuse is an
        optimization, never a correctness requirement.

        Raises:
            SandboxUnavailableError: The backend is configured but unusable, or
                cannot honor the operator's policy. Fail closed.
            SandboxExecutionError: The infrastructure failed mid-run.
        """
        ...

    def shutdown(self) -> None:
        """Release process-wide resources. Must be safe to call repeatedly."""
        ...

    def reset_after_fork(self) -> None:
        """Rebuild synchronization state in a freshly forked child.

        Called in the child's single-threaded post-fork window. Any mutex held
        by another thread at fork time is inherited locked with no owner, so it
        must be replaced rather than reused.
        """
        ...
