"""Backend-independent primitives shared by every sandbox backend.

Nothing here knows which backend is configured. It holds the result and error
types the callers see, the operator settings a backend must honor, and the
code normalization that has to be identical whichever backend runs the code.

Split out of the former single ``lfx/utils/sandbox.py`` module so a backend
can be added without editing shared code. See :mod:`lfx.utils.sandbox.registry`.
"""

from __future__ import annotations

import ast
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

    @property
    def success(self) -> bool:
        """Return True when the execution exited with code 0."""
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


@dataclass(frozen=True)
class _SandboxSettings:
    """Operator-tunable sandbox settings, with safe defaults for every field."""

    timeout_seconds: int = 30
    memory_mb: int = 192
    allow_network: bool = False
    allowed_domains: tuple[str, ...] = ()
    allow_software_emulation: bool = False


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
    )


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

    Every field defaults to the value that grants nothing, so a backend that
    omits one is refused rather than trusted. ``isolation`` is the field that
    matters most: ``_assert_backend_honours_policy`` accepts only
    ``"hardware-virtualized"``, and defaulting to it would let a plugin that
    never names its isolation clear the strongest gate by saying nothing.
    """

    # Deliberately not "hardware-virtualized". See the note above.
    isolation: str = "none"
    supports_deny_all_egress: bool = False
    supports_domain_allowlist: bool = False
    # Longest single execution the backend accepts, or None for no cap.
    max_timeout_seconds: int | None = None


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

    def run(self, code: str, *, env: dict[str, str] | None = None) -> SandboxResult:
        """Run ``code`` to completion and return its outcome.

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
