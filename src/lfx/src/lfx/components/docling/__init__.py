from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod
from lfx.utils.validate_cloud import is_astra_cloud_environment

if TYPE_CHECKING:
    from .chunk_docling_document import ChunkDoclingDocumentComponent  # noqa: F401
    from .docling_inline import DoclingInlineComponent  # noqa: F401
    from .docling_remote import DoclingRemoteComponent  # noqa: F401
    from .export_docling_document import ExportDoclingDocumentComponent  # noqa: F401

_all_components = [
    "ChunkDoclingDocumentComponent",
    "DoclingInlineComponent",
    "DoclingRemoteComponent",
    "ExportDoclingDocumentComponent",
]

_all_dynamic_imports = {
    "ChunkDoclingDocumentComponent": "chunk_docling_document",
    "DoclingInlineComponent": "docling_inline",
    "DoclingRemoteComponent": "docling_remote",
    "ExportDoclingDocumentComponent": "export_docling_document",
}

# Components that require local Docling/EasyOCR dependencies (disabled in cloud)
_cloud_disabled_components = {
    "ChunkDoclingDocumentComponent",
    "DoclingInlineComponent",
    "ExportDoclingDocumentComponent",
}


def _get_available_components() -> list[str]:
    """Get list of available components, filtering out cloud-disabled ones."""
    if is_astra_cloud_environment():
        # Only show DoclingRemoteComponent (Docling Serve) in cloud
        return [comp for comp in _all_components if comp not in _cloud_disabled_components]
    return _all_components


def _get_dynamic_imports() -> dict[str, str]:
    """Get dynamic imports dict, filtering out cloud-disabled ones."""
    if is_astra_cloud_environment():
        # Only allow DoclingRemoteComponent (Docling Serve) in cloud
        return {k: v for k, v in _all_dynamic_imports.items() if k not in _cloud_disabled_components}
    return _all_dynamic_imports


# Dynamically set __all__ and _dynamic_imports based on cloud environment
__all__: list[str] = _get_available_components()  # noqa: PLE0605
_dynamic_imports: dict[str, str] = _get_dynamic_imports()


def __getattr__(attr_name: str) -> Any:
    """Lazily import docling components on attribute access."""
    # Check if component is available (not disabled in cloud)
    if is_astra_cloud_environment() and attr_name in _cloud_disabled_components:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)

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
    return _get_available_components()
