from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from .opendataloader_pdf import OpenDataLoaderPDFComponent  # noqa: F401

_all_components = [
    "OpenDataLoaderPDFComponent",
]

_all_dynamic_imports = {
    "OpenDataLoaderPDFComponent": "opendataloader_pdf",
}

__all__: list[str] = _all_components  # noqa: PLE0605
_dynamic_imports: dict[str, str] = _all_dynamic_imports


def __getattr__(attr_name: str) -> Any:
    """Lazily import opendataloader_pdf components on attribute access."""
    if attr_name not in _all_dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _all_dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return _all_components
