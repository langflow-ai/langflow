from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import custom_component as custom_component
    from . import utils as utils
    from .custom_component.component import Component
    from .custom_component.custom_component import CustomComponent

__all__ = ["Component", "CustomComponent", "custom_component", "utils"]

_DYNAMIC_IMPORTS = {
    "Component": (".custom_component.component", "Component"),
    "CustomComponent": (".custom_component.custom_component", "CustomComponent"),
    "custom_component": (".custom_component", None),
    "utils": (".utils", None),
}


def __getattr__(name: str) -> Any:
    """Resolve public exports lazily to keep cold-start imports light."""
    if name not in _DYNAMIC_IMPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)

    module_name, attr_name = _DYNAMIC_IMPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return list(__all__)
