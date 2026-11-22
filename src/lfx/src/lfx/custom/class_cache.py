"""Reuse of validated Python classes for a few reviewed built-in components across flow builds (opt-in).

Building a component class re-parses and re-executes its whole source. For the same source that work
is identical every time, so an opt-in cache can hand back the class built earlier. Instances are always
created fresh by the caller; only the *class* is shared.

Safety model:

* The cache is consulted only after source resolution and policy checks, so a hit can never authorize
  code the ordinary path rejects.
* Only the components in ``REVIEWED_COMPONENTS`` are reused. Each entry pins the sha256 of the exact source
  that was reviewed (and confirmed to keep no state on the class or at module level). A source qualifies only
  if its digest is pinned and the class being built is that entry's component. Any edit changes the digest, so
  edited or updated source takes the ordinary path until it is reviewed again (a test fails when a shipped file no
  longer matches its pin). Custom code, extension bundles and ``LANGFLOW_COMPONENTS_PATH`` components always
  take the ordinary path. No code is analysed at runtime.
* The source must also be, byte for byte, in the current component registry (the trusted-source gate), so
  an overridden or unloaded registry never serves a cached class.
* The built class must be a ``Component`` subclass: only ``Component.__init__`` copies ``inputs``/``outputs``
  per instance. Every reviewed entry is one; the check is kept as a safeguard.
* Entries are keyed by digest and class name, and the full source is compared on every hit.
* ``clear_component_class_cache`` bumps a generation counter and drops all entries; it is called when
  the component registry or an extension bundle is (re)loaded.
* Errors raised while building are never cached.
"""

from __future__ import annotations

import hashlib
import threading
from typing import TYPE_CHECKING

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable

# (file under ``lfx/components``, component class, sha256 of the reviewed source). Add or update an entry only
# after reviewing that the file keeps no state on the class or at module level.
REVIEWED_COMPONENTS = (
    ("input_output/chat.py", "ChatInput", "45974e6b1909ddbbfec5381cf528523131c7579f3724a1a6cc05ab62cfc63827"),
    ("input_output/chat_output.py", "ChatOutput", "0aab1c78e1dc24ff5a066dc8db75a695aa46cb3ba8fbb13c34f70672c5f2b967"),
    ("input_output/text.py", "TextInputComponent", "2811c0e0496fb2b0fc9eb115823699e04b1629846395340cc50dd37feb5d2f89"),
    (
        "input_output/text_output.py",
        "TextOutputComponent",
        "3ececc60ddafd6328dcc7235739e05d03696602ac1afd5d1263d8ac340ba8d15",
    ),
    (
        "processing/create_list.py",
        "CreateListComponent",
        "5657383579615ce5781924b307013d60e7662b45bca7e3f8db021813eefef73f",
    ),
    ("processing/parser.py", "ParserComponent", "cc797b144b5db59f071000d22ecca10d2df9dfbcd1b28020b9dc89da60aba95a"),
    (
        "processing/converter.py",
        "TypeConverterComponent",
        "60cbfe96d7eb4f462553bbe8afddf7e289a68e90651d9a6a4b0362bc76e34c4d",
    ),
    (
        "models_and_agents/prompt.py",
        "PromptComponent",
        "e3714ffe5d15e1c8ee7410f0449c0d4641cb1c6c92bd6c63e9e2aa22a3f00098",
    ),
)
_REVIEWED_CLASS_BY_DIGEST = {digest: class_name for _path, class_name, digest in REVIEWED_COMPONENTS}

_lock = threading.Lock()
_entries: dict[tuple[str, str], tuple[str, type]] = {}  # (digest, class name) -> (source, class)
_generation = 0
_hits = 0
_misses = 0
_declines: dict[str, int] = {}


def source_digest(source: str) -> str:
    """Return the sha256 hex digest used to pin reviewed sources."""
    return hashlib.sha256(source.encode("utf-8", "surrogatepass")).hexdigest()


def _is_reviewed(digest: str, class_name: str) -> bool:
    """Return True only when ``digest`` is pinned in ``REVIEWED_COMPONENTS`` for ``class_name``."""
    return _REVIEWED_CLASS_BY_DIGEST.get(digest) == class_name


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


def _cache_enabled() -> bool:
    """Return whether the cache is enabled in the settings service; disabled when unavailable."""
    try:
        from lfx.services.deps import get_settings_service

        settings = getattr(get_settings_service(), "settings", None)
    except Exception:  # noqa: BLE001
        return False
    return getattr(settings, "component_class_cache_enabled", False) is True


def _record_decline(reason: str) -> None:
    with _lock:
        _declines[reason] = _declines.get(reason, 0) + 1


def get_or_build_component_class(code: str, class_name: str, build: Callable[[], type]) -> type:
    """Return a cached component class for ``code``/``class_name`` or build it with ``build``.

    ``class_name`` must already be resolved. ``build`` is the ordinary uncached path; exceptions it raises
    propagate unchanged and are never cached. When the cache is disabled, or ``code`` is not a reviewed,
    trusted registry source, this is just ``build()``.
    """
    global _hits, _misses  # noqa: PLW0603
    if not _cache_enabled():
        if _entries:  # drop retained state once the cache is observed disabled
            clear_component_class_cache()
        return build()

    digest = source_digest(code)
    if not _is_reviewed(digest, class_name):
        _record_decline("not_reviewed")
        return build()
    if not _is_trusted_source(code):
        _record_decline("untrusted_source")
        return build()

    key = (digest, class_name)
    with _lock:
        entry = _entries.get(key)
        if entry is not None and entry[0] == code:
            _hits += 1
            return entry[1]
        generation = _generation

    component_class = build()
    from lfx.custom.custom_component.component import Component

    # Only Component.__init__ deep-copies inputs/outputs per instance; legacy classes are not proven.
    if not (isinstance(component_class, type) and issubclass(component_class, Component)):
        logger.debug(f"Component class cache declined {class_name}: not_component_subclass")
        _record_decline("not_component_subclass")
        return component_class

    with _lock:
        _misses += 1
        existing = _entries.get(key)
        if existing is not None:  # first writer wins so concurrent builders converge; a collision stays uncached
            return existing[1] if existing[0] == code else component_class
        if generation == _generation:  # not stored when the registry was reloaded mid-build
            _entries[key] = (code, component_class)
    return component_class


def clear_component_class_cache() -> None:
    """Drop every cached class and bump the generation so in-flight builds are not stored."""
    global _generation  # noqa: PLW0603
    with _lock:
        _generation += 1
        _entries.clear()


def component_class_cache_stats() -> dict[str, object]:
    """Return counters and size; never includes source code or parameters."""
    with _lock:
        return {
            "hits": _hits,
            "misses": _misses,
            "declines": sum(_declines.values()),
            "decline_reasons": dict(_declines),
            "size": len(_entries),
            "generation": _generation,
        }


def reset_component_class_cache_stats() -> None:
    """Reset the hit/miss/decline counters (the cached entries are kept)."""
    global _hits, _misses  # noqa: PLW0603
    with _lock:
        _hits = 0
        _misses = 0
        _declines.clear()
