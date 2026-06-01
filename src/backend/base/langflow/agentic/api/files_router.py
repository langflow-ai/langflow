"""HTTP endpoint that exposes files written by the agent's sandboxed FS tools.

The endpoint is the **only** path by which the frontend reads files the agent
materialized — it is therefore a security-critical surface. Every defense in
depth here delegates to ``FileSystemToolComponent`` rather than re-implementing
sandbox boundaries:

- Authentication: ``CurrentActiveUser`` (any unauthenticated request → 401).
- Path validation: a two-layer guard.
    1. **Pre-validation** in this module rejects the obvious shapes (absolute
       paths, drive letters, ``..`` components, null bytes, empty input)
       *before* any I/O is attempted. This avoids feeding malformed input to
       deeper layers where the failure mode may be subtler.
    2. **Sandbox boundary** is enforced by ``FileSystemToolComponent._validate_path``
       which performs ``Path.resolve()`` + ``is_relative_to(root)`` plus the
       deny-list / hardlink / O_NOFOLLOW guards already proven in the lfx
       sandbox test suite.
- Cross-user isolation: each request instantiates a fresh component bound to
  ``current_user.id`` so the resolved root is ``<base>/<hash(user_id)>/``.
  Another user's file is unreachable — the path resolves outside the requesting
  user's namespace and returns 404 (not 403, to avoid leaking namespace existence).
- Size / binary guards: enforced by ``FileSystemToolComponent._read_file`` —
  oversize → 413, binary → 415.
- Download mode: ``?download=true`` forces ``application/octet-stream`` and
  an ``attachment`` content disposition, so a returned ``.html`` / ``.svg`` /
  ``.js`` can never be inlined by the browser as page content (T7).

Audit log: every successful read emits ``agentic.files.read`` with the
``user_id``, the **relative** path, and the byte size — never the absolute
filesystem path.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

# CurrentActiveUser is a FastAPI Annotated[Depends(...)] alias — needs the
# runtime symbol so FastAPI can resolve the dependency. Cannot be moved into
# a TYPE_CHECKING block.
from langflow.api.utils.core import CurrentActiveUser  # noqa: TC001

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic", tags=["Agentic"])


_MAX_PATH_LENGTH = 1024
_DRIVE_LETTER_PREFIX_LEN = 2  # ``C:`` is the smallest detectable Windows-absolute prefix.


def _looks_like_drive_letter(path: str) -> bool:
    r"""``C:foo`` / ``c:\foo`` style — Windows-style absolute prefix."""
    return len(path) >= _DRIVE_LETTER_PREFIX_LEN and path[1] == ":" and path[0].isalpha()


def _is_unsafe_path_shape(path: str) -> bool:
    """Pre-validation: refuse shapes a relative-sandbox path could never have.

    These are checked **before** any filesystem call so a bad request cannot
    reach the deeper layers in an ambiguous state. The deeper sandbox check
    (``FileSystemToolComponent._validate_path``) is the source of truth for
    *boundary* enforcement; this layer rejects egregious shapes early.
    """
    if not path or len(path) > _MAX_PATH_LENGTH:
        return True
    if "\x00" in path:
        return True
    if path.startswith(("/", "\\")):
        return True
    if _looks_like_drive_letter(path):
        return True
    # Split on BOTH separators (Windows paths can use either). If any
    # component is exactly ``..``, refuse. A literal ``..`` filename is not
    # legitimate inside a sandboxed workspace — the agent's write_file
    # cannot create one either.
    parts = path.replace("\\", "/").split("/")
    return any(part == ".." for part in parts)


def _safe_filename_for_disposition(relative_path: str) -> str:
    """Return a basename safe to interpolate into ``Content-Disposition``.

    Strips quotes and control characters so the header value cannot be split
    or broken by an attacker-controlled filename.
    """
    base = Path(relative_path).name
    return "".join(ch for ch in base if ch.isprintable() and ch not in '"\r\n')


@router.get("/files")
async def get_file(
    *,
    current_user: CurrentActiveUser,
    path: Annotated[str, Query(min_length=1, max_length=_MAX_PATH_LENGTH)],
    download: Annotated[bool, Query()] = False,
) -> Response:
    """Return the contents of a sandboxed file as text (or as an attachment).

    Raises:
        HTTPException(400): The path shape is invalid (traversal, absolute,
            null byte, etc.). No I/O is attempted.
        HTTPException(404): The file does not exist in the requesting user's
            sandbox. Same status for sandbox-internal "not found" and for
            "path resolves outside the user namespace" — by design, to avoid
            leaking namespace existence to another tenant.
        HTTPException(413): The file is larger than ``MAX_FILE_SIZE_BYTES``.
        HTTPException(415): The file is binary (null byte in the first 8 KiB).
    """
    if _is_unsafe_path_shape(path):
        raise HTTPException(status_code=400, detail="Invalid path")

    # Deferred import: FileSystemToolComponent pulls a chunk of lfx — we don't
    # want every router-import path to do it eagerly. We use the **same**
    # security primitives the agent's tools use, not a parallel implementation.
    from lfx.components.files_and_knowledge.filesystem import (
        BINARY_SNIFF_BYTES,
        MAX_FILE_SIZE_BYTES,
        FileSystemToolComponent,
        _looks_binary,
        _read_bytes_no_follow,
        _read_head_no_follow,
    )

    fs = FileSystemToolComponent()
    fs._user_id = str(current_user.id)  # noqa: SLF001 — bind sandbox to caller
    # B1: this endpoint carries an authenticated user identity and must
    # always resolve a per-user sandbox root, even under AUTO_LOGIN=True
    # (otherwise two users on a shared deployment read the same `shared/`
    # tree). The agent's write tools set the same flag in build_toolkit so
    # write and read paths resolve to the SAME users/<hash>/ root.
    fs._force_isolation = True  # noqa: SLF001 — security: see filesystem._validate_root
    try:
        resolved = fs._validate_path(path)  # noqa: SLF001 — public sandbox entry
    except PermissionError as exc:
        # _validate_root / _validate_path raise PermissionError on sandbox
        # boundary violations (path escape, deny-list, etc.). Map to 404 so we
        # never leak namespace existence to another tenant.
        logger.warning(
            "agentic.files.read.refused user_id=%s path=%s reason=%s",
            current_user.id,
            path,
            exc,
        )
        raise HTTPException(status_code=404, detail="Not found") from None

    if not resolved.exists() or resolved.is_dir():
        logger.warning(
            "agentic.files.read.missing user_id=%s path=%s resolved=%s exists=%s is_dir=%s",
            current_user.id,
            path,
            resolved,
            resolved.exists(),
            resolved.is_dir(),
        )
        raise HTTPException(status_code=404, detail="Not found")

    try:
        size = resolved.stat().st_size
    except OSError:
        raise HTTPException(status_code=404, detail="Not found") from None
    if size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File too large")

    # Binary sniff before the full read — same heuristic the FS tool uses.
    try:
        head = _read_head_no_follow(resolved, BINARY_SNIFF_BYTES)
    except (OSError, PermissionError):
        raise HTTPException(status_code=404, detail="Not found") from None
    if _looks_binary(head):
        raise HTTPException(status_code=415, detail="Binary content not supported")

    try:
        body_bytes = _read_bytes_no_follow(resolved)
    except (OSError, PermissionError):
        raise HTTPException(status_code=404, detail="Not found") from None

    # Audit log — relative path only, never the absolute sandbox-resolved path.
    logger.info(
        "agentic.files.read user_id=%s path=%s size=%d download=%s",
        current_user.id,
        path,
        len(body_bytes),
        download,
    )

    if download:
        filename = _safe_filename_for_disposition(path) or "file"
        return Response(
            content=body_bytes,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return Response(content=body_bytes, media_type="text/plain; charset=utf-8")
