"""Autogenerate rules for schema objects that exist on one database dialect only.

Some objects only make sense on one backend, for example PostgreSQL GIN
indexes over jsonb columns. The model declares them with ``ddl_if`` so
``create_all`` skips them elsewhere, and marks them with
``info={"dialects": (...)}`` so autogenerate can skip them too: it does not
read ``ddl_if``, and would otherwise report them missing on every other
backend and fail the startup schema check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def include_object_for(dialect_name: str) -> Callable[..., bool]:
    """Return an ``include_object`` hook that compares an object only on its own dialects."""

    def include_object(obj: Any, _name: str | None, _type: str, reflected: bool, _compare_to: Any) -> bool:  # noqa: FBT001
        dialects = getattr(obj, "info", {}).get("dialects")
        return reflected or not dialects or dialect_name in dialects

    return include_object
