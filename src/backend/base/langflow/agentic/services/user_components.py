"""Privileged registry for user-generated Component classes.

When the Layer-2 validation in ``assistant_service`` confirms a generated
``Component`` subclass passes both static AST and pydantic-runtime checks,
the code is persisted into the user's FS sandbox at::

    <BASE>/users/<hash>/.components/<ClassName>.py     # AUTO_LOGIN=False
    <BASE>/shared/.components/<ClassName>.py           # AUTO_LOGIN=True

The reserved-segment guard (`.components` in ``RESERVED_SEGMENTS``) keeps
the agent's 5 FileSystem tools from reading or writing this directory —
only THIS helper may do so. That asymmetry is the security boundary:
arbitrary code from the agent's runtime side never lands in the namespace
that the registry overlay will later import and execute.

Reuses the FileSystemToolComponent's existing primitives instead of
duplicating them:
    - sandbox resolution (`_validate_root`)
    - per-user HMAC-SHA256 hash with stored pepper
    - AUTO_LOGIN dispatch and refusal-without-user
    - cross-platform path / name validation

What's added on top:
    - ``ClassName`` validation (filesystem-portable + module-importable).
    - Atomic write (tmp file + os.replace) so a crash mid-write never
      leaves a half-file the registry loader would crash on.
    - Size cap to catch runaway model outputs / abuse.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from pathlib import Path

from lfx.components.files_and_knowledge.filesystem import (
    FileSystemToolComponent,
    _check_windows_portability,
)

# A generated Component class is well under 1 MB in practice. Anything
# above that is almost certainly an attack or a runaway model output.
MAX_COMPONENT_SOURCE_BYTES = 1 * 1024 * 1024

# Windows-portability cap on the ClassName segment of the on-disk path.
#
# The full path is
#     <BASE_DIR>/users/<32-hex-hash>/.components/<ClassName>.py
# On Windows the legacy MAX_PATH is 260 chars and the default-installed
# OS does NOT have long-path support enabled. With a deep BASE_DIR like
# ``C:\Users\<long-username>\AppData\Local\langflow\fs_tool\fs_sandbox``
# (~70 chars), the fixed portion (``users\<hash>\.components\.py``) eats
# ~50 chars. Capping ClassName at 64 leaves ~75 chars of headroom — safe
# even under pathological host paths, and well above what any realistic
# Python class name needs.
MAX_CLASS_NAME_LENGTH = 64

# Mirrors Python identifier rules. We additionally require the first
# character to be an uppercase letter (PEP 8 class naming) so the file
# stem also reads naturally as a module-style name in the registry loader.
_CLASS_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9_]*$")

# Filesystem-only refusals on top of the identifier regex above. The
# regex already forbids dots, slashes, NUL, control chars, and the
# Windows-forbidden punctuation, but a few names like ``CON`` /
# ``NUL`` are valid Python identifiers AND Windows reserved devices.
_WINDOWS_RESERVED_DEVICES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)


class UserComponentError(ValueError):
    """Raised when a user-component registration is refused.

    All refusals are this single class so callers can match on one
    boundary type. The message is safe for surfacing to the user (no
    internal paths, no stack traces).
    """


def register_user_component(*, user_id: str | None, class_name: str, code: str) -> Path:
    """Persist ``code`` as ``<class_name>.py`` under the user's sandbox.

    Returns the absolute path of the written file. Raises
    ``UserComponentError`` on any input validation failure, no-user
    refusal, or write failure (atomic — partial files are removed).
    """
    _validate_class_name(class_name)
    _validate_code(code)

    components_dir = _resolve_components_dir(user_id=user_id)
    target = components_dir / f"{class_name}.py"
    _atomic_write_text(target, code)
    return target


def register_user_component_if_valid(*, user_id: str | None, class_name: str | None, code: str | None) -> Path | None:
    """Best-effort wrapper for the streaming-loop hook.

    Wraps ``register_user_component`` with two policies the orchestrator
    needs:

    1. **Swallow input refusals** (``UserComponentError``). The component
       code was already streamed to the chat by the time we reach this
       hook; failing the user's request because the auto-registration
       step refused a bad class name or empty body would be hostile.
       Returns ``None`` in that case so the caller's stream can finish
       cleanly.

    2. **Propagate genuine errors.** Disk full, permission denied,
       pepper corruption — those are observability concerns; let them
       bubble so monitors fire.

    Returns the on-disk path on success, ``None`` if the input was
    refused or the user_id/class_name are missing.
    """
    if not user_id or not class_name or not code:
        return None
    try:
        return register_user_component(user_id=user_id, class_name=class_name, code=code)
    except UserComponentError:
        return None


def clear_user_components(*, user_id: str | None) -> int:
    """Wipe every ``*.py`` file under the user's ``.components/`` dir.

    Called by ``POST /api/v1/agentic/sessions/reset`` whenever the
    frontend declares a "new session" boundary (fresh panel mount or
    explicit New session click). Components are session-scoped from the
    user's perspective; persisting them across sessions would surprise
    users who don't expect "I generated SumComponent last week" to
    survive a New session click.

    Semantics:
        - **Per-user isolated** by the existing sandbox hash.
        - **Idempotent** — empty dir or missing user namespace → 0.
        - **Targeted** — only ``*.py`` files in ``.components/`` are
          removed. Sibling files (planted by some other path) and the
          ``.components/`` directory itself are preserved so the
          loader's walk stays simple on the next register call.
        - **Silent on no-user** — AUTO_LOGIN=False + ``user_id=None``
          returns 0 instead of raising, mirroring the
          ``register_user_component_if_valid`` contract used by the
          orchestration hook.

    Returns the number of files actually deleted.
    """
    if not user_id:
        # Mirror the FS tool's "no user → no namespace" semantics.
        # Resolve only if a real user is bound; otherwise the call is
        # a silent no-op (avoids leaking the sandbox refusal as an
        # exception out of a routine cleanup hook).
        components_dir = get_user_components_dir(user_id=None)
        if components_dir is None:
            return 0
    else:
        components_dir = get_user_components_dir(user_id=user_id)
        if components_dir is None:
            return 0

    if not components_dir.exists():
        return 0

    deleted = 0
    for entry in components_dir.iterdir():
        # Only sweep `.py` — defends against a future bug that plants
        # data files into the reserved segment; they stay until
        # explicit cleanup.
        if entry.is_file() and entry.suffix == ".py":
            try:
                entry.unlink()
            except OSError:
                # Permission denied / file vanished mid-walk: skip and
                # keep counting the rest. The next session reset will
                # try again.
                continue
            deleted += 1
    return deleted


def get_user_components_dir(*, user_id: str | None) -> Path | None:
    """Return the absolute path of the user's ``.components/`` directory.

    Returns ``None`` when AUTO_LOGIN=False and no user is bound (matching
    the FS tool's refusal semantics — the registry overlay simply skips
    its walk in that case rather than raising).
    """
    try:
        return _resolve_components_dir(user_id=user_id)
    except UserComponentError:
        return None


# ---------------------------------------------------------------------------
# internals
# ---------------------------------------------------------------------------


def _validate_class_name(class_name: str) -> None:
    if not class_name:
        msg = "class_name must be a non-empty string"
        raise UserComponentError(msg)
    # Windows-portability path-length cap. Checked BEFORE other rules so
    # the error message is specific and the rest of the validator never
    # has to reason about pathological inputs.
    if len(class_name) > MAX_CLASS_NAME_LENGTH:
        msg = f"class_name length {len(class_name)} exceeds max {MAX_CLASS_NAME_LENGTH} (Windows MAX_PATH safeguard)"
        raise UserComponentError(msg)
    # Filesystem-portability guard (rejects NUL, Windows-forbidden punct,
    # path separators, dotdot, control chars, trailing dot/space, etc.).
    if err := _check_windows_portability(class_name):
        raise UserComponentError(err)
    # Reject `.`, `..`, leading dots, leading underscores, dunders, and
    # anything that isn't a valid CamelCase identifier.
    if not _CLASS_NAME_RE.fullmatch(class_name):
        msg = (
            f"class_name must be a CamelCase identifier "
            f"(letters/digits/underscores, leading uppercase). Got: {class_name!r}"
        )
        raise UserComponentError(msg)
    if class_name.upper() in _WINDOWS_RESERVED_DEVICES:
        msg = f"class_name {class_name!r} is a Windows-reserved device name"
        raise UserComponentError(msg)


def _validate_code(code: str) -> None:
    if not code or not code.strip():
        msg = "code must be a non-empty string"
        raise UserComponentError(msg)
    encoded_size = len(code.encode("utf-8"))
    if encoded_size > MAX_COMPONENT_SOURCE_BYTES:
        msg = f"code size {encoded_size} bytes exceeds limit of {MAX_COMPONENT_SOURCE_BYTES} bytes"
        raise UserComponentError(msg)


def _resolve_components_dir(*, user_id: str | None) -> Path:
    """Resolve and create ``<sandbox>/.components/`` for the given user.

    Reuses the FS tool's authoritative sandbox resolver so the hash
    function, pepper handling, AUTO_LOGIN dispatch, and no-user refusal
    stay in one place. The reserved-segment guard does NOT apply here —
    this helper is the privileged writer that the guard is protecting.
    """
    component = FileSystemToolComponent()
    if user_id is not None:
        component._user_id = user_id  # noqa: SLF001 — privileged binding seam
    try:
        sandbox_root = component._validate_root()  # noqa: SLF001
    except PermissionError as exc:
        # PermissionError from _validate_root happens in two cases:
        # 1. AUTO_LOGIN=False and no user_id → translate to our domain error.
        # 2. Sandbox config / disk failure → re-wrap so callers see the
        #    same single-class refusal envelope.
        raise UserComponentError(str(exc)) from exc

    components_dir = sandbox_root / ".components"
    try:
        components_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        msg = f"Cannot create .components directory: {exc.strerror or exc}"
        raise UserComponentError(msg) from exc
    return components_dir


def _atomic_write_text(target: Path, text: str) -> None:
    """Write ``text`` to ``target`` via a tmp file + os.replace rename.

    On any failure, removes the tmp file so the directory never
    accumulates stray ``.tmp`` artifacts. ``os.replace`` is atomic on
    POSIX and on Windows (since Python 3.3) when source and dest are on
    the same filesystem — which they are here, both inside the user's
    sandbox.
    """
    # Use tempfile inside the SAME directory so os.replace stays
    # cross-device-safe (replace requires source+dest on the same FS).
    tmp_fd, tmp_name = tempfile.mkstemp(prefix=f"{target.stem}.", suffix=".py.tmp", dir=str(target.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(text)
        tmp_path.replace(target)
    except OSError as exc:
        # Clean up the tmp file (it might have data but is unreachable).
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        msg = f"Failed to write {target.name}: {exc.strerror or exc}"
        raise UserComponentError(msg) from exc
