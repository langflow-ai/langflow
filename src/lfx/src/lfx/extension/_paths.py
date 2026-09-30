"""Shared path-safety primitives used by every extension walker.

Centralises the directory-name skip list and the resolve-and-relative-to
containment check.  Every loader / discovery layer that follows a filesystem
walk must import these symbols rather than reimplementing them, so a
tightening (e.g. adding ``.tox`` to ``SKIP_DIR_NAMES`` or making
``is_within`` stricter about symlinked roots) lands everywhere at once.

Why: the trust-boundary check was reimplemented at least three times with
subtly different strictness (loader orchestrator, per-file re-resolve,
seed walker).  The drift between them caused a real security gap
(symlinked seed subdirectories slipped past one walker while the others
caught them).  This module is the single audited source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

SKIP_DIR_NAMES: frozenset[str] = frozenset({"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache"})
"""Directory names skipped by every extension filesystem walker.

A path component matching one of these names is treated as build/cache
detritus and not traversed.  The check is component-name only -- it
does not look inside the directory."""


def is_within(child: Path, root: Path) -> bool:
    """Return True iff ``child`` (after resolution) is the same as or under ``root``.

    Both operands are resolved with ``strict=False`` so a still-being-created
    path (or a vanished one in a TOCTOU race) returns a deterministic answer
    instead of raising.  A symlink whose target lies outside ``root`` returns
    False, which is the trust-boundary check the extension subsystem relies
    on to refuse symlink-escape.

    The implementation uses ``Path.relative_to`` rather than string-prefix
    matching so ``/a/bb`` is correctly rejected against root ``/a/b``.
    """
    try:
        resolved_child = child.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
    except OSError:
        return False
    try:
        resolved_child.relative_to(resolved_root)
    except ValueError:
        return False
    return True
