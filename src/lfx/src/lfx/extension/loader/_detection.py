"""Component-subclass detection for the extension loader.

After ``_discovery`` imports a bundle module, this module is responsible
for picking the Component subclasses out of the resulting namespace.  The
detection is intentionally heuristic (matches any class whose name or any
ancestor's name ends in ``Component``) so the loader doesn't have to drag
in the real ``lfx.custom.custom_component.component.Component`` -- that
class brings the full graph / vertex stack with it, and registration
doesn't need any of that.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types


# Bases that should never self-register, even if a bundle re-exports them.
# This is intentionally a small, name-only list; the loader runs at startup
# in the trusted-code path and does not need (or want) MRO walking against
# the live Component class.
_BASE_CLASS_NAMES: frozenset[str] = frozenset({"Component", "CustomComponent", "BaseComponent"})


def is_component_subclass(obj: object) -> bool:
    """Return True if ``obj`` is a Component subclass that should register.

    The check uses runtime MRO: a class registers iff one of its bases is
    named ``Component`` or ends with ``Component``.  This mirrors the AST
    heuristic in validate.py and avoids importing the real Component base
    here (the loader is part of lfx; importing the rich Component class
    pulls in graph/, vertex/, etc., which are not needed for registration).

    The Langflow base classes themselves (``Component``, ``CustomComponent``,
    ``BaseComponent``) are excluded by name so they don't self-register
    when a bundle re-exports them.
    """
    if not inspect.isclass(obj):
        return False
    if obj.__name__ in _BASE_CLASS_NAMES:
        return False
    for base in obj.__mro__[1:]:
        if base is object:
            continue
        if base.__name__ == "Component" or base.__name__.endswith("Component"):
            return True
    return False


def collect_component_classes(module: types.ModuleType) -> list[type]:
    """Return Component subclasses defined or aliased in ``module``.

    We require the class's ``__module__`` to match the module under
    inspection so that re-imports (``from x import Foo``) do not double
    register.  Stable order: iteration order of ``vars(module)`` is the
    insertion order in the module's namespace (i.e. source order), which
    is deterministic for a given source file.
    """
    seen: list[type] = []
    seen_ids: set[int] = set()
    module_name = module.__name__
    for value in vars(module).values():
        if not is_component_subclass(value):
            continue
        # Restrict to classes actually declared in this module to avoid
        # double-registering re-exported classes from another bundle file.
        if getattr(value, "__module__", None) != module_name:
            continue
        # Defensive: avoid duplicate references inside the same module
        # (e.g. ``Foo = Foo`` at the bottom of a file).
        if id(value) in seen_ids:
            continue
        seen.append(value)
        seen_ids.add(id(value))
    return seen
