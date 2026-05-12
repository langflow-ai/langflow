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


class _FieldTypingNamespace(dict):
    """Dict that resolves ``lfx.field_typing`` names on demand via ``__missing__``.

    WHY THIS EXISTS
    ---------------
    The previous implementation iterated ``field_typing.__all__`` and called
    ``getattr(field_typing, name)`` for every entry before passing the namespace
    to ``get_type_hints``.  Each ``getattr`` call triggered the lazy resolver in
    ``field_typing/constants.py``, which imports the real langchain class for that
    name.  Some of those imports chain as:

        langchain_classic.agents → transformers → torch._C  (a C extension)

    Loading ``torch._C`` registers a C-level cleanup handler via ``Py_AtExit()``.
    On ``release-1.10.0`` that import happened at process startup (before asyncio),
    so shutdown was orderly.  On this branch ``field_typing/constants.py`` is lazy,
    meaning torch was first imported *inside* the running asyncio event loop.
    During interpreter shutdown the C-level pybind11 atexit then ran after the
    event-loop state it referenced had already been freed — producing SIGSEGV
    (exit 139) on every ``lfx run`` invocation that used an agent component.

    HOW THIS FIXES IT
    -----------------
    ``__missing__`` is called by ``get_type_hints`` only when it actually needs a
    specific name while evaluating a string annotation.  A method annotated
    ``-> Message`` resolves only ``Message``; a method annotated ``-> str`` never
    touches ``field_typing`` at all.  The 30+ langchain symbols that chain to torch
    are therefore never imported unless a component annotation genuinely references
    them, avoiding the eager torch load inside asyncio.
    """

    def __missing__(self, key: str) -> Any:
        try:
            from lfx import field_typing

            val = getattr(field_typing, key)
        except (ImportError, AttributeError) as exc:
            raise KeyError(key) from exc
        self[key] = val
        return val


def get_runtime_type_hints(obj: Any) -> dict[str, Any]:
    """Return ``get_type_hints(obj)`` with ``lfx.field_typing`` names available.

    For bound methods, class-level attributes are also injected as locals so
    type aliases declared on the class resolve correctly.
    """
    globalns = _FieldTypingNamespace(getattr(obj, "__globals__", {}))
    localns = None
    bound_instance = getattr(obj, "__self__", None)
    if bound_instance is not None:
        # Bound-method case: inject the class's own attributes as locals so a
        # method annotated with a type alias declared on the class itself
        # (e.g. ``MyAlias: TypeAlias = ...`` at class scope, then
        # ``def f(self) -> MyAlias:``) resolves. ``typing.get_type_hints``
        # walks the MRO for class-level annotations but not for *bound method*
        # annotations, so without this the alias name would NameError.
        # Caveat: a class attribute named the same as a module-level symbol
        # would shadow it here; in practice annotations are simple types or
        # aliases, but worth noting if a future bug points back at this line.
        localns = vars(bound_instance.__class__)

    return get_type_hints(obj, globalns=globalns, localns=localns)
