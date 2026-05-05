"""Runtime type-hint resolution helper.

Wraps ``typing.get_type_hints`` with the public names from
``lfx.field_typing`` injected into the function's resolution namespace.
This is needed because components consistently use ``from __future__ import
annotations`` and import langchain symbols only under ``if TYPE_CHECKING:``
to keep them off the cold-start path. The annotations end up as strings
(PEP 563); ``get_type_hints`` later evaluates those strings and fails with
``NameError`` if the symbol is not in the function's ``__globals__``.

Tool-mode component instantiation hits this: ``Component.to_toolkit`` is
annotated ``-> list[Tool]`` with ``Tool`` only declared under
``TYPE_CHECKING``. Resolving its return type via plain ``get_type_hints``
raises ``NameError: name 'Tool' is not defined``. Injecting the public
``lfx.field_typing`` names — which lazily resolve to the real classes when
accessed — closes that gap.
"""

from __future__ import annotations

from typing import Any, get_type_hints


def get_runtime_type_hints(obj: Any) -> dict[str, Any]:
    """Return ``get_type_hints(obj)`` with ``lfx.field_typing`` names available.

    For bound methods, class-level attributes are also injected as locals so
    type aliases declared on the class resolve correctly.
    """
    globalns = dict(getattr(obj, "__globals__", {}))
    localns = None
    bound_instance = getattr(obj, "__self__", None)
    if bound_instance is not None:
        localns = vars(bound_instance.__class__)

    try:
        from lfx import field_typing

        for name in getattr(field_typing, "__all__", ()):
            try:
                globalns.setdefault(name, getattr(field_typing, name))
            except Exception:  # noqa: BLE001, S112 - best-effort: any failure on a single name skips that name
                continue
    except Exception:  # noqa: BLE001, S110 - best-effort: if field_typing itself is broken, fall back to plain hints
        pass

    return get_type_hints(obj, globalns=globalns, localns=localns)
