"""Lazy-resolved class objects for langchain field types.

Pairs with ``names.py``: that module owns the static metadata
(resolution paths, TypeVar specs); this module owns the actual
class objects, resolved on demand via PEP 562 ``__getattr__``.
Importing this module does not pull langchain at import time;
resolution happens only when a consumer accesses a class.

``LANGCHAIN_BASE_TYPES`` and ``CUSTOM_COMPONENT_SUPPORTED_TYPES``
are built fresh on each access (not cached on the module). Reading
either dict materializes every langchain class — and, for the
latter, ``lfx.schema.dataframe`` (pandas). Callers that only need
to enumerate the names should iterate ``names.LANGCHAIN_BASE_TYPE_KEYS``
or ``names.LANGCHAIN_SYMBOLS`` directly to stay off the import path.

Stub fallbacks (``_FooStub``) keep type annotations resolvable when
langchain itself is unimportable — installation gap or transitive
native-dep failure on Windows (``c10.dll``). Stubs are never cached
under public names so a transient failure does not pin a process.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from typing import Any, TypeAlias, TypeVar

from lfx.field_typing.names import LANGCHAIN_BASE_TYPE_KEYS, LANGCHAIN_SYMBOLS, TYPEVAR_SPECS
from lfx.schema.data import JSON, Data

# ``Text`` is re-exported as a public name because downstream modules (notably
# ``lfx.template.field.base``) import it as ``from lfx.field_typing import Text``.
# In Python 3.x ``typing.Text`` is ``str``; the alias keeps existing callers
# working without changes.
Text = str

# -- Local non-langchain types (always eager) --------------------------------


class Object:
    """Generic object type for custom components."""


class Code:
    """Code type for custom components."""


NestedDict: TypeAlias = dict[str, str | dict]


# -- Stub classes (private; used on ImportError/OSError fallback) ------------
# Generated from the resolution table so that every name in ``LANGCHAIN_SYMBOLS``
# has a fallback. Names are underscore-prefixed (``_FooStub``) so they do not
# shadow the public symbol; the PEP 562 ``__getattr__`` below only fires when
# the public name is absent from ``globals()``.
_STUBS: dict[str, type] = {name: type(f"_{name}Stub", (), {}) for name in LANGCHAIN_SYMBOLS}
_STUB_TYPES: tuple[type, ...] = tuple(_STUBS.values())

# Tracks symbols whose import has already failed once, so the warning fires
# at most once per process per symbol.
_STUB_WARNED: set[str] = set()


def _is_stub(value: Any) -> bool:
    """Return True if ``value`` is one of our private stub classes.

    Also walks one level into TypeVar ``__bound__``/``__constraints__`` since a
    TypeVar built on top of stub-resolved langchain classes is itself degraded.
    Aggregate dicts (``LANGCHAIN_BASE_TYPES`` etc.) are not cached on this
    module, so we do not need to recurse into them.
    """
    if value in _STUB_TYPES:
        return True
    constraints = getattr(value, "__constraints__", ())
    if constraints and any(c in _STUB_TYPES for c in constraints):
        return True
    bound = getattr(value, "__bound__", None)
    return bound is not None and bound in _STUB_TYPES


def _cache_if_concrete(name: str, value: Any) -> Any:
    """Cache ``value`` under ``name`` only if it is fully resolved.

    Stub-backed values are returned but not cached so a later call has a
    chance to retry the real import. This matters for transient failures and
    for prefork servers (Gunicorn ``preload_app=True``): if the parent
    cached a stub, every worker would inherit that degraded value after fork.
    """
    if _is_stub(value):
        globals().pop(name, None)
        return value
    globals()[name] = value
    return value


def _clear_degraded_caches_after_fork() -> None:
    """Drop stub-backed symbol caches inherited from a prefork parent."""
    _STUB_WARNED.clear()
    for name in (*tuple(LANGCHAIN_SYMBOLS), *tuple(TYPEVAR_SPECS)):
        cached = globals().get(name)
        if cached is not None and _is_stub(cached):
            globals().pop(name, None)


# ``os.register_at_fork`` has no unregister API. Reloads of this module via
# ``monkeypatch.delitem(sys.modules, ...)`` (see test_lazy_imports.py) will
# accumulate handlers across the test run. Idempotent — they only ever clear
# stub-backed caches — so this is overhead, not a correctness issue.
if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_clear_degraded_caches_after_fork)


def _resolve_langchain_symbol(name: str) -> Any:
    """Return the real langchain class if importable, else the private stub."""
    module_path, attr = LANGCHAIN_SYMBOLS[name]
    try:
        module = importlib.import_module(module_path)
        return getattr(module, attr)
    except (ImportError, OSError, AttributeError) as exc:
        # Import failed (langchain not installed; a transitive native dep
        # like torch's c10.dll failing with ``OSError: [WinError 126]`` on
        # Windows without the MSVC redistributable; or an upstream rename
        # that drops ``attr`` from a still-importable module — the legacy
        # ``from langchain_classic.agents import AgentExecutor`` form
        # converted this last case to ImportError, but ``getattr`` raises
        # AttributeError directly). Fall back to the stub so simple type
        # annotations still resolve, but warn once per symbol so a broken
        # install is not invisible to support engineers.
        if name not in _STUB_WARNED:
            _STUB_WARNED.add(name)
            from lfx.log.logger import logger

            logger.warning(
                f"lfx.field_typing.constants: {module_path}.{attr} unavailable "
                f"({type(exc).__name__}: {exc}); falling back to stub. Downstream "
                "isinstance/issubclass checks against this name will not match real "
                "langchain objects."
            )
        return _STUBS[name]


def _get_langchain(name: str) -> Any:
    """Return the cached or freshly-resolved langchain class for ``name``."""
    cached = globals().get(name)
    if cached is not None and not _is_stub(cached):
        return cached
    # Either uncached or previously cached as the stub. Re-attempt the real
    # import: a transient earlier failure should not poison the process for
    # life.
    return _cache_if_concrete(name, _resolve_langchain_symbol(name))


def _build_typevar(name: str) -> TypeVar:
    """Construct the requested TypeVar with constraints resolved lazily."""
    spec = TYPEVAR_SPECS.get(name)
    if spec is None:
        msg = f"unknown typevar: {name}"
        raise AttributeError(msg)
    kind, value = spec
    if kind == "bound":
        assert isinstance(value, str)  # noqa: S101 - shape guarantee from TYPEVAR_SPECS
        built = TypeVar(name, bound=_get_langchain(value))
    else:
        assert isinstance(value, tuple)  # noqa: S101 - shape guarantee from TYPEVAR_SPECS
        built = TypeVar(name, *(_get_langchain(c) for c in value))
    return _cache_if_concrete(name, built)


def _get_typevar(name: str) -> TypeVar:
    """Return the cached TypeVar for ``name`` or build it now."""
    cached = globals().get(name)
    if cached is not None and not _is_stub(cached):
        return cached
    return _build_typevar(name)


def _build_LANGCHAIN_BASE_TYPES() -> dict[str, Any]:  # noqa: N802 - public dict name
    """Materialize ``LANGCHAIN_BASE_TYPES`` fresh.

    Not cached on this module: building on demand keeps stub-detection trivial
    and removes the recursive cache-walk the previous design needed for
    aggregate dicts. Per-symbol caches in ``globals()`` still memoize the
    real classes, so subsequent rebuilds are cheap.
    """
    return {key: _get_typevar(key) if key in TYPEVAR_SPECS else _get_langchain(key) for key in LANGCHAIN_BASE_TYPE_KEYS}


def _build_CUSTOM_COMPONENT_SUPPORTED_TYPES() -> dict[str, Any]:  # noqa: N802 - public dict name
    """Materialize ``CUSTOM_COMPONENT_SUPPORTED_TYPES`` fresh.

    Reading this dict eagerly resolves langchain *and* ``lfx.schema.dataframe``
    (which pulls pandas). Callers that only need to check whether a name
    exists should iterate ``names.LANGCHAIN_BASE_TYPE_KEYS`` and the local
    additions below directly instead of materializing the class-valued dict.
    """
    from lfx.schema.dataframe import DataFrame, Table

    return {
        **_build_LANGCHAIN_BASE_TYPES(),
        "NestedDict": NestedDict,
        "Data": Data,
        "JSON": JSON,
        "Text": Text,
        "Object": Object,
        "Callable": Callable,
        "LanguageModel": _get_typevar("LanguageModel"),
        "Retriever": _get_typevar("Retriever"),
        "DataFrame": DataFrame,
        "Table": Table,
    }


# -- PEP 562 module-level __getattr__ ----------------------------------------


def __getattr__(name: str) -> Any:
    """Lazy resolution for langchain classes, TypeVars, and aggregate dicts."""
    if name in LANGCHAIN_SYMBOLS:
        return _get_langchain(name)
    if name in TYPEVAR_SPECS:
        return _build_typevar(name)
    if name == "LANGCHAIN_BASE_TYPES":
        return _build_LANGCHAIN_BASE_TYPES()
    if name == "CUSTOM_COMPONENT_SUPPORTED_TYPES":
        return _build_CUSTOM_COMPONENT_SUPPORTED_TYPES()
    if name in {"DataFrame", "Table"}:
        # Cache both at once: ``lfx.schema.dataframe`` is loaded as a unit, so
        # paying the cost for one means we can hand out the other for free
        # without re-firing ``__getattr__``.
        from lfx.schema.dataframe import DataFrame, Table

        globals()["DataFrame"] = DataFrame
        globals()["Table"] = Table
        return globals()[name]

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
