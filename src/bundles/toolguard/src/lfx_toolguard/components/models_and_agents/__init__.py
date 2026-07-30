from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .policies_component import PoliciesComponent

__all__ = ["PoliciesComponent"]


def __getattr__(attr_name: str) -> Any:
    if attr_name not in __all__:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    result = import_mod(attr_name, "policies_component", __spec__.parent)
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
