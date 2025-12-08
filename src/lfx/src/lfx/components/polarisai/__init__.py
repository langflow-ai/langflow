from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .polaris_ai_data_insight import PolarisAIDataInsightComponent

_dynamic_imports = {
    "PolarisAIDataInsightComponent": "polaris_ai_data_insight",
}

__all__ = [
    "PolarisAIDataInsightComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import polarisai components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
