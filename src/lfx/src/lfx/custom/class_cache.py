"""Bounded reuse of validated Python component classes across flow builds (opt-in).

Building a component class re-parses and re-executes its whole source. For the same source that work
is identical every time, so an opt-in cache can hand back the class built earlier. Instances are always
created fresh by the caller; only the *class* is shared.

Safety model:

* The cache is consulted only after source resolution and policy checks, so a hit can never authorize
  code the ordinary path rejects.
* The security boundary is the trusted-source gate: only a source that is, byte for byte, in the current
  component registry is reused. The registry holds built-in components, installed extension bundles, and
  components loaded from ``LANGFLOW_COMPONENTS_PATH`` (operator-provided). Custom or edited code that lives
  in a flow and not in the registry always takes the ordinary path. Registered code is assumed reviewed.
* On top of that sits a small best-effort mistake guard (``lfx.custom.class_eligibility``). It is NOT a
  sandbox; it only skips sources with patterns that would leak state between builds by accident.
* Entries are keyed by ``sha256(source)`` + class name, and the full source is compared on every hit.
* ``clear_component_class_cache`` bumps a generation counter and drops all entries; it is called when
  the component registry or an extension bundle is (re)loaded.
* Errors raised while building are never cached.
* Guard verdicts for declined sources are kept in a separate bounded map (not in the class LRU) so a
  declined source is parsed once rather than on every build.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

from lfx.custom.class_eligibility import ineligible_reason as _ineligible_reason
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_MAX_SIZE = 256


_lock = threading.Lock()
_entries: OrderedDict[tuple[str, str], tuple[str, type]] = OrderedDict()  # key -> (source, class)
_verdicts: OrderedDict[tuple[str, str], tuple[str, str]] = OrderedDict()  # key -> (source, decline reason)
_generation = 0
_hits = 0
_misses = 0
_declines: dict[str, int] = {}


def _digest(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8", "surrogatepass")).hexdigest()


def _is_trusted_source(code: str) -> bool:
    """Return True only when ``code`` is, byte for byte, a source in the current component registry.

    Uses the registry's hash-to-source map (one hash and one dict lookup per call, no registry scan), then
    compares the full string so a truncated-hash collision cannot pass. An uninitialized or just-invalidated
    registry has no map, so the answer is False.
    """
    try:
        from lfx.utils.flow_validation import get_trusted_code_for_validation

        return get_trusted_code_for_validation(code) == code
    except Exception:  # noqa: BLE001
        return False


def _read_policy() -> tuple[bool, int]:
    """Return ``(enabled, max_size)`` from the settings service; disabled when unavailable."""
    try:
        from lfx.services.deps import get_settings_service

        service = get_settings_service()
        settings = getattr(service, "settings", None)
    except Exception:  # noqa: BLE001
        return False, DEFAULT_MAX_SIZE
    if getattr(settings, "component_class_cache_enabled", False) is not True:
        return False, DEFAULT_MAX_SIZE
    max_size = getattr(settings, "component_class_cache_max_size", DEFAULT_MAX_SIZE)
    if not isinstance(max_size, int) or isinstance(max_size, bool) or max_size < 1:
        max_size = DEFAULT_MAX_SIZE
    return True, max_size


def _record_decline(reason: str) -> None:
    _declines[reason] = _declines.get(reason, 0) + 1


def _remember(table: OrderedDict, key: tuple[str, str], value: tuple, generation: int, max_size: int) -> tuple:
    """Insert ``value`` unless the generation moved; first writer wins so concurrent builders converge.

    A different source under the same digest (collision) leaves the incumbent and the newcomer uncached.
    """
    with _lock:
        existing = table.get(key)
        if existing is not None:
            return existing if existing[0] == value[0] else value
        if generation == _generation:
            table[key] = value
            while len(table) > max_size:
                table.popitem(last=False)
        return value


def get_or_build_component_class(code: str, class_name: str, build: Callable[[], type]) -> type:
    """Return a cached component class for ``code``/``class_name`` or build it with ``build``.

    ``class_name`` must already be resolved. ``build`` is the ordinary uncached path; exceptions it raises
    propagate unchanged and are never cached. When the cache is disabled, or ``code`` is not a trusted registry
    source, this is just ``build()``.
    """
    global _hits, _misses  # noqa: PLW0603
    enabled, max_size = _read_policy()
    if not enabled:
        if _entries or _verdicts:  # drop retained state once the cache is observed disabled
            clear_component_class_cache()
        return build()

    if not _is_trusted_source(code):
        with _lock:
            _record_decline("untrusted_source")
        return build()

    key = (_digest(code), class_name)
    with _lock:
        for table in (_entries, _verdicts):  # the limit may have been lowered since the last store
            while len(table) > max_size:
                table.popitem(last=False)
        entry = _entries.get(key)
        if entry is not None and entry[0] == code:
            _entries.move_to_end(key)
            _hits += 1
            return entry[1]
        verdict = _verdicts.get(key)
        if verdict is not None and verdict[0] == code:
            _verdicts.move_to_end(key)
            _record_decline(verdict[1])
            return_uncached = True
        else:
            return_uncached = False
        generation = _generation
    if return_uncached:
        return build()

    reason = _ineligible_reason(code)
    if reason is not None:
        logger.debug(f"Component class cache declined {class_name}: {reason}")
    component_class = build()
    if reason is None:
        from lfx.custom.custom_component.component import Component

        # Only Component.__init__ deep-copies inputs/outputs per instance; legacy classes are not proven.
        if not (isinstance(component_class, type) and issubclass(component_class, Component)):
            reason = "not_component_subclass"

    if reason is not None:
        with _lock:
            _record_decline(reason)
        _remember(_verdicts, key, (code, reason), generation, max_size)
        return component_class

    stored = _remember(_entries, key, (code, component_class), generation, max_size)
    with _lock:
        _misses += 1
    return stored[1]


def clear_component_class_cache() -> None:
    """Drop every cached class and bump the generation so in-flight builds are not stored."""
    global _generation  # noqa: PLW0603
    with _lock:
        _generation += 1
        _entries.clear()
        _verdicts.clear()


def component_class_cache_stats() -> dict[str, object]:
    """Return counters and size; never includes source code or parameters."""
    with _lock:
        return {
            "hits": _hits,
            "misses": _misses,
            "declines": sum(_declines.values()),
            "decline_reasons": dict(_declines),
            "size": len(_entries),
            "declined_size": len(_verdicts),
            "generation": _generation,
        }


def reset_component_class_cache_stats() -> None:
    """Reset the hit/miss/decline counters (the cached entries are kept)."""
    global _hits, _misses  # noqa: PLW0603
    with _lock:
        _hits = 0
        _misses = 0
        _declines.clear()
