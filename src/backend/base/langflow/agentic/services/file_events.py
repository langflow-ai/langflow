"""Per-request event queue for filesystem-tool side effects.

The document_assistant flow wraps the ``FileSystemToolComponent`` write/edit
tools so that, on success, they push a payload describing the touched file
into this queue. ``assistant_service`` drains the queue between LLM tokens
and forwards each entry to the SSE client as a ``file_written`` event.

Mirrors ``lfx.mcp.flow_builder_tools._flow_events_var`` but kept separate so
file consumers don't have to import flow-builder internals.

Security: the queue payload MUST carry a path relative to the user's sandbox
root — never the absolute filesystem path. ``emit_file_event`` enforces this
at the boundary so a misbehaving wrapper cannot leak ``BASE_DIR`` or the
per-user namespace hash.
"""

from __future__ import annotations

import contextvars
import json
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.tools import StructuredTool

logger = logging.getLogger(__name__)

# ContextVar is per-request — concurrent SSE sessions stay isolated.
# Default=None lazily allocates the deque on first access in the current
# context so contexts created by ``copy_context().run(...)`` get their own
# instance rather than sharing the parent's deque object.
_file_events_var: contextvars.ContextVar[deque[dict[str, Any]] | None] = contextvars.ContextVar(
    "_file_events_var",
    default=None,
)


def _get_file_events() -> deque[dict[str, Any]]:
    queue = _file_events_var.get()
    if queue is None:
        queue = deque()
        _file_events_var.set(queue)
    return queue


def emit_file_event(*, action: str, path: str, size: int, content: str | None = None) -> None:
    """Push a file-touched event onto the per-request queue.

    Args:
        action: Tool name that produced the side effect — ``"write_file"`` or
            ``"edit_file"``. Must be non-empty.
        path: Path relative to the user's sandbox root (e.g. ``"DOCS.md"``,
            ``"reports/2026.md"``). Absolute paths and Windows drive letters
            are refused — emitting them would leak sandbox internals to the
            SSE consumer.
        size: File size in bytes after the operation. Must be non-negative.
        content: The file's final text content. When non-None, the frontend
            renders it inline (no extra HTTP fetch) — keeps the surface tiny
            and avoids round-tripping data we already have in this request.
            Pass None for binary writes or when content shouldn't be shipped
            (e.g., oversize files).
    """
    if not action:
        msg = "emit_file_event: action must be non-empty"
        raise ValueError(msg)
    if not path:
        msg = "emit_file_event: path must be non-empty"
        raise ValueError(msg)
    if path.startswith(("/", "\\")) or _has_drive_letter(path):
        msg = f"emit_file_event: path must be relative to the sandbox root, got absolute path: {path!r}"
        raise ValueError(msg)
    if size < 0:
        msg = f"emit_file_event: size must be non-negative, got {size}"
        raise ValueError(msg)
    payload: dict[str, Any] = {"action": action, "path": path, "size": size}
    if content is not None:
        payload["content"] = content
    _get_file_events().append(payload)


def drain_file_events() -> list[dict[str, Any]]:
    """Return and clear all pending file events for the current context.

    Returns an empty list when nothing has been emitted in this context.
    Crucially, this path does NOT lazily allocate a deque: doing so would
    cause a drain call in the parent context to write a shared deque into
    the ContextVar, which child tasks would then inherit and mutate
    in lockstep — breaking the per-task isolation contract.
    """
    queue = _file_events_var.get()
    if queue is None:
        return []
    drained = list(queue)
    queue.clear()
    return drained


def reset_file_events() -> None:
    """Allocate a fresh queue in the current context for this request.

    Sets the ContextVar to a **new empty deque** so that any child task
    spawned by this request (the agent's LLM call, the wrapped tool
    invocations) inherits this same deque by reference through Python's
    context-copy semantics. Emits in the children become visible to the
    drain calls back here in the parent.

    Cross-request isolation is provided by Starlette/FastAPI giving each
    incoming HTTP request its own task context — different request tasks
    get independent deque instances. Concurrent ``asyncio.gather`` within
    a SINGLE request intentionally shares the deque (mirrors the proven
    ``flow_builder_tools._flow_events_var`` pattern).
    """
    _file_events_var.set(deque())


_DRIVE_LETTER_PREFIX_LEN = 2


def _has_drive_letter(path: str) -> bool:
    r"""Detect a Windows-style drive-letter prefix (e.g. ``C:\`` or ``C:/``).

    Returns True for ``C:foo``, ``C:\foo``, ``c:/foo``; False for ``foo:bar``
    (which has a colon mid-path but no drive-letter shape).
    """
    return len(path) >= _DRIVE_LETTER_PREFIX_LEN and path[1] == ":" and path[0].isalpha()


def wrap_file_tool_with_event(tool: StructuredTool, *, action: str) -> StructuredTool:
    """Wrap a ``FileSystemToolComponent`` StructuredTool to emit ``file_written``.

    The wrapper calls the original ``func`` (which keeps all sandbox checks,
    O_NOFOLLOW writes, deny-list, hardlink guard, etc. in
    ``FileSystemToolComponent``); on a success response it parses the JSON and
    emits a ``file_written`` event onto the per-request queue. The event
    carries the file's text content so the frontend can render it inline —
    no second HTTP round-trip needed. Failures (responses with an ``"error"``
    key) and unparseable responses are passed through unchanged and emit
    nothing — so a refused path traversal cannot enqueue a stale event.

    Args:
        tool: A ``StructuredTool`` produced by ``FileSystemToolComponent._get_tools()``.
        action: The event ``action`` string (``"write_file"`` or ``"edit_file"``).
            Forwarded verbatim into the emitted event payload.

    Returns:
        A new ``StructuredTool`` with the same ``name``/``description``/
        ``args_schema``/``tags`` but a wrapped ``func``.
    """
    # Defer the langchain import to runtime — this module is otherwise pure
    # stdlib and we don't want the dependency at import time of every service
    # that touches file_events.
    from langchain_core.tools import StructuredTool as _StructuredTool

    original_func = tool.func
    if original_func is None:
        msg = f"wrap_file_tool_with_event: tool {tool.name!r} has no .func to wrap (async-only tools are not supported)"
        raise TypeError(msg)

    def _wrapped(**kwargs: Any) -> str:
        # The langchain StructuredTool always calls its ``func`` with kwargs
        # parsed by ``args_schema``. We forward unchanged.
        result_json = original_func(**kwargs)
        # For write_file the content was passed in via kwargs (the LLM
        # supplied it). For edit_file we don't have the final content here
        # — we'd need to re-read from disk; current frontend gracefully
        # handles missing content by hiding the preview.
        kwarg_content = kwargs.get("content") if action == "write_file" else None
        _maybe_emit_from_response(result_json, action=action, content=kwarg_content)
        return result_json

    return _StructuredTool.from_function(
        name=tool.name,
        description=tool.description,
        func=_wrapped,
        args_schema=tool.args_schema,
        tags=getattr(tool, "tags", None),
    )


def _maybe_emit_from_response(
    result_json: str,
    *,
    action: str,
    content: str | None = None,
) -> None:
    """Emit ``file_written`` if the FileSystemTool response represents a success.

    Decision matrix (silent no-op for anything that isn't an unambiguous success):
        - non-JSON response             → no emit
        - non-dict JSON                  → no emit
        - dict with ``error`` key        → no emit
        - dict missing ``path``          → no emit
        - dict with absolute ``path``    → no emit (``emit_file_event`` refuses
                                            it; logged at WARNING so we notice
                                            if FileSystemTool ever changes the
                                            response contract)

    The caller (the wrapper) never raises out of this helper — the LLM should
    still see the underlying response and react to errors itself.
    """
    try:
        payload = json.loads(result_json)
    except (ValueError, TypeError):
        return
    if not isinstance(payload, dict):
        return
    if "error" in payload:
        return
    path = payload.get("path")
    if not isinstance(path, str) or not path:
        return
    size_raw = payload.get("bytes_written", 0)
    try:
        size = max(0, int(size_raw))
    except (TypeError, ValueError):
        size = 0
    try:
        emit_file_event(action=action, path=path, size=size, content=content)
    except ValueError:
        # emit_file_event refused (e.g., absolute path). Log so an unexpected
        # FileSystemTool response shape surfaces in operator dashboards, but
        # do not propagate — the LLM has the underlying response and we don't
        # want to break the tool call.
        logger.warning(
            "file_events.emit_refused",
            extra={"action": action, "path_repr": repr(path)[:200]},
        )
        return
    logger.info("file_events.emit %s path=%s size=%d has_content=%s", action, path, size, content is not None)
