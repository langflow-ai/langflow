"""Regression tests for runtime type-hint resolution.

The bug: components consistently use ``from __future__ import annotations`` and
import langchain symbols only under ``if TYPE_CHECKING:``. Plain
``typing.get_type_hints`` then raises ``NameError`` when it tries to resolve
the lazy annotation strings — for example ``-> list[Tool]`` on
``Component.to_toolkit`` — because ``Tool`` is not in the function's
``__globals__`` at runtime. ``get_runtime_type_hints`` injects the public
``lfx.field_typing`` names so the resolution succeeds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from langchain_core.tools import Tool


def test_resolves_typecheck_only_name_via_field_typing():
    """Resolve a TYPE_CHECKING-only langchain symbol via the runtime helper.

    Mirrors the path ``Component._get_method_return_type`` uses for tool-mode
    components.
    """
    from lfx.utils.type_hints import get_runtime_type_hints

    async def to_toolkit() -> list[Tool]:  # type: ignore[name-defined]
        return []

    hints = get_runtime_type_hints(to_toolkit)
    return_type = hints.get("return")
    # Resolves to ``list[langchain_core.tools.Tool]`` — the TypeVar/Tool class object,
    # not a string. If __future__ + TYPE_CHECKING wasn't bridged, this would raise
    # NameError before the assert ran.
    assert return_type is not None
    assert "Tool" in repr(return_type)


def test_plain_get_type_hints_would_raise_for_baseline_proof():
    """Vanilla ``get_type_hints`` raises on the same function shape.

    Confirms the helper is doing real work and isn't a tautology.
    """
    from typing import get_type_hints

    async def to_toolkit() -> list[Tool]:  # type: ignore[name-defined]
        return []

    with pytest.raises(NameError, match="Tool"):
        get_type_hints(to_toolkit)
