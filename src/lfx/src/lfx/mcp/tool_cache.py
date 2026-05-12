"""Per-request result cache for pure-read MCP tools.

The Langflow Assistant's flow-builder agent often re-invokes the same
read-only tool with identical args inside a single build session — e.g.
``describe_component("ChatInput")`` called multiple times while wiring a
graph, or ``search_components("LLM")`` issued from successive planning
turns. Caching these calls within the request shaves real cost (fewer
component-registry walks, fewer token-laden tool results in the LLM
context window) without changing observable behavior.

Scope is **per request**:
    - The cache lives in a ``contextvars.ContextVar`` so concurrent
      assistant requests (different SSE sessions, different users) never
      see each other's entries.
    - ``reset_tool_cache()`` is called by ``assistant_service`` at the
      start of every request, alongside ``reset_working_flow()``.
    - Child contexts spawned via ``copy_context()`` (e.g. ``asyncio.gather``
      tasks) get their own fresh cache. The lazy-allocate-on-first-write
      pattern is the same one used by ``_flow_events_var`` for events.

Eviction:
    - Bounded at ``MAX_CACHE_ENTRIES`` per request to cap memory growth in
      pathological agent runs that issue thousands of tool calls.
    - LRU order via ``collections.OrderedDict``: a cache hit moves the
      entry to the most-recent end, and a write past the cap drops the
      least-recently-used entry.

Errors are NOT cached:
    - If the producer raises, the cache stays untouched. The next call
      with the same key re-runs the producer. This matches the semantic
      a flaky network/registry call has — caching an exception would
      pin the failure for the whole request.
"""

from __future__ import annotations

import contextvars
import json
from collections import OrderedDict
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_CACHE_ENTRIES = 100

# Per-request cache. Default None lazily allocates the OrderedDict on
# first access in the current context so child contexts get their own
# instance instead of inheriting a shared one.
_cache_var: contextvars.ContextVar[OrderedDict[str, Any] | None] = contextvars.ContextVar(
    "lfx_tool_cache", default=None
)


T = TypeVar("T")


def _get_cache() -> OrderedDict[str, Any]:
    cache = _cache_var.get()
    if cache is None:
        cache = OrderedDict()
        _cache_var.set(cache)
    return cache


def _make_key(tool_name: str, args: dict[str, Any]) -> str:
    """Build a deterministic cache key from a tool name + its args.

    ``sort_keys=True`` makes the encoding insensitive to dict insertion
    order, so the same logical call hits the cache regardless of how the
    LLM happens to serialize its tool-call JSON. ``default=str`` keeps
    the encoding lossy-but-stable for any non-JSON arg (e.g. ``UUID``).
    """
    try:
        encoded_args = json.dumps(args, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # If args can't be serialized at all, skip the cache entirely by
        # returning a unique key (caller will treat as miss every time).
        encoded_args = repr(args)
    return f"{tool_name}::{encoded_args}"


def cached_tool_call(
    tool_name: str,
    args: dict[str, Any],
    producer: Callable[[], T],
) -> T:
    """Run ``producer`` once per ``(tool_name, args)`` within the current request.

    On cache hit, returns the stored value WITHOUT invoking ``producer``.
    On cache miss, invokes ``producer``, stores its return value, and
    returns it. If ``producer`` raises, the exception propagates and
    nothing is cached.

    The ``args`` dict serializes order-insensitively (``sort_keys``), so
    callers don't need to normalize keys before lookup.
    """
    key = _make_key(tool_name, args)
    cache = _get_cache()
    if key in cache:
        # Mark as most-recently used.
        cache.move_to_end(key)
        return cache[key]

    # Cache miss: produce, store on success, propagate on failure.
    value = producer()
    cache[key] = value
    cache.move_to_end(key)
    # LRU eviction: drop the oldest entry if we exceed the cap.
    while len(cache) > MAX_CACHE_ENTRIES:
        cache.popitem(last=False)
    return value


def reset_tool_cache() -> None:
    """Drop the cache for the current request.

    Setting the ContextVar back to ``None`` (rather than an empty
    OrderedDict) ensures any child context spawned after this reset
    lazily allocates its OWN fresh cache instead of inheriting and
    mutating one shared object. This is the same isolation primitive
    ``reset_flow_events`` uses for the SSE event queue.
    """
    _cache_var.set(None)
